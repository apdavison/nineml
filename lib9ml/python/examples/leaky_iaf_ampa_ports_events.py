# A leaky_iaf which defines ports to play with an ampa synapse
import nineml.abstraction_layer as nineml


threshold_event = nineml.Event(
    "tspike = t",
    "V = Vreset",
    nineml.SpikeOutputEvent,
    condition = "V>Vth"
    transition = "refractory-regime"
    )


# Leaky iaf
regimes = [
    nineml.Sequence(
    "dV/dt = (-gL*(V-vL) + Isyn)/C",
    events = [threshold_event],
    name = "sub-threshold-regime"
    ),

    nineml.Union(
    events = [nineml.Event(condition="t >= tspike + trefractory",transition="sub-threshold-regime")],
    name = "refractory-regime"
    )]


ports = [nineml.Port("V"),
         nineml.ReducePort("Isyn",op="+")]

c1 = nineml.Component("LeakyIAF", regimes = regimes, ports = ports)

