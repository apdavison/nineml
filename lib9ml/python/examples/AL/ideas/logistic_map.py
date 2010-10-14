from nineml.abstraction_layer import *

# Case study:
# The logistic map in 9ML

# This is NOT valid 9ML

# Why:
# - Need to allow events to go to Events
# - Need to allow from_=None

iteration = Event("x = r*x*(1.0-x)",
                  "n+=1",
                  to="log_map_iter",
                  name="log_map_iter")

ports = [SendPort("x"), SendPort("n")]

logistic_map = nineml.Component("Logistic Map", events = [iteration], ports = ports)
