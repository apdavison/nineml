
import unittest
import nineml.abstraction_layer as nineml
from nineml.abstraction_layer.expr_parse import expr_parse, NineMLMathParseError, call_expr_func
import numpy

import os, tempfile

# [expr, vars, functions]
expr_vars = [["-A/tau_r", ("A","tau_r"),()],
             ["V*V", ("V",),()],
             ["a*(b*V - U)", ("U","V","b","a"),()],
             [" 0.04*V*V + 5.0*V + 1. + 140.0 - U + Isyn", ("V","U","Isyn"),()],
             ["c",("c"),()],
             ["1",(),()],
             ["atan2(sin(x),cos(y))",("x","y"),("atan2","sin","cos")],
             ["1.*V",("V"),()],
             ["1.0",(),()],
             [".1",(),()],
             ["1/(1 + mg_conc*eta*exp(-1*gamma*V))", ("mg_conc","eta","gamma","V"),('exp',)],
             ["1 / ( 1 + mg_conc * eta *  exp( -1 * gamma*V))", ("mg_conc","eta","gamma","V"),('exp',)],
             ["1 / ( 1 + mg_conc * sin(0.5) *  exp ( -1 * gamma*V))", ("mg_conc","gamma","V"),('exp',"sin")],
             [".1 / ( 1.0 + mg_conc * sin(V) *  exp ( -1.0 * gamma*V))", ("mg_conc","gamma","V"),('exp',"sin")],
             ["sin(w)",("w"),("sin",)]]


namespace = {
    "A": 10.0,
    "tau_r": 11.0,
    "V":-70.0,
    "a": 1.2,
    "b": 3.0,
    "U": -80.0,
    "Isyn": 2.0,
    "c": 10.0,
    "mg_conc":1.0,
    "eta":2.0,
    "gamma":-20.0,
    "x":1.0,
    "y":1.0,
    "w":numpy.arange(10)
    }

return_values = [-0.909090909091, 4900.0,-156.0,69.0,10.0,1,1.0,-70.0,1.0,0.1,1.0,1.0,1.0,0.1, numpy.sin(namespace['w'])]



class ExprParseTestCase(unittest.TestCase):

    def test_unmatchedparenthesis(self):

        self.assertRaises(NineMLMathParseError, expr_parse, "1 / (( 1 + mg_conc * eta *  exp ( -1 * gamma*V))")

        self.assertRaises(NineMLMathParseError, expr_parse, "1 / ( 1 + mg_conc * eta *  exp ( -1 * gamma*V)))")

        self.assertRaises(NineMLMathParseError, expr_parse, "1 / ( 1 + mg_conc * eta *  exp (( -1 * gamma*V))")

        self.assertRaises(NineMLMathParseError, expr_parse, "1..0")

        self.assertRaises(NineMLMathParseError, expr_parse, "..0")


    def test_unknownfunc(self):

        self.assertRaises(NineMLMathParseError, expr_parse, "WhatFunc(x)")
        

        
    def test_getvf(self):
        """Test that we can get vars and funcs out"""
        for i,e in enumerate(expr_vars):

            vars, funcs, python_func = expr_parse(e[0])
            assert set(vars)==set(e[1])
            assert set(funcs)==set(e[2])

            r = call_expr_func(python_func,namespace)
            assert numpy.allclose(r,return_values[i])




def suite():

    suite = unittest.makeSuite(ExprParseTestCase,'test')
    return suite

if __name__ == "__main__":

    # unittest.main()
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
