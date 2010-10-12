import nineml.abstraction_layer as nineml


parameters = ["Isyn", "a", "b", "c", "d", "theta"]

subthreshold_regime = nineml.Union(
    "dV/dt = 0.04*V*V + 5*V + 140.0 - U + Isyn",
    "dU/dt = a*(b*V - U)",
    name="subthreshold_regime"
    )

spike_event = nineml.Event(
    "V = c",
    "U += d",
    from_=subthreshold_regime,
    condition="V > theta",
    name="spike_event"
    )

c1 = nineml.Component("Izhikevich", parameters = parameters,
                             events=(spike_event,))


# write to file object f if defined
try:
    # This case is used in the test suite for examples.
    c1.write(f)
except NameError:
    import os

    base = "izhikevich"
    c1.write(base+".xml")
    c2 = nineml.parse(base+".xml")
    assert c1==c2

    c1.to_dot(base+".dot")
    os.system("dot -Tpng %s -o %s" % (base+".dot",base+".png"))

