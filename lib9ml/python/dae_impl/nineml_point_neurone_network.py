#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import os, sys, urllib, re
from time import localtime, strftime

import nineml
from nineml.abstraction_layer import readers
from nineml.abstraction_layer.testing_utils import TestableComponent

from daetools.pyDAE import pyCore, pyActivity, pyDataReporting, pyIDAS, daeLogs
from nineml_component_inspector import nineml_component_inspector
from nineml_daetools_bridge import nineml_daetools_bridge, findObjectInModel, fixObjectName
from nineml_tex_report import createLatexReport, createPDF
from nineml_daetools_simulation import daeSimulationInputData, nineml_daetools_simulation, ninemlTesterDataReporter, daetools_model_setup

def fixParametersDictionary(parameters):
    """
    Returns a dictionary made of the following key:value pairs: { 'name' : (value, unit) }  
      - parameters: ParameterSet object
    """
    new_parameters = {}
    for name, parameter in list(parameters.items()):
        new_parameters[name] = (parameter.value, parameter.unit) 
    return new_parameters

def create_nineml_daetools_bridge(name, al_component, parent = None, description = ''):
    """
    Creates 'nineml_daetools_bridge' object for a given AbstractionLayer Component
    """
    return nineml_daetools_bridge(fixObjectName(name), al_component, parent, description)

def create_al_from_ul_component(ul_component):
    """
    Creates AL component referenced in the given UL component.
    Returns the AL Component object. If the url does not point to the xml file with AL components
    (for instance it is an explicit connections file) - the function returns None.
    This is a case when loading ExplicitConnections rule or the url cannot be resolved.
    However, the function always checks if the url is valid and throws an exception if it ain't.
    """
    try:
        al_component = None
        al_component = nineml.abstraction_layer.readers.XMLReader.read(ul_component.definition.url) 
    
    except Exception as e:
        # Getting an exception does not necessarily mean something bad. It will always happen if 
        # the component is a component with explicit connections which is not a valid xml file. 
        # Therefore, we try to see if the url is valid; if not - a death is imminent
        # and an exception will be thrown.
        f = urllib.urlopen(ul_component.definition.url)

    return al_component

class explicit_connections_generator_interface:
    """
    The simplest implementation of the ConnectionGenerator interface (NEST) 
    built on top of the explicit list of connections.
    """
    def __init__(self, connections):
        """
        Iniializes the list of connections that the simulator can iterate on.
        """
        self._connections = connections
        self._current     = 0
    
    @property
    def size(self):
        """
        Returns the number of the connections.
        """
        return len(self._connections)
        
    @property
    def arity(self):
        """
        Returns the number of values stored in an individual connection.
        """
        if len(self._connections) == 0:
            return 0
        else:
            return len(self._connections[0])
    
    def __iter__(self):
        """
        Initializes the counter and returns the iterator.
        """
        self.start()
        return self
    
    def start(self):
        """
        Initializes the iterator.
        """
        self._current = 0
    
    def next(self):
        """
        Returns the current connection and moves the counter to the next one.
        """
        if self._current >= len(self._connections):
            raise StopIteration
        
        connection = self._connections[self._current]
        self._current += 1
        
        return connection
        
