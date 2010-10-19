
"""

Dynamic synaptic weight implementing phenomenological short term
depression and facilitation.

  Description:
  
   Implemented is the synapse model described in [2].  Which is the
   continuous ODE form of the iterative Eq (2) and Eq (3) in [1] or Eq
   (6) in [3], whereby Eq [2] in [1] seems to have an error in the
   subscript of u_{n+1}.  It should be u_{n}.

   The symbols used here (R,u,U,tau_rec,tau_facil) correspond to
   (R,U_se,U1,tau_rec,tau_facil) in [2].

   The model corresponds to the markram_synapse in NEST, which is a
   simplification of the NEST tsodyks_synapse (synaptic time course is
   neglected).

  References:
  
   [1] Markram, Wang, Tsodyks (1998) Differential Signaling via the same axon 
       of neocortical pyramidal neurons.  PNAS, vol 95, pp. 5323-5328.

   [2] Fuhrmann, Segev, Markram, Tsodyks (2002) Coding of Temporal
   Information by Activity-Dependent Synapses. J.Neurophysiol, vol 87, 140-148.

   [3] D. Sussillo, T. Toyoizumi, and W. Maass. Self-tuning of neural circuits through
   short-term synaptic plasticity. Journal of Neurophysiology, 97:4079-4095, 2007.

Author: Eilif Muller, 2010.

"""

import nineml.abstraction_layer as nineml


regimes = [
    nineml.Union(
        "dR/dt = (1-R)/tau_rec",
        "du/dt = -u/t_facil",
        events = nineml.On(nineml.SpikeInputEvent,
                           do=["W = u*R",
                               "R -= u*R",
                               "u += U*(1-u)"])
    )]

ports = [nineml.SendPort("W")]

c1 = nineml.Component("MarkramSynapseDynamics", regimes=regimes, ports = ports)

# write to file object f if defined
try:
    # This case is used in the test suite for examples.
    c1.write(f)
except NameError:
    import os

    base = "markram_synapse_dynamics"
    c1.write(base+".xml")
    c2 = parse(base+".xml")
    assert c1==c2

    #c1.to_dot(base+".dot")
    #os.system("dot -Tpng %s -o %s" % (base+".dot",base+".png"))


