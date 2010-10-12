from nineml.abstraction_layer import *
 

inter_event_regime = Union(
    "tau_peak := tau_r*tau_d/(tau_d - tau_r)*log(tau_d/tau_r)",
    "factor := 1/(exp(-tau_peak/tau_d) - exp(-tau_peak/tau_r))",
    "gB(V) := 1/(1 + mg_conc*eta*exp(-1*gamma*V))",
    "dA/dt = -A/tau_r",
    "dB/dt = -B/tau_d",
    "g = gB(V)*gmax*(B-A)",
    name="inter_event_regime",
    events=[On("SpikeInputEvent == 1.0",
                    do=["A = A + weight*factor",
                        "B = B + weight*factor"])]
    )

 
# Parameters

external_parameters =  ["tau_r", "tau_d", "mg_conc", "eta", "gamma", "gmax"]
variables_from_elsewhere = ["V", "weight", "SpikeInputEvent"]
state_variables = ["g", "A", "B"]
bindings = ["tau_peak", "factor"]

parameters = external_parameters + variables_from_elsewhere


c1 = Component("NMDA_PSR", parameters = parameters, regimes=[inter_event_regime])


# write to file object f if defined
try:
    # This case is used in the test suite for examples.
    c1.write(f)
except NameError:
    import os

    base = "nmda"
    c1.write(base+".xml")
    c2 = parse(base+".xml")
    assert c1==c2

    c1.to_dot(base+".dot")
    os.system("dot -Tpng %s -o %s" % (base+".dot",base+".png"))
