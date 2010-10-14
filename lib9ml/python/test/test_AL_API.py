
import unittest
import nineml.abstraction_layer as nineml

import os, tempfile



class ComponentTestCase(unittest.TestCase):

    def test_expressions(self):
        from nineml.abstraction_layer import expr_to_obj

        # no redefining or modifying math symbols
        self.assertRaises(ValueError, expr_to_obj,"pi:=11")
        self.assertRaises(ValueError, expr_to_obj,"x:=10+x")

        self.assertRaises(ValueError, expr_to_obj,"dpi/dt = 10+x")
        self.assertRaises(ValueError, expr_to_obj,"de/dt = 10+x")

        self.assertRaises(ValueError, expr_to_obj,"e = 10+x")
        self.assertRaises(ValueError, expr_to_obj,"pi = 10+x")

        self.assertRaises(ValueError, expr_to_obj,"pi += 10")
        self.assertRaises(ValueError, expr_to_obj,"e += 10")

        # undefined functions
        #self.assertRaises(ValueError, expr_to_obj,"U = WhatFunc(x)")


        # assignment self referencing detection
        e = expr_to_obj("U = U+1")
        assert e.self_referencing()
        
        e = expr_to_obj("U = V+1")
        assert not e.self_referencing()

    def test_binding_backsub(self):
        from nineml.abstraction_layer import expr_to_obj, get_args

        # Determine missing functions
        e = expr_to_obj("U(x,y):= exp(x) + y")
        assert list(e.missing_functions)==[]

        e = expr_to_obj("dA/dt = exp(x) + whatfunc(u)")
        assert list(e.missing_functions) == ['whatfunc']

        e = expr_to_obj("U = exp(x) + q(u,U)")
        assert list(e.missing_functions) == ['q']

        e = expr_to_obj("U(x,y):= exp(x) + _q10(y,x)")
        assert list(e.missing_functions) == ['_q10']

        e = expr_to_obj("U(x,y):= exp(x) + _q10(y,x)")
        b = expr_to_obj("_q10 := 20")
        self.assertRaises(ValueError, e.substitute_binding, b)

        e = expr_to_obj("U = exp(x) + _q10")
        e.substitute_binding(b)
        #print e.rhs
        assert e.rhs == "exp(x) + (20)"

        i,args = get_args("exp(exp(z)+1),cos(sin(q)-tan(z))) + 1/_q10(z,w)")
        assert args == ['exp(exp(z)+1)', 'cos(sin(q)-tan(z))']
        
    
        e = expr_to_obj("U(x,y):= exp(x) + _q10(y,x) + 1/_q10(z,w)")
        b = expr_to_obj("_q10(a,b) := a+b")
        e.substitute_binding(b)
        #print e.rhs
        assert e.rhs == "exp(x) + (y+x) + 1/(z+w)"

        e = expr_to_obj("dA/dt = exp(x) + _q10(exp(exp(z)+1),cos(sin(q)-tan(z))) + 1/_q10(z,w)")
        b = expr_to_obj("_q10(a,b) := a+b")
        e.substitute_binding(b)
        assert e.rhs == "exp(x) + (exp(exp(z)+1)+cos(sin(q)-tan(z))) + 1/(z+w)"

        # check that it does all levels of binding resolution (i.e. also in arguments of a binding)
        e = expr_to_obj("dA/dt = exp(x) + _q10(_q10(exp(z),1),cos(sin(q)-tan(z))) + 1/_q10(z,w)")
        b = expr_to_obj("_q10(a,b) := a+b")
        e.substitute_binding(b)
        assert e.rhs == "exp(x) + ((exp(z)+1)+cos(sin(q)-tan(z))) + 1/(z+w)"

        # catch number of args mismatch
        e = expr_to_obj("U(x,y):= exp(x) + _q10(y,x,z) + 1/_q10(z,w)")
        self.assertRaises(ValueError, e.substitute_binding, b)
        
        # check recursive binding is caught
        self.assertRaises(ValueError, expr_to_obj, "a(x) := a(x) + 1")

        # check
        b1 = expr_to_obj("v1(x) := exp(x)")
        b2 = expr_to_obj("p := e")
        b1.substitute_binding(b2)
        #print b1.rhs
        assert b1.rhs == "exp(x)"
        

        # check catch of binding rhs having no dependance on lhs args
        self.assertRaises(ValueError, expr_to_obj, "a(x) := exp(z) + 1")
        self.assertRaises(ValueError, expr_to_obj, "a(x,y,z) := exp(z) + x")
        b = expr_to_obj("a(x,y,z) := exp(z) + x + y")

        b1 = expr_to_obj("v1(x) := 1/v2(x+1,v3(x)+1) + v3(x)")
        b2 = expr_to_obj("v2(x,y) := v3(x)*y + 10")
        b3 = expr_to_obj("v3(x) := exp(x)")
        b2.substitute_binding(b3)
        #print b2.rhs
        assert b2.rhs == "(exp(x))*y + 10"
        b1.substitute_binding(b2)
        #print b1.rhs
        assert b1.rhs == "1/((exp(x+1))*v3(x)+1 + 10) + v3(x)"
        b1.substitute_binding(b3)
        #print b1.rhs
        assert b1.rhs == "1/((exp(x+1))*(exp(x))+1 + 10) + (exp(x))"
        #assert e.rhs == "exp(x) + ((exp(z)+1)+cos(sin(q)-tan(z))) + 1/(z+w)"



        # now to components

        bindings = [
            "v1(x) := 1/v2(x+1,v3(x)+1) + v3(x)",
            "v2(x,y) := v3(x)*y + 10",
            "v3(x) := exp(x)**2"
            ]
        r = nineml.Union("dV/dt = 0.04*V*V + 5*V + 140.0 - U + Isyn + v1(v3(x))")

        c1 = nineml.Component("Izhikevich", regimes = [r], bindings=bindings )
        c1.backsub_bindings()
        c1.backsub_equations()

        bm = c1.bindings_map
        assert bm['v1'].rhs == "1/((exp(x+1)**2)*(exp(x)**2)+1 + 10) + (exp(x)**2)"
        assert bm['v2'].rhs == "(exp(x)**2)*y + 10"
        assert bm['v3'].rhs == "exp(x)**2"
        for e in c1.equations:
            assert e.rhs == "0.04*V*V + 5*V + 140.0 - U + Isyn + (1/((exp((exp(x)**2)+1)**2)*(exp((exp(x)**2))**2)+1 + 10) + (exp((exp(x)**2))**2))"

        # TODO More tests here ... Although the basic functionality is there,
        # as the code is custom written, some syntactic differences might still
        # cause problems.  An implementation using sympy might also be an option
        # to consider ...

    def test_ports_construction(self):

        # Check catches bad mode
        self.assertRaises(ValueError, nineml.AnalogPort,"q",mode="11")

        # Check catches op on non-reduce port
        self.assertRaises(ValueError, nineml.AnalogPort,"q",mode="send", op='+')

        # Check catches bad op for reduce port
        self.assertRaises(ValueError, nineml.AnalogPort,"q",mode="reduce", op='^')

        # No expressions for 'recv','reduce'
        for mode in ('recv','reduce'):
            self.assertRaises(ValueError, nineml.AnalogPort,"q = v**2",mode=mode)

        # Check symbol as expression ...
        p = nineml.AnalogPort("q = v**2",mode='send')
        assert p.symbol == 'q'
        assert p.expr.rhs == "v**2"

        # catch a binding expression ...
        self.assertRaises(ValueError, nineml.AnalogPort, "q := v**2",mode='send')
        # ode
        self.assertRaises(ValueError, nineml.AnalogPort, "dq/dt = v**2",mode='send')
        # inplace
        self.assertRaises(ValueError, nineml.AnalogPort, "q += 10",mode='send')

    def test_find_port_expr_symbols(self):
        # check that symbols on rhs of a 'send' port expr
        # are considered for user parameters

        parameters = ['tau','E','q']
        
        regimes = [
            nineml.Union(
                "dg/dt = -g/tau",
                events = nineml.On(nineml.SpikeInputEvent,do="g+=q")
                )]

        ports = [nineml.RecvPort("V"),
                 nineml.SendPort("Isyn = g(E-V)")]

        coba_syn = nineml.Component("CoBaSynapse", regimes = regimes, ports = ports)

        assert sorted(parameters) == sorted(coba_syn.parameters)
        

    def test_ports_diverse(self):

        r = nineml.Union(
            "dV/dt = 0.04*V*V + 5*V + 140.0 - U + Isyn",
            events = [nineml.On(nineml.SpikeInputEvent,do="V+=10"),
                      nineml.On("V>Vth",do=["V=c","U+=d",nineml.SpikeOutputEvent])])

        c1 = nineml.Component("Izhikevich", regimes = [r], ports=[nineml.AnalogPort("V")] )
        ep = list(c1.event_ports)
        assert len(ep)==2

        # test some port filtering, get with symb="V"
        ep = list(c1.filter_ports(symb="V"))
        assert len(ep)==1
        assert ep[0]==nineml.AnalogPort("V")

        # get all the event ports
        ep = list(c1.filter_ports(cls=nineml.EventPort))
        assert len(ep)==2
        assert nineml.SpikeInputEvent in ep
        assert nineml.SpikeOutputEvent in ep
        
        # get just the "recv" EventPort
        ep = list(c1.filter_ports(mode="recv", cls=nineml.EventPort))
        assert len(ep)==1
        assert ep[0]==nineml.SpikeInputEvent


        # check that Event catches condition in mode="send"
        self.assertRaises(ValueError, nineml.On,nineml.SpikeOutputEvent,do="V+=10" )
        # check that it won't accept a simple Port
        self.assertRaises(ValueError, nineml.On,nineml.Port("hello",mode="recv"),do="V+=10" )
        # check that it won't accept an AnalogPort
        self.assertRaises(ValueError, nineml.On,nineml.Port("hello",mode="recv"),do="V+=10" )

        # user defined EventPort should be ok.
        e = nineml.On(nineml.EventPort("hello",mode="recv"),do="V+=10" )

        
        r = nineml.Union(
            "_q10(V):=exp(V)",
            "dV/dt = 0.04*V*V + 5*V + 140.0 - U + Isyn",
            events = nineml.On(nineml.SpikeInputEvent,do="V+=10"))

        # ok to read from a binding, where function bindings are most interesting.
        c1 = nineml.Component("Izhikevich", regimes = [r], ports=[nineml.AnalogPort("_q10","send")] )
        # may not write to a binding
        self.assertRaises(ValueError,nineml.Component, "Izhikevich", regimes = [r], ports=[nineml.AnalogPort("_q10","recv")])

        # may not read from an undefined symbol
        self.assertRaises(ValueError,nineml.Component, "Izhikevich", regimes = [r], ports=[nineml.AnalogPort("_q11","send")])

        # Should be AnalogPort
        self.assertRaises(ValueError,nineml.Component, "Izhikevich", regimes = [r], ports=[nineml.Port("_q10","send")])

        # Should be AnalogPort
        self.assertRaises(ValueError,nineml.Component, "Izhikevich", regimes = [r], ports=[nineml.EventPort("_q10","send")])


        # EventPorts as nodes in Events

        # multiple EventPorts
        myeventport = nineml.EventPort('myeventport',mode="send")
        r = nineml.Union(
            "dV/dt = 0.04*V*V + 5*V + 140.0 - U + Isyn",
            events = nineml.On("V>Vth",do=[nineml.SpikeOutputEvent,myeventport ]))

        c1 = nineml.Component("Izhikevich", regimes = [r] )
        ep = list(c1.event_ports)
        assert len(ep)==2

        assert ep[0]==nineml.SpikeOutputEvent
        assert ep[1]==myeventport


        # ok
        e = nineml.On("V>Vth", do=nineml.EventPort("hello",mode="send"))
        # not ok: do=EventPort cannot recv
        self.assertRaises(ValueError, nineml.On, "V>Vth", do=nineml.EventPort("hello",mode="recv"))


    def test_trivial_conditions(self):
        """ Disallow trivial conditions """

        from nineml.abstraction_layer import cond_to_obj

        self.assertRaises(ValueError,cond_to_obj,"true")
        self.assertRaises(ValueError,cond_to_obj,"false")

        # undefined functions
        #self.assertRaises(ValueError, cond_to_obj,"U > WhatFunc(x)")

        
      
    def test_regime(self):

        for cls in (nineml.Union,nineml.Sequence):
            # no self-referencing Assignments in Regimes
            self.assertRaises(ValueError,cls,"U = U+1")

            # no self-referencing Inplace ops in Regime
            self.assertRaises(ValueError,cls,"U += 10")

        # no constructing from Regime base-class
        u = nineml.Union("dU/dt = -U")
        self.assertRaises(nineml.UnimplementedError,nineml.Regime,"dU/dt = -U")

        
        u = nineml.Union("dU/dt = -U")
        assert not list(u.events_with_target)

        u = nineml.Union("dU/dt = -U", events=[nineml.On("V>10",to="test")])
        assert list(u.events_with_target)

        u = nineml.Union("dU/dt = -U", events=[nineml.Event("U+=10",condition="U>10")])
        assert not list(u.events_with_target)

        u = nineml.Union("dU/dt = -U", events=[nineml.Event("U+=10",condition="U>10",to="test")])
        assert list(u.events_with_target)



    def test_event(self):

        t = nineml.Event(to=nineml.Reference(nineml.Regime,"test"), condition = "V>10")
        
        
    def test_event(self):

        e = nineml.Event("A+=10",condition="A>10")

        # Event must have condition (otherwise it is not temporally sparse
        self.assertRaises(ValueError, nineml.Event, "A+=10")

        # Event conditional may not be true or false
        # as the former violates temporal sparsesness,
        # the latter neuters the Event.
        self.assertRaises(ValueError, nineml.Event, "A+=10", condition="true")
        self.assertRaises(ValueError, nineml.Event, "A+=10", condition="false")

        # No ODEs in Events
        self.assertRaises(ValueError, nineml.Event, "dA/dt = -A", condition="A>10")

        e = nineml.Event("A+=10", condition="A>10", to="test")
        e = nineml.Event("A+=10", condition="A>10", to=None)
        e = nineml.Event("A+=10", condition="A>10", to=nineml.Reference(nineml.Regime,"test"))
        e = nineml.Event("A+=10", condition="A>10", to=nineml.Reference(nineml.Union,"test"))


        t = nineml.Event(to=nineml.Reference(nineml.Regime,"test"), condition = "V>10")
                
        self.assertRaises(ValueError, nineml.Event, "A+=10", condition="A>10", to=t)
        self.assertRaises(ValueError, nineml.Event, "A+=10", condition="A>10", to=nineml.Reference(nineml.Event,"test"))


    def test_component(self):
    
        r = nineml.Union(
            "_q10(V):=exp(V)",
            "dV/dt = 0.04*V*V + 5*V + 140.0 - U + Isyn",
            events = nineml.On(nineml.SpikeInputEvent,do="V+=10"))

        # ok to read from a binding, where function bindings are most interesting.
        c1 = nineml.Component("Izhikevich", regimes = [r], ports=[nineml.AnalogPort("_q10","send")] )

        



def suite():

    suite = unittest.makeSuite(ComponentTestCase,'test')
    return suite

if __name__ == "__main__":

    # unittest.main()
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