class daetools_point_neurone_network(pyCore.daeModel):
    """
    A top-level daetools model. All other models will be added to it (neurones, synapses):
     - Neurone names will be: model_name.population_name_Neurone(xxx)
     - Synapse names will be: model_name.projection_name_Synapsexxx(source_index,target_index)
    """
    def __init__(self, model):
        """
        """
        name_ = fixObjectName(model.name)
        pyCore.daeModel.__init__(self, name_, None, '')
        
        self._name        = name_
        self._model       = model
        self._components  = {}
        self._groups      = {}
        
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
        if not name in self._components:
            raise RuntimeError('Component [{0}] does not exist in the network'.format(name)) 
        return self._components[name][0]

    def getComponentURL(self, name):
        if not name in self._components:
            raise RuntimeError('Component [{0}] does not exist in the network'.format(name)) 
        return self._components[name][1].definition.url
    
    def getComponentParameters(self, name):
        if not name in self._components:
            raise RuntimeError('Component [{0}] does not exist in the network'.format(name)) 
        return self._components[name][1].parameters

    def getGroup(self, name):
        if not name in self._groups:
            raise RuntimeError('Group [{0}] does not exist in the network'.format(name)) 
        return self._groups[name]

    def DeclareEquations(self):
        pass
    
    def _handleGroup(self, name, ul_group):
        """
        Handles a NineML UserLayer Group object:
         - Resolves/creates AL components and their runtime parameters'/initial-conditions' values.
         - Creates populations of neurones and adds them to the 'neuronePopulations' dictionary
         - Creates projections and adds them to the 'projections' dictionary
        Arguments:
         - name: string
         - ul_group: UL Group object
        """
        group = daetools_group(name, ul_group, self) 
        self._groups[name] = group
    
    def _handleComponent(self, name, ul_component):
        """
        Resolves UL component and returns AL component
        Arguments:
         - name: string
         - ul_component: UL BaseComponent-derived object
        """
        al_component = create_al_from_ul_component(ul_component) 
        self._components[name] = (al_component, ul_component)

