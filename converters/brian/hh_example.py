import nineml.abstraction_layer as nineml
from brian import *
import brian.stdunits as units


# Sequence free hh model definition
hh = nineml.parse("hh.xml")

def component_to_native_brian(c):

    assert len(c.regime_map)==1, "brian supports 1 regime natively"

    # back substitute bindings which need bindings
    hh.backsub_bindings()
    # substitute bindings in equations
    hh.backsub_equations()

    eqns = []
    for e in hh.equations:
        # this fudges units
        eqn = '%s = (  %s  )/__time_factor__ : 1.' % (e.lhs,e.rhs,)
        eqns+=[eqn]
    return eqns
        
    
eqns = component_to_native_brian(hh)
for e in eqns:
    print e

# User parameters (lets get units spec'd!)
# Unitless hack
#dimless = units._units.Quantity(1.0)
area=20000*umetre**2

celsius = 6.3 # results in eqns in Gerstner & Kistler
el = -54.4 # mv
ek = -77.0 # mv
ena = 50.0 # mv

gl = 0.3*msiemens/cm**2
gl = gl*area/nS

gkbar = 36.0*msiemens/cm**2
gkbar = gkbar*area/nS

gnabar = 120.0*msiemens/cm**2
gnabar = gnabar*area/nS

C = 1.0*ufarad/cm**2
C = C*area/pfarad

Isyn = 20.0*uA/cm**2
Isyn = Isyn*area/pA
#Isyn = 0.0
__time_factor__ = 1.*ms

#c=brian.Clock(dt=.01*brian.ms)
defaultclock.dt = 0.1*ms
neuron=NeuronGroup(1,eqns,implicit=True,freeze=True, compile=False)
trace=StateMonitor(neuron,'V',record=True)

#run(100*ms)
#neuron.I=10*uA
run(100*ms)
plot(trace.times/ms,trace[0])
xlabel('t [ms]')
ylabel('V [mV]')
show()




# this is a hack until 9ml defines units,
# which defines the unit of time in Brian ODE
#__time_factor__ = 1.*units.ms

# Initial conditions
#init = {'V': 0.0, 'U':0.0, 'Isyn':1.0}
#t_init = [init.get(x,0.0) for x in model.state_vars]


# Threshold is 0.5 to detect a spike event on the spikeout var,
# which is 0.0 if no spike, 1.0 if spike on that clock tick.
# reset resets spikeout var to 0.0

#P = NeuronGroup(10, model, init=t_init, threshold=0.5, reset=0.0)
