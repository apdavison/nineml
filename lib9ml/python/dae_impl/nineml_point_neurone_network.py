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

def fixKeyNames(rootModel, parameters):
    """
    The function replaces dictionary keys with their canonical names: 'V' becomes 'model1.model2.[...].V' 
    Arguments:
      - rootModel: daeModel object
      - parameters: ParameterSet object
    """
    rootName = rootModel.CanonicalName
    new_parameters = {}
    for name, parameter in list(parameters.items()):
        new_parameters[rootName + '.' + name] = (parameter.value, parameter.unit) 
    return new_parameters

def create_nineml_daetools_bridge(name, al_component, parent = None, description = ''):
    """
    Creates 'nineml_daetools_bridge' object for a given AbstractionLayer Component
    """
    return nineml_daetools_bridge(fixObjectName(name), al_component, parent, description)

def create_al_from_ul_component(ul_component):
    """
    Creates AL component for a given UL component.
    Returns a tuple (ALComponent object, URL). If the component cannot be loaded then the object is None.
    This is a case when loading ExplicitConnections rule or the url cannot be resolved.
    """
    try:
        al_component = None
        al_component = nineml.abstraction_layer.readers.XMLReader.read(ul_component.definition.url) 
    
    except Exception as e:
        print(str(e))

    # If the component cannot be loaded then 
    return al_component

class daetools_point_neurone_network(pyCore.daeModel):
    """
    A top-level daetools model. All other models will be added to it (neurones, synapses):
     - Neurone names will be: model_name.population_name.Neurone_xxx
     - Synapse names will be: model_name.projection_name_Synxxx_sourceindex_targetindex
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
        self._connection_type       = network.getComponent(ul_projection.connection_type.name)
        self._generated_connections = []
        
        al_connection_rule_component = network.getComponent(ul_projection.rule.name)
        explicit_connections_file    = network.getComponentURL(ul_projection.rule.name)
        if al_connection_rule_component: # CSA
            self._handleConnectionRuleComponent(al_connection_rule_component)
        else: # explicit connections
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
           The file is a space-delimited text file in the format: source_target[_weight_delay_parameter1_parameter2 ...]
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
        Arguments:
         - source_index: integer; index in the source population
         - target_index: integer; index in the target population
         - weight: float
         - delay: float
        """
        source_neurone = self._source_population.getNeurone(source_index)
        target_neurone = self._target_population.getNeurone(target_index)
        
        synapse_name   = '{0}_Synapse({1})({2},{3})'.format(self._name, n, int(source_index), int(target_index))
        synapse        = create_nineml_daetools_bridge(synapse_name, self._psr, self._network, '')
        print(synapse.CanonicalName)
        
        nineml_daetools_bridge.connectEventPorts(source_neurone, synapse, self._network)
        nineml_daetools_bridge.connectAnaloguePorts(synapse, target_neurone, self._network)
        
        self._generated_connections.append( (source_neurone, synapse, target_neurone) )

"""    
        

    def DeclareEquations(self):
        pass

    def _createConnection(self, source_index, target_index, weight, delay):
        source = self.population_s[source_index]
        target = self.population_t[target_index]
        psr    = self._clonePSRComponent()
        
        self._connectSourceNeuroneAndPSR(source, psr)
        self._connectPSRAndTargetNeurone(psr, target)
        
        self.generated_connections.append( (source, psr, target) )

    def _connectSourceNeuroneAndPSR(self, source, psr):
        source_port = findObjectInModel(source, 'spikeoutput', look_for_eventports = True)
        target_port = findObjectInModel(psr,    'spikeinput',  look_for_eventports = True)
        print(source_port)
        print(target_port)
    
    def _connectPSRAndTargetNeurone(self, psr, target):
        source_I = findObjectInModel(psr, 'I', look_for_ports = True)
        source_V = findObjectInModel(psr, 'V', look_for_ports = True)
        print(source_I)
        print(source_V)
        
        target_I = findObjectInModel(target, 'ISyn', look_for_reduceports = True)
        target_V = findObjectInModel(target, 'V',    look_for_ports       = True)
        print(target_I)
        print(target_V)
        
        nineml_daetools_bridge.connectPorts(self, source_I, target_I)
        nineml_daetools_bridge.connectPorts(self, source_V, target_V)

    def _clonePSRComponent(self):
        psr = nineml_daetools_bridge('PSR_{0}'.format(len(self.generated_connections)), self.psr, self)
        return psr
"""

