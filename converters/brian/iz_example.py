import nineml.abstraction_layer as nineml
import nineml_stateupdater as brian9ml
from brian.stateupdater import NonlinearStateUpdater
import brian

regimes = [
    nineml.Union(
        "dV/dt = 0.04*V*V + 5*V + 140.0 - U + Isyn",
        "dU/dt = a*(b*V - U)",
        transitions = [nineml.On("V > theta",to="suprathreshold_regime")],
        name="subthreshold_regime"
    ),
    nineml.Union(
        "V = c",
        "U += d",
        transitions = [nineml.On("true",to="subthreshold_regime")],
        name="suprathreshold_regime"
    )]


c1 = nineml.Component("Izhikevich", parameters,
                             regimes = regimes )


model = brian9ml.NineMLStateUpdater(c1,regime_updater_cls=NonlinearStateUpdater,
                                    base_regime=regimes[0])

# Initial conditions
init = {'V': 0.0, 'U':0.0, 'Isyn':1.0}
t_init = [init.get(x,0.0) for x in model.state_vars]


# Threshold is 0.5 to detect a spike event on the spikeout var,
# which is 0.0 if no spike, 1.0 if spike on that clock tick.
# reset resets spikeout var to 0.0

P = NeuronGroup(10, model, init=t_init, threshold=0.5, reset=0.0)
