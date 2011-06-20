from nineml.abstraction_layer.validators.base import ComponentValidatorPerNamespace

from collections import defaultdict
from nineml.exceptions.exceptions import NineMLRuntimeError
from nineml.abstraction_layer.component.namespaceaddress import NamespaceAddress
from nineml.abstraction_layer import math_namespace
from nineml.utility import assert_no_duplicates

# Check that the sub-components stored are all of the
# right types:
class ComponentValidatorTimeDerivativesAreDeclared(ComponentValidatorPerNamespace):
    """ 
    """
     
    def __init__(self, component):
        ComponentValidatorPerNamespace.__init__(self, explicitly_require_action_overrides=False)
        self.sv_declared = defaultdict(list)
        self.time_derivatives_used = defaultdict(list)
            
        self.visit(component)
        
        for namespace,time_derivatives in self.time_derivatives_used.iteritems():
            for td in time_derivatives:
                assert td in self.sv_declared[namespace], 'StateVariable not declared: %s'%td
        
        
    def ActionStateVariable(self, state_variable, namespace, **kwargs):
        self.sv_declared[namespace].append(state_variable.name)
        
    def ActionODE(self, timederivative, namespace,**kwargs):
        self.time_derivatives_used[namespace].append(timederivative.dependent_variable)




class ComponentValidatorStateAssignmentsAreOnStateVariables(ComponentValidatorPerNamespace):
    """ Check that we only attempt to make StateAssignments to state-variables.
    """
     
    def __init__(self, component):
        ComponentValidatorPerNamespace.__init__(self, explicitly_require_action_overrides=False)
        self.sv_declared = defaultdict(list)
        self.state_assignments_lhses = defaultdict(list)
            
        self.visit(component)
        
        for namespace,state_assignments_lhs in self.state_assignments_lhses.iteritems():
            for td in state_assignments_lhs:
                assert td in self.sv_declared[namespace]
            
    def ActionStateVariable(self, state_variable, namespace, **kwargs):
        self.sv_declared[namespace].append(state_variable.name)
        
    def ActionStateAssignment(self, state_assignment, namespace,**kwargs):
        assert False
        self.state_assignments_lhses[namespace].append(state_assignment.lhs)









class ComponentValidatorAliasesAreNotRecursive(ComponentValidatorPerNamespace):
    """Check that aliases are not self-referential"""
    
    def __init__(self,component):
        ComponentValidatorPerNamespace.__init__(self, explicitly_require_action_overrides=False)
        self.visit(component)
        
    def ActionComponentClass(self, component, namespace):
        
        unresolved_aliases = dict( (a.lhs, a) for a in component.aliases ) 
        
        def alias_contains_unresolved_symbols(alias):
            unresolved = [ sym for sym in alias.rhs_atoms if sym in unresolved_aliases]
            return len(unresolved) != 0
        
        def get_resolved_aliases( ):
            return [alias for alias in unresolved_aliases.values() if not alias_contains_unresolved_symbols(alias) ]
        
                            
        while( unresolved_aliases ):
            
            resolved_aliases = get_resolved_aliases()
            if resolved_aliases:
                for r in resolved_aliases:
                    del unresolved_aliases[r.lhs]
                
            else:
                errmsg = "Unable to resolve all aliases in %. You may have a recursion issue. Remaining Aliases: %s"% (namespace, ','.join(unresolved_aliases.keys()) )
                raise NineMLRuntimeError(errmsg)
            
            






class ComponentValidatorAliasesAndStateVariablesHaveNoUnResolvedSymbols(ComponentValidatorPerNamespace):
    """Check that aliases and timederivatives are defined in terms of other parameters, aliases, statevariables and ports"""
    def __init__(self,component):
        ComponentValidatorPerNamespace.__init__(self, explicitly_require_action_overrides=False)

        self.available_symbols = defaultdict(list)
        self.aliases = defaultdict(list)
        self.timederivatives = defaultdict(list)
        
        self.visit(component)

        
        #TODO:
        excludes = ['celsius'] + math_namespace.namespace.keys()
        
        for ns,aliases in self.aliases.iteritems():
            for alias in aliases:
                for rhs_atom in alias.rhs_atoms:
                    if not rhs_atom in self.available_symbols[ns] and not rhs_atom in excludes:
                        raise NineMLRuntimeError('Unresolved Symbol in Alias: %s [%s]'%(rhs_atom, alias))                
        
        for ns, timederivatives in self.timederivatives.iteritems():
            for timederivative in timederivatives:
                for rhs_atom in timederivative.rhs_atoms:
                    if not rhs_atom in self.available_symbols[ns] and not rhs_atom in excludes:
                        raise NineMLRuntimeError('Unresolved Symbol in Time Derivative: %s [%s]'%(rhs_atom, timederivative))
            
        
    def add_symbol(self, namespace, symbol):
        assert not symbol in self.available_symbols[namespace] 
        self.available_symbols[namespace].append(symbol)
    
    def ActionAnalogPort(self, port, namespace, **kwargs):
        if port.is_incoming():
            self.available_symbols[namespace].append(port.name)
            
    def ActionStateVariable(self, state_variable, namespace, **kwargs):
        self.add_symbol(namespace=namespace, symbol=state_variable.name)
        
    def ActionTimeDerivative(self, time_derivative, namespace, **kwargs):
        self.aliases[namespace].append(time_derivative)
                        
    def ActionAlias(self, alias, namespace, **kwargs):
        self.add_symbol(namespace=namespace, symbol=alias.lhs )
        self.aliases[namespace].append(alias)

    def ActionParameter(self, parameter, namespace, **kwargs):
        self.add_symbol(namespace=namespace, symbol=parameter.name )











