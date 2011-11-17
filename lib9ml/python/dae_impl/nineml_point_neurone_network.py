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

# Here the argument 'parameters' is a ParameterSet object
def getInitialValues(rootModel, parameters):
    rootName = rootModel.CanonicalName
    new_parameters = {}
    for name, parameter in list(parameters.items()):
        new_parameters[rootName + '.' + name] = (parameter.value, parameter.unit) 
    return new_parameters

class daetools_neurone_population(pyCore.daeModel):
    def __init__(self, nineml_population, parent, description):
        pyCore.daeModel.__init__(self, nineml_population.name, parent, description)

        self.nineml_population = nineml_population
        self.neurones          = []
        
        # Here we should intantiate AL component based on the UL component
        self.nineml_component = nineml.abstraction_layer.readers.XMLReader.read(nineml_population.prototype.definition.url) 
        print(self.nineml_component)
        
        for i in range(0, nineml_population.number):
            neurone = nineml_daetools_bridge('Neurone_{0}'.format(i), self.nineml_component, self, '')
            self.neurones.append(neurone)
    
    def DeclareEquations(self):
        for neurone in self.neurones:
            neurone.DeclareEquations()
    
    def __getitem__(self, index):
        return self.neurones[index]
    
class daetools_point_neurone_network(pyCore.daeModel):
    def __init__(self, nineml_source_population, nineml_target_population, psr_component, connections, weight, delay):
        pyCore.daeModel.__init__(self, 'NineMLPointNeuroneNetwork', None, '')

        self.nineml_source_population = nineml_source_population
        self.nineml_target_population = nineml_target_population
        self.psr_component            = psr_component
        self.connections              = connections
        self.weight                   = weight
        self.delay                    = delay
        
        self.generated_connections = []
        self.psr                   = nineml.abstraction_layer.readers.XMLReader.read(psr_component.definition.url)
        self.population_s          = daetools_neurone_population(nineml_source_population, self, '')
        self.population_t          = daetools_neurone_population(nineml_target_population, self, '')
        
        for connection in self.connections:
            self._createConnection(connection[0], connection[1], self.weight, self.delay)
    
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

class nineml_daetools_network_simulation(pyActivity.daeSimulation):
    def __init__(self, network):
        pyActivity.daeSimulation.__init__(self)
        
        self.m = network
        self.model_setups = []
        
        for neurone in network.population_s.neurones:
            initial_values = getInitialValues(neurone, network.nineml_source_population.prototype.parameters)
            setup = daetools_model_setup(neurone, parameters         = initial_values, 
                                                  initial_conditions = initial_values)
            self.model_setups.append(setup)
        
        for neurone in network.population_t.neurones:
            initial_values = getInitialValues(neurone, network.nineml_target_population.prototype.parameters)
            setup = daetools_model_setup(neurone, parameters         = initial_values, 
                                                  initial_conditions = initial_values)
            self.model_setups.append(setup)

        for t in network.generated_connections:
            source, psr, target = t
            initial_values = getInitialValues(psr, network.psr_component.parameters)
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

