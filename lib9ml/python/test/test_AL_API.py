
import unittest
import nineml.abstraction_layer as nineml

import os, tempfile




# regimes maynot have transition(condition=None)
# events : transition maynot have condition


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

        import nineml.abstraction_layer as nineml

        bindings = [
            "v1(x) := 1/v2(x+1,v3(x)+1) + v3(x)",
            "v2(x,y) := v3(x)*y + 10",
            "v3(x) := exp(x)**2"
            ]
        r = nineml.Union("dV/dt = 0.04*V*V + 5*V + 140.0 - U + Isyn + v1(v3(x))")


        c1 = nineml.Component("Izhikevich", regimes = [r], bindings=bindings )

        bm = c1.bindings_map
        assert bm['v1'].rhs == "1/((exp(x+1)**2)*(exp(x)**2)+1 + 10) + (exp(x)**2)"
        assert bm['v2'].rhs == "(exp(x)**2)*y + 10"
        assert bm['v3'].rhs == "exp(x)**2"


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
        assert not list(u.transitions_with_target)

        u = nineml.Union("dU/dt = -U", events=[nineml.On("V>10",to="test")])
        assert list(u.transitions_with_target)

        u = nineml.Union("dU/dt = -U", events=[nineml.Event("U+=10",condition="U>10")])
        assert not list(u.transitions_with_target)

        u = nineml.Union("dU/dt = -U", events=[nineml.Event("U+=10",condition="U>10",to="test")])
        assert list(u.transitions_with_target)



    def test_transition(self):

        t = nineml.Transition(to=nineml.Reference(nineml.Regime,"test"), condition = "V>10")
        
        
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


        t = nineml.Transition(to=nineml.Reference(nineml.Regime,"test"), condition = "V>10")
                
        self.assertRaises(ValueError, nineml.Event, "A+=10", condition="A>10", to=t)
        self.assertRaises(ValueError, nineml.Event, "A+=10", condition="A>10", to=nineml.Reference(nineml.Transition,"test"))


    def test_component(self):
        pass
        
        



def suite():

    suite = unittest.makeSuite(ComponentTestCase,'test')
    return suite

if __name__ == "__main__":

    # unittest.main()
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
