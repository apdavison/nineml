
import unittest
import nineml.abstraction_layer as nineml
from nineml.abstraction_layer.expressions import *
from nineml.abstraction_layer.conditions import *

import os, tempfile

class ExpressionsTestCase(unittest.TestCase):

    def test_prefixing(self):

        # TODO: These test cases aren't hard enough ... 

        c = Condition("x>10 & pi < 3 & exp(pi,y)==1")
        pfx_c = c.prefix("PRE_")
        assert pfx_c == "PRE_x>10 & pi < 3 & exp(pi,PRE_y)==1"

        b = Binding("ntau(V)","1/(q10*(alpha_n(V) + beta_n(V)))")
        pfx_b = b.prefix("PRE_")
        assert pfx_b == "PRE_ntau(V) := 1/(PRE_q10*(PRE_alpha_n(V) + PRE_beta_n(V)))"

        ode = ODE("V","t","(ina + ik + il + Isyn)/C")
        pfx_ode = ode.prefix("PRE_")
        assert pfx_ode == "dPRE_V/dt = (PRE_ina + PRE_ik + PRE_il + PRE_Isyn)/PRE_C"

        a = Assignment("U","gk(n)*(V - ek)")
        pfx_a = a.prefix("PRE_")
        assert pfx_a == "PRE_U = PRE_gk(PRE_n)*(PRE_V - PRE_ek)"

        i = Inplace("U","+=", "gk(n)*(V - ek)")
        pfx_i = i.prefix("PRE_")
        assert pfx_i == "PRE_U += PRE_gk(PRE_n)*(PRE_V - PRE_ek)"


def suite():

    suite = unittest.makeSuite(ExpressionsTestCase,'test')
    return suite

if __name__ == "__main__":

    # unittest.main()
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