class ComponentValidatorPortConnections(ComponentValidatorPerNamespace):
    """Check that all the port connections point to a port, and that
    each send & recv port only has a single connection. 
    """
    def __init__(self,component):
        ComponentValidatorPerNamespace.__init__(self, explicitly_require_action_overrides=False)

        self.ports = defaultdict(list)
        self.portconnections = list()
        
        self.visit(component)
        
        connected_recv_ports = set()
        
        # Check each source and sink exist,
        # and that each recv port is connected at max once.
        for src,sink in self.portconnections:
            if not src in self.ports:
                raise NineMLRuntimeError('Unable to find port specified in connection: %s'%(src) )
            if self.ports[src].is_incoming():
                raise NineMLRuntimeError('Port was specified as a source, but is incoming: %s'%(src) )
            
            
            if not  sink in self.ports:
                raise NineMLRuntimeError('Unable to find port specified in connection: %s'%(src) )
            
            if not self.ports[sink].is_incoming():
                raise NineMLRuntimeError('Port was specified as a sink, but is not incoming: %s'%(src) )
                
                
            if self.ports[sink].mode == 'recv':
                if self.ports[sink] in connected_recv_ports:
                    raise NineMLRuntimeError("Port was 'recv' and specified twice: %s"%(src) )
                connected_recv_ports.add( self.ports[sink] )
        
        
    def ActionAnalogPort(self, analogport, namespace):
        port_address = NamespaceAddress.concat( namespace, analogport.name) 
        print 'Found Port', port_address
        assert not port_address in self.ports
        self.ports[port_address] = analogport
        
        
    def ActionEventPort(self, analogport, namespace):
        port_address = NamespaceAddress.concat( namespace, analogport.name )
        assert not port_address in self.ports
        self.ports[port_address] = analogport
        
        
    def ActionComponentClass(self, component, namespace):
        for src,sink in component.portconnections:
            full_src   = NamespaceAddress.concat( namespace, src )
            full_sink  = NamespaceAddress.concat( namespace, sink )
            self.portconnections.append( (full_src, full_sink) )
            
        
        
        

    
class ComponentValidatorRegimeGraph(ComponentValidatorPerNamespace):
    
    def __init__(self,component):
        ComponentValidatorPerNamespace.__init__(self, explicitly_require_action_overrides=False)
        
        self.connected_regimes_from_regime = defaultdict( set ) 
        self.regimes_in_namespace = defaultdict( set )
    
        self.visit(component)
    
    
        def add_connected_regimes_recursive( regime, connected ):
            connected.add(regime)
            for r in self.connected_regimes_from_regime[regime]:
                if not r in connected:
                    add_connected_regimes_recursive( r, connected )
                
        for namespace, regimes in self.regimes_in_namespace.iteritems():
            
            # Perhaps we have no transition graph; this is OK:
            if len( regimes ) == 0:continue
        
            connected = set()
            add_connected_regimes_recursive( regimes[0], connected)
            if len( connected ) != len( self.regimes_in_namespace[namespace] ):
                raise NineMLRuntimeError('Transition graph is contains islands')
    
    
    def ActionComponentClass(self, component, namespace):
        self.regimes_in_namespace[namespace] = list( component.regimes )
        


    def ActionRegime(self, regime, namespace):
        for transition in regime.transitions:
            self.connected_regimes_from_regime[regime].add( transition.target_regime )
            self.connected_regimes_from_regime[transition.target_regime].add( regime )
        
    


class ComponentValidatorNoDuplicatedObjects(ComponentValidatorPerNamespace):
    def __init__(self,component):
        ComponentValidatorPerNamespace.__init__(self, explicitly_require_action_overrides=True)

        self.all_objects = list()
    
        self.visit(component)
    
        assert_no_duplicates(self.all_objects)
        
    
    def ActionComponentClass(self, component,  **kwargs):
        self.all_objects.append(component)
        
    def ActionDynamics(self, dynamics, **kwargs):
        self.all_objects.append(dynamics)
        
    def ActionRegime(self,regime,  **kwargs):
        self.all_objects.append(regime)
        
    def ActionStateVariable(self, state_variable, **kwargs):
        self.all_objects.append(state_variable)
        
    def ActionParameter(self, parameter, **kwargs):
        self.all_objects.append(parameter)
        
    def ActionAnalogPort(self, port, **kwargs):
        self.all_objects.append(port)
        
    def ActionEventPort(self, port, **kwargs):
        self.all_objects.append(port)
        
    def ActionOutputEvent(self, output_event, **kwargs):
        self.all_objects.append(output_event)
        
    def ActionAssignment(self, assignment, **kwargs):
        self.all_objects.append(assignment)
        
    def ActionAlias(self, alias, **kwargs):
        self.all_objects.append(alias)
        
    def ActionODE(self,ode, **kwargs):
        self.all_objects.append(ode)
        
    def ActionCondition(self, condition, **kwargs):
        self.all_objects.append(condition)
        
    def ActionOnCondition(self, on_condition, **kwargs):
        self.all_objects.append(on_condition)
        
    def ActionOnEvent(self, on_event, **kwargs):
        self.all_objects.append(on_event)
