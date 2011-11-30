#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import os, sys
from time import localtime, strftime

import nineml
from nineml.abstraction_layer import readers
from nineml.abstraction_layer.testing_utils import TestableComponent
from nineml.abstraction_layer import ComponentClass

from daetools.pyDAE import pyCore, pyActivity, pyDataReporting, pyIDAS, daeLogs
from nineml_component_inspector import nineml_component_inspector
from nineml_daetools_bridge import nineml_daetools_bridge, findObjectInModel
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
        self._model       = model
        self._components  = {}
        self._groups      = {}
        
        for name, ul_component in list(self.model.components.items()):
            self._handleComponent(ul_component)
        
        for name, group in list(self.model.groups.items()):
            self._handleGroup(name, group)

    def getComponent(self, name):
        if not name in self._components:
            raise RuntimeError('Component [%s] does not exist in the network'.format(name)) 
        return self._components[name]
        
    def getGroup(self, name):
        if not name in self._groups:
            raise RuntimeError('Group [%s] does not exist in the network'.format(name)) 
        return self._groups[name]

    def _handleGroup(self, name, group):
        """
        Handles a NineML UserLayer Group object:
         - Resolves/creates AL components and their runtime parameters'/initial-conditions' values.
         - Creates populations of neurones and adds them to the 'neuronePopulations' dictionary
         - Creates projections and adds them to the 'projections' dictionary
        Arguments:
         - name: string
         - group: UL Group object
        """
        pass
    
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
         - ul_projection: UL Projection object
         - network: daetools_point_neurone_network object
        """
        self._name       = name
        self._neurones   = []
        
        # Instantiate AL component based on the UL component
        al_component = network.getComponent(ul_population.prototype.name) 
        
        for i in range(0, ul_population.number):
            neurone = create_nineml_daetools_bridge('Neurone_{0}'.format(i), al_component)
            self._neurones.append(neurone)
    
    def getNeurone(self, index):
        return self._neurones[int(index)]
    
class daetools_projection:
    """
    """
    def __init__(self, name, ul_projection, group, network):
        """
        Arguments:
         - name: string
         - ul_projection: UL Projection object
         - group: daetools_group object
         - network: daetools_point_neurone_network object
        """
        if (not isinstance(ul_projection.source, Population)) or (not isinstance(ul_projection.target, Population)):
            raise RuntimeError('Only projections on populations are supported at the moment')
        
        if ul_projection.connection_type:
            raise RuntimeError('Connection type components are not supported at the moment')
        
        if (not isinstance(ul_projection.rule, list)):
            raise RuntimeError('Only explicit connections are supported at the moment')

        self._name                  = ul_projection.name
        self._source_population     = group.getPopulation(ul_projection.source.name)
        self._target_population     = group.getPopulation(ul_projection.target.name)
        self._psr_al_component      = network.getComponent(ul_projection.synaptic_response.name)
        self._connections           = ul_projection.rule
        self._connection_type       = network.getComponent(ul_projection.connection_type.name)
        self._generated_connections = []

        for connection in self._connections:
            if not isinstance(connection, (list, tuple)):
                raise RuntimeError('Invalid list of explicit connections')
            
            if len(connection) == 4:
                # Format: (s, t, w, d)
                s, t, w, d = connection
                self._createConnection(s, t, w, d)
            else:
                raise RuntimeError('Invalid explicit connection: {1}'.format(connection))

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
    sn_parameters = {
                     'tspike' :    (-100000000.0, ''),
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

    sn_component  = nineml.user_layer.SpikingNodeType('iaf',      'iaf.xml',          sn_parameters)
    psr_component = nineml.user_layer.SynapseType('coba_synapse', 'coba_synapse.xml', psr_parameters)
    
    sn_positions  = nineml.user_layer.PositionList()
    psr_positions = nineml.user_layer.PositionList()
    
    ns = 5
    nt = 5
    source_population = nineml.user_layer.Population('Source', ns, sn_component, sn_positions)
    target_population = nineml.user_layer.Population('Target', nt, sn_component, psr_positions)
    
    weight = 1.0
    delay  = 0.0
    
    connections = []
    for i in range(0, ns):
        connections.append( (i, i) )
    
    network = daetools_point_neurone_network(source_population, target_population, psr_component, connections, weight, delay)
    simulation = nineml_daetools_network_simulation(network)
    
    # Create Log, Solver, DataReporter and Simulation object
    log          = pyCore.daeBaseLog()
    daesolver    = pyIDAS.daeIDAS()
    datareporter = pyDataReporting.daeTCPIPDataReporter()
    
    # Set the time horizon and the reporting interval
    simulation.ReportingInterval = 0.1
    simulation.TimeHorizon       = 1.0
    simulation.m.SetReportingOn(True)

    # Connect data reporter
    simName = simulation.m.Name + strftime(" [%d.%m.%Y %H:%M:%S]", localtime())
    if(datareporter.Connect("", simName) == False):
        sys.exit()

    # Initialize the simulation
    simulation.Initialize(daesolver, datareporter, log)
    
    simulation.m.population_s.neurones[0].SaveModelReport(simulation.m.population_s.neurones[0].Name + ".xml")
    simulation.m.SaveModelReport(simulation.m.Name + ".xml")
    
    # Solve at time=0 (initialization)
    simulation.SolveInitial()

    # Run
    simulation.Run()
    simulation.Finalize()