class daetools_group:
    """
    """
    def __init__(self, name, ul_group, network):
        """
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
        if not name in self._populations:
            raise RuntimeError('Population [{0}] does not exist in the group'.format(name)) 
        return self._populations[name]
        
    def getProjection(self, name):
        if not name in self._projections:
            raise RuntimeError('Projection [{0}] does not exist in the group'.format(name)) 
        return self._projections[name]
    
    def _handlePopulation(self, name, ul_population, network):
        """
        Handles a NineML UserLayer Population object:
         - Creates 'nineml_daetools_bridge' object for each neurone in the population
        Arguments:
         - name: string
         - ul_population: UL Population object
        """
        population = daetools_population(name, ul_population, network) 
        self._populations[name] = population
    
    def _handleProjection(self, name, ul_projection, network):
        """
        Handles a NineML UserLayer Projection object:
         - Creates connections between a source and a target neurone via PSR component.
           PSR components are first transformed into the 'nineml_daetools_bridge' objects
        Arguments:
         - name: string
         - ul_projection: UL Projection object
        """
        projection = daetools_projection(name, ul_projection, self, network) 
        self._projections[name] = projection

class daetools_population:
    """
    """
    def __init__(self, name, ul_population, network):
        """
        Arguments:
         - name: string
         - ul_population: UL Population object
         - network: daetools_point_neurone_network object
        """
        self._name       = fixObjectName(name)
        self._network    = network
        self._parameters = fixParametersDictionary(ul_population.prototype.parameters)
        self._neurones   = []
        self._positions  = []
        
        # Get the AL component from the network
        al_component = network.getComponent(ul_population.prototype.name) 
        
        for i in range(0, ul_population.number):
            neurone = create_nineml_daetools_bridge('{0}_Neurone({1})'.format(self._name, i), al_component, network, '')
            self._neurones.append(neurone)
        
        try:
            self._positions = ul_population.positions.get_positions(ul_population)
        except Exception as e:
            print(str(e))
        
    def getNeurone(self, index):
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
      _name                  : string
      _source_population     : daetools_population
      _target_population     : daetools_population
      _psr                   : AL Component
      _connection_type       : AL Component
      _generated_connections : 
    """
    def __init__(self, name, ul_projection, group, network):
        """
        Arguments:
         - name: string
         - ul_projection: UL Projection object
         - group: daetools_group object
         - network: daetools_point_neurone_network object
        """
        self._name                  = fixObjectName(name)
        self._network               = network
        self._source_population     = group.getPopulation(ul_projection.source.name)
        self._target_population     = group.getPopulation(ul_projection.target.name)
        self._psr                   = network.getComponent(ul_projection.synaptic_response.name)
        self._psr_parameters        = fixParametersDictionary(ul_projection.synaptic_response.parameters)
        self._connection_type       = network.getComponent(ul_projection.connection_type.name)
        self._generated_connections = []
        
        al_connection_rule_component = network.getComponent(ul_projection.rule.name)
        if al_connection_rule_component: # CSA
            self._handleConnectionRuleComponent(al_connection_rule_component)
        
        else: # explicit connections
            explicit_connections_file = network.getComponentURL(ul_projection.rule.name)
            self._handleExplicitConnections(explicit_connections_file)
        
    def __repr__(self):
        res = 'daetools_projection({0})\n'.format(self._name)
        res += '  source_population:\n'
        res += '    {0}\n'.format(self._source_population)
        res += '  target_population:\n'
        res += '    {0}\n'.format(self._target_population)
        res += '  psr:\n'
        res += '    {0}\n'.format(self._psr)
        #res += '  connection_rule:\n'
        #res += '    {0}\n'.format(self._connection_rule)
        res += '  connection_type:\n'
        res += '    {0}\n'.format(self._connection_type)
        return res

    def _handleConnectionRuleComponent(self, al_connection_rule):
        """
        Arguments:
         - al_connection_rule: AL Component object (CSA or other)
        """
        raise RuntimeError('Support for connection rule component not implemented yet')

    def _handleExplicitConnections(self, url):
        """
        Creates connections based on the file with explicit connections (argument 'url'). 
         - Opens and parses the file with explicit connections.
           The file is a space-delimited text file in the format: source target [weight delay parameter1 parameter2 ...]
           Weight, delay and parameters are optional.
         - Based on the connections connects source->target neurones and (optionally) sets weights and delays
        Arguments:
         - url: URL of the external file with explicit connections
        """
        connections = []
        f = urllib.urlopen(url)
        
        source_index = -1
        target_index = -1
        weight       = 0.0
        delay        = 0.0
        parameters   = []
        conn_count   = 0
        
        scan = re.compile(' ')
        for line in f.readlines():
            items = scan.split(line)
            
            size = len(items)
            if(size < 2):
                raise RuntimeError('Not enough data in the explicit connections file: {0}'.format(url))
            
            source_index = int(items[0])
            target_index = int(items[1])
            
            if size >= 3:
                weight = float(items[2])
            else:
                weight = 0.0
            
            if size >= 4:
                delay = float(items[3])
            else:
                delay = 0.0
            
            connections.append( (source_index, target_index, weight, delay) )
            self._createConnection(source_index, target_index, weight, delay, conn_count)
            conn_count += 1
        
        print(connections)
        #print(self._generated_connections)

    def _createConnection(self, source_index, target_index, weight, delay, n):
        """
        Connects a source and a target neurone via the psr component.
        First tries to obtain the source/target neurone objects from the corresponding populations, 
        then creates the nineml_daetools_bridge object for the synapse component and finally tries 
        to connect event ports between the source neurone and the synapse and analogue ports between
        the synapse and the target neurone. The source neurone, the synapse and the target neurone 
        are appended to the list of generated connections.
        Arguments:
         - source_index: integer; index in the source population
         - target_index: integer; index in the target population
         - weight: float
         - delay: float
         - n: number of connections in the projection (just to format the name of the synapse)
        Returns nothing.
        """
        source_neurone = self._source_population.getNeurone(source_index)
        target_neurone = self._target_population.getNeurone(target_index)
        
        synapse_name   = '{0}_Synapse{1}({2},{3})'.format(self._name, n, int(source_index), int(target_index))
        synapse        = create_nineml_daetools_bridge(synapse_name, self._psr, self._network, '')
        print(synapse.CanonicalName)
        
        nineml_daetools_bridge.connectModelsViaEventPort    (source_neurone, synapse,        self._network)
        nineml_daetools_bridge.connectModelsViaAnaloguePorts(synapse,        target_neurone, self._network)
        
        self._generated_connections.append( (source_neurone, synapse, target_neurone) )

