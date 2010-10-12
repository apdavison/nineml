"""
Script for generating a single-compartment Hodgkin-Huxley cell in NineML XML format.

Andrew Davison, 2010
"""

from nineml.abstraction_layer import *
import os

q10_binding = Binding("q10",  "3**((celsius - 6.3)/10)")

sodium_state_update = Union(
    "alpha_m(V) := -0.1*(V+40)/(exp(-(V+40)/10) - 1)",
    "beta_m(V) := 4*exp(-(V+65)/18)",
    "mtau(V) := 1/(q10*(alpha_m(V) + beta_m(V)))",
    "minf(V) := alpha_m(V)/(alpha_m(V) + beta_m(V))",
    "alpha_h(V) := 0.07*exp(-(V+65)/20)",
    "beta_h(V) := 1/(exp(-(V+35)/10) + 1)",
    "htau(V) := 1/(q10*(alpha_h(V) + beta_h(V)))",
    "hinf(V) := alpha_h(V)/(alpha_h(V) + beta_h(V))",
    "dm/dt = (minf(V)-m)/mtau(V)",
    "dh/dt = (hinf(V)-h)/htau(V)",
    name="sodium_state_update"
)

potassium_state_update = Union(
    "alpha_n(V) := -0.01*(V+55)/(exp(-(V+55)/10) - 1)",
    "beta_n(V) := 0.125*exp(-(V+65)/80)",
    "ntau(V) := 1/(q10*(alpha_n(V) + beta_n(V)))",
    "ninf(V) := alpha_n(V)/(alpha_n(V) + beta_n(V))",
    "dn/dt = (ninf(V)-n)/ntau(V)",
    name="potassium_state_update"
)

state_updates = Union(sodium_state_update,
                      potassium_state_update,
                      name="state_updates")

current_calculation = Union(
    "gna(m,h) := gnabar*m*m*m*h",
    "gk(n) := gkbar*n*n*n*n",
    "ina = gna(V,m,h)*(V - ena)",
    "ik = gk(n)*(V - ek)",
    "il = gl*(V - el)",
    name="current_calculation"
)

hh_regime = Union( # or Union? do we solve for m,h,n first then V, or all together?
    state_updates,
    current_calculation,
    "dV/dt = (ina + ik + il + Isyn)/C",
    name="hh_regime",
    events=[On("V > theta",do=["tspike=t"])]
)





#input_variables = ["Isyn", "t"]
#state_variables = ["m", "h", "n", "V"]
#fixed_parameters = ["C", "gnabar", "gkbar", "gl", "ena", "ek", "el", "celsius", "theta"]
#assigned_variables = ["q10", "alpha_m", "beta_m", "alpha_h", "beta_h",
#                      "alpha_n", "beta_n", "gna", "gk", "tspike"]
#parameters = input_variables + state_variables + fixed_parameters + assigned_variables

parameters = ['el', 'C', 'ek', 'ena', 'Isyn', 'gkbar', 'gnabar', 'theta', 'gl','celsius']

c1 = Component("Hodgkin-Huxley", parameters=parameters,
                      regimes=(hh_regime,),
                      bindings=[q10_binding])

# write to file object f if defined
try:
    # This case is used in the test suite for examples.
    c1.write(f)
except NameError:

    base = "hh2"
    c1.write(base+".xml")
    c2 = parse(base+".xml")
    assert c1==c2

    c1.to_dot(base+".dot")
    os.system("dot -Tpng %s -o %s" % (base+".dot",base+".png"))
