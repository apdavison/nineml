import nineml.abstraction_layer as nineml


parameters = ["Isyn", "gL", "vL", "theta", "Vreset", "C", "trefractory"]


subthreshold_regime = nineml.Union(
                        "dV/dt = (-gL*(V-vL) + Isyn)/C",
                        name="subthreshold_regime"
                      )

refractory_regime = nineml.Union(
                        "V = Vreset",
                        name="refractory_regime"
                    )

spike_event = nineml.Event(
                        "tspike = t",
                        from_=subthreshold_regime,
                        to=refractory_regime,
                        condition="V > theta",
                        name="spike_transition"
                    )

subthreshold_event = nineml.Event(
                            from_=refractory_regime,
                            to=subthreshold_regime,
                            condition="t >= tspike + trefractory",
                            name="subthreshold_transition"
                          )

c1 = nineml.Component("LeakyIAF", parameters=parameters,
                             events=(spike_event, subthreshold_event))



# write to file object f if defined
try:
    # This case is used in the test suite for examples.
    c1.write(f)
except NameError:
    import os

    base = "leaky_iaf2"
    c1.write(base+".xml")
    c2 = nineml.parse(base+".xml")
    assert c1==c2

    c1.to_dot(base+".dot")
    os.system("dot -Tpng %s -o %s" % (base+".dot",base+".png"))
