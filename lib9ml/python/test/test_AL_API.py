
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