class nineml_daetools_network_simulation(pyActivity.daeSimulation):
    def __init__(self, network):
        pyActivity.daeSimulation.__init__(self)
        
        self.m = network
        self.model_setups = []
        
        for neurone in network.population_s.neurones:
            initial_values = fixKeyNames(neurone, network.nineml_source_population.prototype.parameters)
            setup = daetools_model_setup(neurone, parameters         = initial_values, 
                                                  initial_conditions = initial_values)
            self.model_setups.append(setup)
        
        for neurone in network.population_t.neurones:
            initial_values = fixKeyNames(neurone, network.nineml_target_population.prototype.parameters)
            setup = daetools_model_setup(neurone, parameters         = initial_values, 
                                                  initial_conditions = initial_values)
            self.model_setups.append(setup)

        for t in network.generated_connections:
            source, psr, target = t
            initial_values = fixKeyNames(psr, network.psr_component.parameters)
            setup = daetools_model_setup(psr, parameters         = initial_values, 
                                              initial_conditions = initial_values)
            self.model_setups.append(setup)

    def SetUpParametersAndDomains(self):
        for s in self.model_setups:
            s.SetUpParametersAndDomains()
        
    def SetUpVariables(self):
        for s in self.model_setups:
            s.SetUpVariables()

if __name__ == "__main__":
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

    exc_celltype = nineml.user_layer.SpikingNodeType("Excitatory neuron type", catalog + "iaf.xml", sn_parameters)
    inh_celltype = nineml.user_layer.SpikingNodeType("Inhibitory neuron type", catalog + "iaf.xml", sn_parameters)

    exc_cells = nineml.user_layer.Population("Excitatory cells", 10, exc_celltype, nineml.user_layer.PositionList(structure=fake_grid2D))
    inh_cells = nineml.user_layer.Population("Inhibitory cells", 10, inh_celltype, nineml.user_layer.PositionList(structure=fake_grid2D))

    exc_connection_rule = nineml.user_layer.ConnectionRule("Excitatory Connections", catalog + "exc_connections.txt",)
    inh_connection_rule = nineml.user_layer.ConnectionRule("Inhibitory Connections", catalog + "inh_connections.txt",)

    exc_psr = nineml.user_layer.SynapseType("Excitatory post-synaptic response", catalog + "coba_synapse.xml", psr_parameters)
    inh_psr = nineml.user_layer.SynapseType("Inhibitory post-synaptic response", catalog + "coba_synapse.xml", psr_parameters)

    exc_connection_type = nineml.user_layer.ConnectionType("Static excitatory connections", catalog + "coba_synapse.xml", {'weight': (0.1, "nS"), 'delay': (0.3, "ms")})
    inh_connection_type = nineml.user_layer.ConnectionType("Static inhibitory connections", catalog + "coba_synapse.xml", {'weight': (0.2, "nS"), 'delay': (0.3, "ms")})

    exc2exc = nineml.user_layer.Projection("Excitatory connections", exc_cells, exc_cells, exc_connection_rule, exc_psr, exc_connection_type)
    inh2exc = nineml.user_layer.Projection("Inhibitory connections", inh_cells, exc_cells, inh_connection_rule, inh_psr, inh_connection_type)

    network = nineml.user_layer.Group("Network")
    network.add(exc_cells)
    network.add(inh_cells)
    network.add(exc2exc)
    network.add(inh2exc)

    model = nineml.user_layer.Model("Simple 9ML example model")
    model.add_group(network)
    model.write("simple_example1.xml")
    
    
    network = daetools_point_neurone_network(model)
    #print(network)

