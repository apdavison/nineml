#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
.. module:: nineml_point_neurone_network
   :platform: Unix, Windows
   :synopsis: A useful module indeed.

.. moduleauthor:: Dragan Nikolic <dnikolic@incf.org>

"""

from __future__ import print_function
import os, sys, urllib, re, traceback, csv
from time import localtime, strftime
import numpy.random

import nineml
from nineml.abstraction_layer import readers
from nineml.abstraction_layer.testing_utils import TestableComponent

from daetools.pyDAE import pyCore, pyActivity, pyDataReporting, pyIDAS, daeLogs
from nineml_component_inspector import nineml_component_inspector
from nineml_daetools_bridge import nineml_daetools_bridge, ninemlRNG, findObjectInModel, fixObjectName, printComponent, daetools_spike_source
from nineml_tex_report import createLatexReport, createPDF
from nineml_daetools_simulation import daeSimulationInputData, nineml_daetools_simulation, ninemlTesterDataReporter, daetools_model_setup

def fixParametersDictionary(parameters):
    """
    :param parameters: ParameterSet object.
    
    :rtype: A dictionary made of the following key:value pairs: ``{'name' : (value, unit) }``.
    :raises: 
    """
    new_parameters = {}
    for name, parameter in list(parameters.items()):
        new_parameters[name] = (parameter.value, parameter.unit) 
    return new_parameters

def create_nineml_daetools_bridge(name, al_component, parent, description, rng, parameters):
    """
    Creates 'nineml_daetools_bridge' object for a given AbstractionLayer Component.
    There are some special cases which are handled individually such as:
     * SpikeSourcePoisson
    
    :param name: string
    :param al_component: AL Component object
    :param parent: daeModel derived object
    :param description: string
    :param rng: numpy.random.RandomState object
    
    :rtype: nineml_daetools_bridge object
    :raises: RuntimeError 
    """
    if al_component.name == 'SpikeSourcePoisson':
        if 'rate' in parameters:
            rate = float(parameters['rate'][0])
        else:
            raise RuntimeError('The SpikeSourcePoisson component: must have [rate] parameter')
        
        if 'duration' in parameters:
            duration = float(parameters['duration'][0])
        else:
            raise RuntimeError('The SpikeSourcePoisson component: must have [duration] parameter')
        
        if 't0' in parameters:
            t0 = float(parameters['t0'][0])
        else:
            t0 = 0.0

        lambda_ = rate * duration

        spiketimes = daetools_spike_source.createPoissonSpikeTimes(rate, duration, t0, rng, lambda_, rng)
        return daetools_spike_source(spiketimes, name, parent, description)
    
    else:
        return nineml_daetools_bridge(fixObjectName(name), al_component, parent, description)

def create_al_from_ul_component(ul_component, random_number_generators):
    """
    Creates AL component referenced in the given UL component and does some additional
    processing depending on its type. Returns the AL Component object. 
    It always checks if the url is valid and throws an exception if it ain't.
    
    Achtung!! Check if the component-data are needed at all.
    
    :param ul_component: UL Component object
    :param random_number_generators: python dictionary 'UL Component name' : ninemlRNG object (numpy RandomState based)
    
    :rtype: tuple (AL Component object, list component_data)
    :raises: RuntimeError 
    """
    
    # Getting an exception can occur for two reasons:
    #  1. The component at the specified URL does not exist
    #  2. The component exists but the parser cannot parse it
    try:
        # First check if the component exists; if not - raise an exception.
        f = urllib.urlopen(ul_component.definition.url)
    
    except Exception as e:
        raise RuntimeError('Cannot resolve the component: {0}, definition url: {1}, error: {2}'.format(ul_component.name, ul_component.definition.url, str(e)))
    
    try:
        # Try to load the component
        al_component = nineml.abstraction_layer.readers.XMLReader.read(ul_component.definition.url) 
        parameters   = fixParametersDictionary(ul_component.parameters)
    
    except Exception as e:
        raise RuntimeError('The component: {0} failed to parse: {1}'.format(ul_component.name, str(e)))

    # Do the additional processing, depending on the component's type.
    # Should be completed (if needed) in the future.
    try:
        if isinstance(ul_component, nineml.user_layer.ConnectionRule):
            pass
        
        elif isinstance(ul_component, nineml.user_layer.ConnectionType):
            pass
        
        elif isinstance(ul_component, nineml.user_layer.SpikingNodeType):
            pass
        
        elif isinstance(ul_component, nineml.user_layer.SynapseType):
            pass
        
        elif isinstance(ul_component, nineml.user_layer.CurrentSourceType):
            pass
        
        elif isinstance(ul_component, nineml.user_layer.Structure):
            pass
        
        elif isinstance(ul_component, nineml.user_layer.RandomDistribution):
            # Add a new RNG with the name of the UL component as a key
            # to the *random_number_generators* dictionary
            if not ul_component.name in random_number_generators:
                rng = ninemlRNG.create_rng(al_component, parameters)
                random_number_generators[ul_component.name] = rng
        
        else:
            RuntimeError('Unsupported UL Component type: {0}, component name: {1}'.format(type(ul_component), ul_component.name))
    
    except Exception as e:
        raise RuntimeError('The component: {0} failed to parse: {1}'.format(ul_component.name, str(e)))
    
    return (al_component, parameters)

class explicit_connections_generator_interface:
    """
    The simplest implementation of the ConnectionGenerator interface (Mikael Djurfeldt)
    built on top of the explicit list of connections.
    
    **Achtung, Achtung!** All indexes are zero-index based, for both source and target populations.
    """
    def __init__(self, connections):
        """
        Initializes the list of connections that the simulator can iterate on.
        
        :param connections: a list of tuples: (int, int) or (int, int, weight) or (int, int, weight, delay) or (int, int, weight, delay, parameters)
    
        :rtype:        
        :raises: RuntimeError 
        """
        if not connections or len(connections) == 0:
            raise RuntimeError('The connections argument is either None or an empty list')
        
        n_values = len(connections[0])
        if n_values < 2:
            raise RuntimeError('The number of items in each connection must be at least 2')
        
        for c in connections:
            if len(c) != n_values:
                raise RuntimeError('An invalid number of items in the connection: {0}; it should be {1}'.format(c, n_values))
        
        self._connections = connections
        self._current     = 0
    
    @property
    def size(self):
        """
        :rtype: Integer (the number of the connections).
        :raises: RuntimeError 
        """
        return len(self._connections)
        
    @property
    def arity(self):
        """
        Returns the number of values stored in an individual connection. It can be zero.
        The first two are always weight and delay; the rest are connection specific parameters.
        
        :rtype: Integer
        :raises: IndexError
        """
        return len(self._connections[0]) - 2
    
    def __iter__(self):
        """
        Initializes and returns the iterator.
        
        :rtype: explicit_connections_generator_interface object (self)
        :raises: 
        """
        self.start()
        return self
    
    def start(self):
        """
        Initializes the iterator.
        
        :rtype:
        :raises: 
        """
        self._current = 0
    
    def next(self):
        """
        Returns the connection and moves the counter to the next one.
        The connection is a tuple: (source_index, target_index, [zero or more floating point values])
        
        :rtype: tuple
        :raises: StopIteration (as required by the python iterator concept)
        """
        if self._current >= len(self._connections):
            raise StopIteration
        
        connection = self._connections[self._current]
        self._current += 1
        
        return connection

class daetools_point_neurone_network(pyCore.daeModel):
    """
    A top-level daetools model. All other models will be added to it (neurones, synapses):
     * Neurone names will be: model_name.population_name_Neurone(xxx)
     * Synapse names will be: model_name.projection_name_Synapsexxx(source_index,target_index)
    """
    def __init__(self, model):
        """
        :param model: UL Model object
        :raises: RuntimeError
        """
        name_ = fixObjectName(model.name)
        pyCore.daeModel.__init__(self, name_, None, '')
        
        self._name        = name_
        self._model       = model
        self._components  = {}
        self._groups      = {}
        self._rngs        = {}
        self._global_rng  = numpy.random.RandomState()
        
        for name, ul_component in list(model.components.items()):
            self._handleComponent(name, ul_component)
        
        for name, group in list(model.groups.items()):
            self._handleGroup(name, group)
        
    def __repr__(self):
        res = 'daetools_point_neurone_network({0})\n'.format(self._name)
        res += '  components:\n'
        for name, o in list(self._components.items()):
            res += '  {0} : {1}\n'.format(name, repr(o))
        res += '  groups:\n'
        for name, o in list(self._groups.items()):
            res += '  {0} : {1}\n'.format(name, repr(o))
        return res

    def getComponent(self, name):
        """
        :param name: string
        :rtype: AL Component object
        :raises: RuntimeError, IndexError
        """
        if not name in self._components:
            raise RuntimeError('Component [{0}] does not exist in the network'.format(name)) 
        return self._components[name][0]

    def getULComponent(self, name):
        """
        :param name: string
        :rtype: UL BaseComponent-derived object
        :raises: RuntimeError, IndexError
        """
        if not name in self._components:
            raise RuntimeError('Component [{0}] does not exist in the network'.format(name)) 
        return self._components[name][1]

    def getComponentParameters(self, name):
        """
        :param name: string
        :rtype: dictionary 'name':(value, unit)
        :raises: RuntimeError, IndexError
        """
        if not name in self._components:
            raise RuntimeError('Component [{0}] does not exist in the network'.format(name)) 
        return self._components[name][2]

    def getGroup(self, name):
        """
        :param name: string
        :rtype: daetools_group object
        :raises: RuntimeError
        """
        if not name in self._groups:
            raise RuntimeError('Group [{0}] does not exist in the network'.format(name)) 
        return self._groups[name]

    @property
    def randomNumberGenerators(self):
        return self._rngs
        
    @property
    def globalRandomNumberGenerator(self):
        return self._global_rng
        
    def DeclareEquations(self):
        """
        Does nothing.
        :rtype:
        :raises:
        """
        pass
    
    def _handleGroup(self, name, ul_group):
        """
        Handles UL Group object:
         * Resolves/creates AL components and their runtime parameters'/initial-conditions' values.
         * Creates populations of neurones and adds them to the 'neuronePopulations' dictionary
         * Creates projections and adds them to the 'projections' dictionary
        
        :param name: string
        :param ul_group: UL Group object
        
        :rtype:
        :raises: RuntimeError
        """
        group = daetools_group(name, ul_group, self) 
        self._groups[name] = group
    
    def _handleComponent(self, name, ul_component):
        """
        Resolves UL component and adds AL Component object to the list.
        :param name: string
        :param ul_component: UL BaseComponent-derived object
        
        :rtype:        
        :raises: RuntimeError
        """
        al_component, parameters = create_al_from_ul_component(ul_component, self._rngs) 
        self._components[name] = (al_component, ul_component, parameters)

class daetools_group:
    """
    """
    def __init__(self, name, ul_group, network):
        """
        :param name: string
        :param ul_group: UL Group object
        :param network: daetools_point_neurone_network object
        
        :rtype:
        :raises: RuntimeError
        """
        self._name        = fixObjectName(name)
        self._network     = network
        self._populations = {}
        self._projections = {}
        
        for name, ul_population in list(ul_group.populations.items()):
            self._handlePopulation(name, ul_population, network)
        
        for name, ul_projection in list(ul_group.projections.items()):
            self._handleProjection(name, ul_projection, network)
    
    def __repr__(self):
        res = 'daetools_group({0})\n'.format(self._name)
        res += '  populations:\n'
        for name, o in list(self._populations.items()):
            res += '  {0} : {1}\n'.format(name, repr(o))
        res += '  projections:\n'
        for name, o in list(self._projections.items()):
            res += '  {0} : {1}\n'.format(name, repr(o))
        return res

    def getPopulation(self, name):
        """
        :param name: string
        :rtype: daetools_population object
        :raises: RuntimeError
        """
        if not name in self._populations:
            raise RuntimeError('Population [{0}] does not exist in the group'.format(name)) 
        return self._populations[name]
        
    def getProjection(self, name):
        """
        :param name: string
        :rtype: daetools_projection object
        :raises: RuntimeError
        """
        if not name in self._projections:
            raise RuntimeError('Projection [{0}] does not exist in the group'.format(name)) 
        return self._projections[name]
    
    def _handlePopulation(self, name, ul_population, network):
        """
        Handles UL Population object:
         * Creates 'nineml_daetools_bridge' object for each neurone in the population
        
        :param name: string
        :param ul_population: UL Population object
        
        :rtype: None
        :raises: RuntimeError
        """
        population = daetools_population(name, ul_population, network) 
        self._populations[name] = population
    
    def _handleProjection(self, name, ul_projection, network):
        """
        Handles a NineML UserLayer Projection object:
         * Creates connections between a source and a target neurone via PSR component.
           PSR components are first transformed into the 'nineml_daetools_bridge' objects
        
        :param name: string
        :param ul_projection: UL Projection object
        
        :rtype:
        :raises: RuntimeError
        """
        projection = daetools_projection(name, ul_projection, self, network) 
        self._projections[name] = projection

class daetools_population:
    """
    """
    def __init__(self, name, ul_population, network):
        """
        :param name: string
        :param ul_population: UL Population object
        :param network: daetools_point_neurone_network object
        
        :rtype: 
        :raises: RuntimeError
        """
        self._name       = fixObjectName(name)
        self._network    = network
        self._neurones   = []
        self._positions  = []
        self._parameters = network.getComponentParameters(ul_population.prototype.name)
        al_component = network.getComponent(ul_population.prototype.name) 
        
        for i in range(0, ul_population.number):
            cell_name = '{0}_Neurone({1:0>4})'.format(self._name, i)
            neurone = create_nineml_daetools_bridge(cell_name, 
                                                    al_component, 
                                                    network, 
                                                    '', 
                                                    network.globalRandomNumberGenerator, 
                                                    self._parameters)
            self._neurones.append(neurone)
        
        try:
            self._positions = ul_population.positions.get_positions(ul_population)
        except Exception as e:
            print(str(e))
        
    def getNeurone(self, index):
        """
        :param name: integer
        :rtype: None
        :raises: IndexError
        """
        return self._neurones[int(index)]
    
    def __repr__(self):
        res = 'daetools_population({0})\n'.format(self._name)
        res += '  neurones:\n'
        for o in self._neurones:
            res += '  {0}\n'.format(repr(o))
        return res

class daetools_projection:
    """
    Data members:    
     * _name                  : string
     * _source_population     : daetools_population
     * _target_population     : daetools_population
     * _psr                   : AL Component
     * _connection_type       : AL Component
     * _connection_rule       : AL component
     * _generated_connections : list of ...
    """
    def __init__(self, name, ul_projection, group, network):
        """
        :param name: string
        :param ul_projection: UL Projection object
        :param group: daetools_group object
        :param network: daetools_point_neurone_network object
        
        :rtype:
        :raises: RuntimeError
        """
        self._name                  = fixObjectName(name)
        self._network               = network
        self._source_population     = group.getPopulation(ul_projection.source.name)
        self._target_population     = group.getPopulation(ul_projection.target.name)
        self._psr                   = network.getComponent(ul_projection.synaptic_response.name)
        self._psr_parameters        = network.getComponentParameters(ul_projection.synaptic_response.name)
        self._connection_rule       = network.getComponent(ul_projection.rule.name)
        self._connection_type       = network.getComponent(ul_projection.connection_type.name)
        self._generated_connections = []
        
        ul_connection_rule = network.getULComponent(ul_projection.rule.name)
        if hasattr(ul_connection_rule, 'connections'): # Explicit connections
            connections = getattr(ul_connection_rule, 'connections') 
            cgi = explicit_connections_generator_interface(connections)
            self._createConnections(cgi)
        
        else: # It should be the CSA component then
            self._handleConnectionRuleComponent(self._connection_rule)
        
    def __repr__(self):
        res = 'daetools_projection({0})\n'.format(self._name)
        res += '  source_population:\n'
        res += '    {0}\n'.format(self._source_population)
        res += '  target_population:\n'
        res += '    {0}\n'.format(self._target_population)
        res += '  psr:\n'
        res += '    {0}\n'.format(self._psr)
        res += '  connection_rule:\n'
        res += '    {0}\n'.format(self._connection_rule)
        res += '  connection_type:\n'
        res += '    {0}\n'.format(self._connection_type)
        return res

    def _handleConnectionRuleComponent(self, al_connection_rule):
        """
        :param al_connection_rule: AL Component object (CSA or other)
        
        :rtype: None
        :raises: RuntimeError
        """
        raise RuntimeError('Support for connection rule component not implemented yet')

    def _createConnections(self, cgi):
        """
        Iterates over ConnectionGeneratorInterface object and creates connections.
        Based on the connections, connects source->target neurones and (optionally) sets weights and delays
        
        :param cgi: ConnectionGeneratorInterface object
        
        :rtype: None
        :raises: RuntimeError
        """
        count        = 0
        connections  = []
        
        for connection in cgi:
            size = len(connection)
            if(size < 2):
                raise RuntimeError('Not enough data in the explicit lists of connections')
            
            source_index = int(connection[0])
            target_index = int(connection[1])
            weight       = 0.0
            delay        = 0.0
            parameters   = []
            
            if cgi.arity == 1:
                weight = float(connection[2])
            elif cgi.arity == 2:
                weight = float(connection[2])
                delay  = float(connection[3])
            elif cgi.arity >= 3:
                weight = float(connection[2])
                delay  = float(connection[3])
                for i in range(4, size):
                    parameters.append(float(connection[i]))           
            
            self._createConnection(source_index, target_index, weight, delay, parameters, count)
            connections.append( (source_index, target_index, weight, delay, parameters) )
            count += 1
        
        #for c in connections:
        #    print(c)

    def _createConnection(self, source_index, target_index, weight, delay, parameters, n):
        """
        Connects a source and a target neurone via PSR component.
        First it tries to obtain the source/target neurone objects from the corresponding populations, 
        then creates the nineml_daetools_bridge object for the synapse component and finally tries 
        to connect event ports between the source neurone and the synapse and analogue ports between
        the synapse and the target neurone. The source neurone, the synapse and the target neurone 
        are appended to the list of generated connections.
        
        :param source_index: integer; index in the source population
        :param target_index: integer; index in the target population
        :param weight: float
        :param delay: float
        :param n: number of connections in the projection (just to format the name of the synapse)
        
        :rtype: None
        :raises: RuntimeError
        """
        source_neurone = self._source_population.getNeurone(source_index)
        target_neurone = self._target_population.getNeurone(target_index)
        
        synapse_name   = '{0}_Synapse{1:0>4}({2:0>4},{3:0>4})'.format(self._name, n, int(source_index), int(target_index))
        synapse        = create_nineml_daetools_bridge(synapse_name, 
                                                       self._psr, 
                                                       self._network, 
                                                       '', 
                                                       self._network.globalRandomNumberGenerator,
                                                       self._psr_parameters)
        
        nineml_daetools_bridge.connectModelsViaEventPort    (source_neurone, synapse,        self._network)
        nineml_daetools_bridge.connectModelsViaAnaloguePorts(synapse,        target_neurone, self._network)
        
        self._generated_connections.append( (source_neurone, synapse, target_neurone) )

class nineml_daetools_network_simulation(pyActivity.daeSimulation):
    """
    """
    def __init__(self, network):
        """
        :rtype: None
        :raises: RuntimeError
        """
        pyActivity.daeSimulation.__init__(self)
        
        self.m            = network
        self.model_setups = []
        
        # What's this?
        event_ports_expressions = {"spikeinput": "0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90"} 
        
        random_number_generators = network.randomNumberGenerators
        
        for name, group in network._groups.items():
            # Setup neurones in populations
            for name, population in group._populations.items():
                for neurone in population._neurones:
                    initial_values = population._parameters
                    setup = daetools_model_setup(neurone, False, parameters               = initial_values, 
                                                                 initial_conditions       = initial_values,
                                                                 event_ports_expressions  = event_ports_expressions,
                                                                 random_number_generators = random_number_generators)
                    self.model_setups.append(setup)
        
            for name, projection in group._projections.items():
                # Setup synapses 
                initial_values = projection._psr_parameters
                for s, synapse, t in projection._generated_connections:
                    setup = daetools_model_setup(synapse, False, parameters               = initial_values, 
                                                                 initial_conditions       = initial_values,
                                                                 random_number_generators = random_number_generators)
                    self.model_setups.append(setup)

    def SetUpParametersAndDomains(self):
        """
        :rtype: None
        :raises: RuntimeError
        """
        for s in self.model_setups:
            s.SetUpParametersAndDomains()
        
    def SetUpVariables(self):
        """
        :rtype: None
        :raises: RuntimeError
        """
        for s in self.model_setups:
            s.SetUpVariables()

def readCSV_pyNN(filename):
    """
    Reads pyNN .conn files and returns a list of connections: [(int, int, float, float), ...]
    """
    connections_out = []
    connections = list(csv.reader(open(filename, 'rb'), delimiter='\t'))
    for connection in connections:
        s = int(float(connection[0]))
        t = int(float(connection[1]))
        w = float(connection[2])
        d = float(connection[3])
        connections_out.append((s, t, w, d))
    return connections_out
    
if __name__ == "__main__":
    catalog = "file:///home/ciroki/Data/NineML/nineml-model-tree/lib9ml/python/dae_impl/"

    rnd_uniform = {
                    'lowerBound': (-0.060, "dimensionless"),
                    'upperBound': (-0.040, "dimensionless")
                  }
    uniform_distribution = nineml.user_layer.RandomDistribution("uniform(-0.060, -0.040)", catalog + "uniform_distribution.xml", rnd_uniform)
    
    poisson_params = {
                       'rate'     : (100.00, 'Hz'),
                       'duration' : (  0.05, 's'),
                       't0'       : (  0.00, 's')
                     }
    
    neurone_params = {
                       'tspike' :    ( -1.000, 's'),
                       'V' :         (uniform_distribution, 'V'),
                       'gl' :        ( 1.0E-8, 'S'),
                       'vreset' :    ( -0.060, 'V'),
                       'taurefrac' : (  0.001, 's'),
                       'vthresh' :   ( -0.040, 'V'),
                       'vrest' :     ( -0.060, 'V'),
                       'cm' :        ( 0.2E-9, 'F')
                     }
    
    psr_poisson_params = {
                           'vrev' : (   0.000, 'V'),
                           'q'    : (100.0E-9, 'S'),
                           'tau'  : (   0.005, 's'),
                           'g'    : (   0.000, 'S')
                         }

    psr_excitatory_params = {
                             'vrev' : (  0.000, 'V'),
                             'q'    : ( 4.0E-9, 'S'),
                             'tau'  : (  0.005, 's'),
                             'g'    : (  0.000, 'S')
                            }
                     
    psr_inhibitory_params = {
                             'vrev' : ( -0.080, 'V'),
                             'q'    : (51.0E-9, 'S'),
                             'tau'  : (  0.010, 's'),
                             'g'    : (  0.000, 'S')
                            }
    
    neurone_IAF     = nineml.user_layer.SpikingNodeType("IAF neurones", catalog + "iaf.xml", neurone_params)
    
    neurone_poisson = nineml.user_layer.SpikingNodeType("Poisson Source", catalog + "spike_source_poisson.xml", poisson_params)
    
    psr_poisson     = nineml.user_layer.SynapseType("COBA poisson",    catalog + "coba_synapse.xml", psr_poisson_params)
    psr_excitatory  = nineml.user_layer.SynapseType("COBA excitatory", catalog + "coba_synapse.xml", psr_excitatory_params)
    psr_inhibitory  = nineml.user_layer.SynapseType("COBA inhibitory", catalog + "coba_synapse.xml", psr_inhibitory_params)
    
    grid2D          = nineml.user_layer.Structure("2D grid", catalog + "2Dgrid.xml")
    connection_type = nineml.user_layer.ConnectionType("Static weights and delays", catalog + "static_weights_delays.xml")
    
    population_excitatory = nineml.user_layer.Population("Excitatory population", 80, neurone_IAF,     nineml.user_layer.PositionList(structure=grid2D))
    population_inhibitory = nineml.user_layer.Population("Inhibitory population", 20, neurone_IAF,     nineml.user_layer.PositionList(structure=grid2D))
    population_poisson    = nineml.user_layer.Population("Poisson population",    20, neurone_poisson, nineml.user_layer.PositionList(structure=grid2D))

    connections_exc_exc     = readCSV_pyNN('e2e.conn')
    connections_exc_inh     = readCSV_pyNN('e2i.conn')
    connections_inh_inh     = readCSV_pyNN('i2i.conn')
    connections_inh_exc     = readCSV_pyNN('i2e.conn')
    connections_poisson_exc = readCSV_pyNN('ext2e.conn')
    connections_poisson_inh = readCSV_pyNN('ext2i.conn')
    #print(connections_exc_exc)
    #print(connections_exc_inh)
    #print(connections_inh_inh)
    #print(connections_inh_exc)
    #print(connections_poisson_exc)
    #print(connections_poisson_inh)
    
    connection_rule_exc_exc     = nineml.user_layer.ConnectionRule("Explicit Connections exc_exc", catalog + "explicit_list_of_connections.xml")
    connection_rule_exc_inh     = nineml.user_layer.ConnectionRule("Explicit Connections exc_inh", catalog + "explicit_list_of_connections.xml")
    connection_rule_inh_inh     = nineml.user_layer.ConnectionRule("Explicit Connections inh_inh", catalog + "explicit_list_of_connections.xml")
    connection_rule_inh_exc     = nineml.user_layer.ConnectionRule("Explicit Connections inh_exc", catalog + "explicit_list_of_connections.xml")
    connection_rule_poisson_exc = nineml.user_layer.ConnectionRule("Explicit Connections poisson_exc", catalog + "explicit_list_of_connections.xml")
    connection_rule_poisson_inh = nineml.user_layer.ConnectionRule("Explicit Connections poisson_inh", catalog + "explicit_list_of_connections.xml")

    setattr(connection_rule_exc_exc,     'connections', connections_exc_exc)
    setattr(connection_rule_exc_inh,     'connections', connections_exc_inh)
    setattr(connection_rule_inh_inh,     'connections', connections_inh_inh)
    setattr(connection_rule_inh_exc,     'connections', connections_inh_exc)
    setattr(connection_rule_poisson_exc, 'connections', connections_poisson_exc)
    setattr(connection_rule_poisson_inh, 'connections', connections_poisson_inh)

    projection_exc_exc     = nineml.user_layer.Projection("Projection exc_exc",     population_excitatory, population_excitatory, connection_rule_exc_exc,     psr_excitatory, connection_type)
    projection_exc_inh     = nineml.user_layer.Projection("Projection exc_inh",     population_excitatory, population_inhibitory, connection_rule_exc_inh,     psr_excitatory, connection_type)
    projection_inh_inh     = nineml.user_layer.Projection("Projection inh_inh",     population_inhibitory, population_inhibitory, connection_rule_inh_inh,     psr_inhibitory, connection_type)
    projection_inh_exc     = nineml.user_layer.Projection("Projection inh_exc",     population_inhibitory, population_excitatory, connection_rule_inh_exc,     psr_inhibitory, connection_type)
    projection_poisson_exc = nineml.user_layer.Projection("Projection poisson_exc", population_poisson,    population_excitatory, connection_rule_poisson_exc, psr_poisson,    connection_type)
    projection_poisson_inh = nineml.user_layer.Projection("Projection poisson_inh", population_poisson,    population_inhibitory, connection_rule_poisson_inh, psr_poisson,    connection_type)

    # Add everything to a single group
    group = nineml.user_layer.Group("Group 1")
    
    # Add populations
    group.add(population_poisson)
    group.add(population_excitatory)
    group.add(population_inhibitory)
    
    # Add projections
    group.add(projection_poisson_exc)
    group.add(projection_poisson_inh)
    group.add(projection_exc_exc)
    group.add(projection_exc_inh)
    group.add(projection_inh_inh)
    group.add(projection_inh_exc)

    # Create a network and add the group to it
    model = nineml.user_layer.Model("Simple 9ML example model")
    model.add_group(group)
    model.write("Brette et al., J. Computational Neuroscience (2007).xml")
    
    network = daetools_point_neurone_network(model)

    # Create Log, Solver, DataReporter and Simulation object
    from daetools.solvers import pySuperLU

    log          = daeLogs.daePythonStdOutLog()
    daesolver    = pyIDAS.daeIDAS()
    datareporter = pyDataReporting.daeTCPIPDataReporter()
    simulation   = nineml_daetools_network_simulation(network)
    
    lasolver     = pySuperLU.daeCreateSuperLUSolver()
    daesolver.SetLASolver(lasolver)

    # Set the time horizon and the reporting interval
    simulation.ReportingInterval = 0.01
    simulation.TimeHorizon       = 1.0

    # Connect data reporter
    simName = simulation.m.Name + strftime(" [%d.%m.%Y %H:%M:%S]", localtime())
    if(datareporter.Connect("", simName) == False):
        sys.exit()

    # Initialize the simulation
    simulation.Initialize(daesolver, datareporter, log)

    # Solve at time=0 (initialization)
    simulation.SolveInitial()

    # Run
    simulation.Run()
    simulation.Finalize()