class nineml_daetools_network_simulation(pyActivity.daeSimulation):
    def __init__(self, network):
        pyActivity.daeSimulation.__init__(self)
        
        self.m = network
        self.model_setups = []
        
        event_ports_expressions = {"spikeinput": "0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90"} 
        for name, group in network._groups.items():
            # Setup neurones in populations
            for name, population in group._populations.items():
                for neurone in population._neurones:
                    initial_values = population._parameters
                    setup = daetools_model_setup(neurone, False, parameters              = initial_values, 
                                                                 initial_conditions      = initial_values,
                                                                 event_ports_expressions = event_ports_expressions)
                    self.model_setups.append(setup)
        
            for name, projection in group._projections.items():
                # Setup synapses 
                initial_values = projection._psr_parameters
                for s, synapse, t in projection._generated_connections:
                    setup = daetools_model_setup(synapse, False, parameters         = initial_values, 
                                                                 initial_conditions = initial_values)
                    self.model_setups.append(setup)

    def SetUpParametersAndDomains(self):
        for s in self.model_setups:
            s.SetUpParametersAndDomains()
        
    def SetUpVariables(self):
        for s in self.model_setups:
            s.SetUpVariables()

if __name__ == "__main__":
    connections = explicit_connections_generator_interface([(0, 0, 0.1, 0.2), (0, 1, 0.1, 0.2), (0, 2, 0.1, 0.2), (0, 3, 0.1, 0.2), (0, 4, 0.1, 0.2)])
    print('size = ', connections.size)
    print('arity = ', connections.arity)
    for connection in connections:
        print(connection)
    
    exit(0)
    
    catalog = "file:///home/ciroki/Data/NineML/nineml-model-tree/lib9ml/python/dae_impl/"

    sn_parameters = {
                     'tspike' :    (-10000.0, ''),
                     'V' :         (-0.06, ''),
                     'gl' :        (50.0, ''),
                     'vreset' :    (-0.06, ''),
                     'taurefrac' : (0.008, ''),
                     'vthresh' :   (-0.04, ''),
                     'vrest' :     (-0.06, ''),
                     'cm' :        (1.0, '')
                    }
    
    psr_parameters = {
                       'vrev' : (0.0, ''),
                       'q'    : (3.0, ''),
                       'tau'  : (5.0, ''),
                       'g'    : (0.0, '')
                     }
    
    fake_grid2D = nineml.user_layer.Structure("2D grid", catalog + "coba_synapse.xml")

    s_celltype = nineml.user_layer.SpikingNodeType("Source neurone type", catalog + "iaf.xml", sn_parameters)
    t_celltype = nineml.user_layer.SpikingNodeType("Target neurone type", catalog + "iaf.xml", sn_parameters)

    s_cells = nineml.user_layer.Population("Source population", 10, s_celltype, nineml.user_layer.PositionList(structure=fake_grid2D))
    t_cells = nineml.user_layer.Population("Target population", 10, s_celltype, nineml.user_layer.PositionList(structure=fake_grid2D))

    connection_rule = nineml.user_layer.ConnectionRule("Explicit Connections",      catalog + "connections.txt",)
    psr             = nineml.user_layer.SynapseType   ("Post-synaptic response",    catalog + "coba_synapse.xml", psr_parameters)
    connection_type = nineml.user_layer.ConnectionType("Static weights and delays", catalog + "coba_synapse.xml", {'weight': (0.1, "nS"), 'delay': (0.3, "ms")})

    projection = nineml.user_layer.Projection("Projection 1", s_cells, t_cells, connection_rule, psr, connection_type)

    network = nineml.user_layer.Group("Network")
    network.add(s_cells)
    network.add(t_cells)
    network.add(projection)

    model = nineml.user_layer.Model("Simple 9ML example model")
    model.add_group(network)
    model.write("simple_example1.xml")
    
    
    network = daetools_point_neurone_network(model)
    #print(network)

    # Create Log, Solver, DataReporter and Simulation object
    log          = daeLogs.daePythonStdOutLog()
    daesolver    = pyIDAS.daeIDAS()
    datareporter = pyDataReporting.daeTCPIPDataReporter()
    simulation   = nineml_daetools_network_simulation(network)

    # Set the time horizon and the reporting interval
    simulation.ReportingInterval = 0.1
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
