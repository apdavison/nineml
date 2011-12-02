#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import os, sys, urllib
from time import localtime, strftime

import nineml
from nineml.abstraction_layer import readers
from nineml.abstraction_layer.testing_utils import TestableComponent

from daetools.pyDAE import pyCore, pyActivity, pyDataReporting, pyIDAS, daeLogs
from nineml_component_inspector import nineml_component_inspector
from nineml_daetools_bridge import nineml_daetools_bridge, findObjectInModel
from nineml_tex_report import createLatexReport, createPDF
from nineml_daetools_simulation import daeSimulationInputData, nineml_daetools_simulation, ninemlTesterDataReporter, daetools_model_setup

__ExplicitConnectionsComponentName__ = 'ExplicitConnectionsComponent'
__CSAComponentName__                 = 'CSA'

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
    return nineml_daetools_bridge(name, al_component, parent, description)

def create_al_from_ul_component(ul_component):
    """
    Creates AL component for a given UL component
    """
    al_component = nineml.abstraction_layer.readers.XMLReader.read(ul_component.definition.url) 
    if not al_component:
        raise RuntimeError('Cannot resolve UL component [%s] definition: %s'.format(name, ul_component.definition.url))
    return al_component

class daetools_point_neurone_network:
    """
    """
    def __init__(self, model):
        """
        """
        self._name        = model.name
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
            raise RuntimeError('Component [%s] does not exist in the network'.format(name)) 
        return self._components[name]
        
    def getGroup(self, name):
        if not name in self._groups:
            raise RuntimeError('Group [%s] does not exist in the network'.format(name)) 
        return self._groups[name]

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
        self._components[name] = al_component

class daetools_group:
    """
    """
    def __init__(self, name, ul_group, network):
        """
        """
        self._name        = name
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
            raise RuntimeError('Population [%s] does not exist in the group'.format(name)) 
        return self._populations[name]
        
    def getProjection(self, name):
        if not name in self._projections:
            raise RuntimeError('Projection [%s] does not exist in the group'.format(name)) 
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
           PSR components are first transformed into 'nineml_daetools_bridge' objects
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
        self._name       = name
        self._neurones   = []
        self._positions  = []
        
        # Instantiate AL component based on the UL component
        al_component = network.getComponent(ul_population.prototype.name) 
        
        for i in range(0, ul_population.number):
            neurone = create_nineml_daetools_bridge('Neurone_{0}'.format(i), al_component)
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
        self._name                  = ul_projection.name
        self._source_population     = group.getPopulation(ul_projection.source.name)
        self._target_population     = group.getPopulation(ul_projection.target.name)
        self._psr                   = network.getComponent(ul_projection.synaptic_response.name)
        self._connection_type       = network.getComponent(ul_projection.connection_type.name)
        self._generated_connections = []
        
        self._handleConnectionRuleComponent(network.getComponent(ul_projection.rule.name))

        """
        for connection in self._connections:
            if not isinstance(connection, (list, tuple)):
                raise RuntimeError('Invalid list of explicit connections')
            
            if len(connection) == 4:
                # Format: (s, t, w, d)
                s, t, w, d = connection
                self._createConnection(s, t, w, d)
            else:
                raise RuntimeError('Invalid explicit connection: {1}'.format(connection))
        """
        
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
        Arguments:
         - al_connection_rule: AL Component object
        """
        if al_connection_rule.name == __ExplicitConnectionsComponentName__:
            pass
        
        elif al_connection_rule.name == __CSAComponentName__:
            pass
        
        else:
            raise RuntimeError('Unsupported connection rule component: {0}'.format(connection_rule.name))
    
    def _createConnection(self, source_index, target_index, weight, delay):
        """
        Arguments:
         - source_index: integer; index in the source population
         - target_index: integer; index in the target population
         - weight: float
         - delay: float
        """
        source_neurone = self._source_population.getNeurone(source_index)
        target_neurone = self._target_population.getNeurone(target_index)
        
        synapse_name   = 'Synapse_n%i_%i_%i'.format(len(target_neurone.Models), source_index, source_index)
        synapse        = create_nineml_daetools_bridge(synapse_name, self._psr_al_component, target)
        
        self._connectSourceNeuroneAndSynapse(source_neurone, synapse)
        self._connectSynapseAndTargetNeurone(synapse, target_neurone)
        
        self.generated_connections.append( (source_neurone, synapse, target_neurone) )

    def _connectSourceNeuroneAndSynapse(self, source, synapse):
        """
        Arguments:
         - source: nineml_daetools_bridge object (neurone)
         - synapse: nineml_daetools_bridge object (synapse)
        """
        if (len(source.nineml_event_ports) != 1) or (source.nineml_event_ports[0].Type != eOutletPort):
            raise RuntimeError('The source neurone [%s] must have a single outlet event port'.format(source.Name))
        
        if (len(synapse.nineml_event_ports) != 1) or (synapse.nineml_event_ports[0].Type != eInletPort):
            raise RuntimeError('The synapse [%s] must have a single inlet event port'.format(source.Name))
        
        source_port = source.nineml_event_ports[0]
        target_port = synapse.nineml_event_ports[0]
        
        nineml_daetools_bridge.connectEventPorts(source, source_port, target_port)
    
    def _connectSynapseAndTargetNeurone(self, synapse, target):
        """
        Arguments:
         - synapse: nineml_daetools_bridge object (synapse)
         - target: nineml_daetools_bridge object (neurone)
        """
        if len(synapse.Ports) != len(target.Ports):
            raise RuntimeError('Cannot connect a synapse to a neurone: number of analogue ports do not match')
        
        # Iterate over synapse ports to find a match for each one in the target neurone ports list.
        # If a match is not found, or if an incompatible pair of ports has been found throw an exception.
        # ACHTUNG, ACHTUNG!! It is assumed that synapses do not have reduce ports (tamba/lamba?)
        for synapse_port in synapse.nineml_analog_ports:
            matching_port_found = False
            
            # 1) Look in the list of analogue ports
            for target_port in target.nineml_analog_ports:
                if synapse_port.Name == target_port.Name:
                    if (synapse_port.Type == eInletPort) and (target_port.Type == eOutletPort):
                        nineml_daetools_bridge.connectPorts(target, synapse_port, target_port)
                        matching_port_found = True
                    
                    elif (synapse_port.Type == eOutletPort) and (target_port.Type == eInletPort):
                        nineml_daetools_bridge.connectPorts(target, synapse_port, target_port)
                        matching_port_found = True
                    
                    else:
                        msg = 'Cannot connect a synapse to a neurone: synapse port [%s] and neurone port [%s] do not match'.format(synapse_port.Name, target_port.Name)
                        raise RuntimeError(msg)
            
            # 2) If not connected yet, look in the list of reduce ports
            if matching_port_found == False:
                for target_port in target.nineml_reduce_ports:
                    if synapse_port.Name == target_port.Name:
                        # Achtung! Reduce ports are implicitly inlet
                        if (synapse_port.Type == eOutletPort):
                            nineml_daetools_bridge.connectPorts(target, synapse_port, target_port)
                            matching_port_found = True
            
            # If not found - die ignobly
            if matching_port_found == False:
                raise RuntimeError('Cannot connect a synapse to a neurone: cannot find a match for the synapse port [%s]'.format(synapse_port.Name))

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

    exc_cell_parameters = nineml.user_layer.ParameterSet(
                                                            membraneCapacitance=(1.0, "nF"),
                                                            membraneTimeConstant=(20.0, "ms"),
                                                            refractoryTime=(5.0, "ms"),
                                                            threshold=(-50.0, "mV"),
                                                            restingPotential=(-65.0, "mV"),
                                                            resetPotential=(-65.0, "mV")
                                                         )

    inh_cell_parameters = nineml.user_layer.ParameterSet(
                                                        membraneTimeConstant=(20.0, "ms"),
                                                        resetPotential=(-60.0, "mV")
                                                        )
    inh_cell_parameters.complete(exc_cell_parameters)

    exc_celltype = nineml.user_layer.SpikingNodeType("Excitatory neuron type",
                                        catalog + "coba_synapse.xml",
                                        exc_cell_parameters)
    inh_celltype = nineml.user_layer.SpikingNodeType("Inhibitory neuron type",
                                        catalog + "coba_synapse.xml",
                                        inh_cell_parameters)

    grid2D = nineml.user_layer.Structure("2D grid",
                            catalog + "coba_synapse.xml",
                            {'fillOrder': ("sequential", None),
                            'aspectRatioXY': (1.0, "dimensionless"),
                            'dx': (1.0, u"µm"), 'dy': (1.0, u"µm"),
                            'x0': (0.0, u"µm"), 'y0': (0.0, u"µm")})
                                    
    exc_cells = nineml.user_layer.Population("Excitatory cells", 100, exc_celltype,
                                nineml.user_layer.PositionList(structure=grid2D))
    inh_cells = nineml.user_layer.Population("Inhibitory cells", 25, inh_celltype,
                                nineml.user_layer.PositionList(structure=grid2D))

    connection_rule = nineml.user_layer.ConnectionRule("random connections",
                                            catalog + "coba_synapse.xml",
                                            {'p_connect': (0.1, "dimensionless")})

    exc_psr = nineml.user_layer.SynapseType("Excitatory post-synaptic response",
                                catalog + "coba_synapse.xml",
                                dict(decayTimeConstant=(5.0, "ms"), reversalPotential=(0.0, "mV")))
    inh_psr = nineml.user_layer.SynapseType("Inhibitory post-synaptic response",
                                catalog + "coba_synapse.xml",
                                dict(decayTimeConstant=(5.0, "ms"), reversalPotential=(-70.0, "mV")))

    exc_connection_type = nineml.user_layer.ConnectionType("Static excitatory connections",
                                                catalog + "coba_synapse.xml",
                                                {'weight': (0.1, "nS"), 'delay': (0.3, "ms")})
    inh_connection_type = nineml.user_layer.ConnectionType("Static inhibitory connections",
                                                catalog + "coba_synapse.xml",
                                                {'weight': (0.2, "nS"), 'delay': (0.3, "ms")})

    exc2exc = nineml.user_layer.Projection("Excitatory cells-Excitatory cells",
                                exc_cells, exc_cells, connection_rule,
                                exc_psr, exc_connection_type)
    inh2all = nineml.user_layer.Projection("Inhibitory connections",
                                inh_cells, exc_cells, connection_rule,
                                inh_psr, inh_connection_type)

    network = nineml.user_layer.Group("Network")
    network.add(exc_cells)
    network.add(inh_cells)
    network.add(exc2exc)
    network.add(inh2all)

    model = nineml.user_layer.Model("Simple 9ML example model")
    model.add_group(network)
    #model.write("simple_example1.xml")
    
    
    network = daetools_point_neurone_network(model)
    print(network)

