"""
Python module for reading 9ML abstraction layer files in XML format.

Copyright Andrew P. Davison, Eilif B. Muller, 2010 # if you edit this file, add your name here
"""


from operator import and_
from nineml import __version__
import re
import copy

from nineml.cache_decorator import cache_decorator as cache
from nineml.abstraction_layer import math_namespace
from nineml import helpers
from nineml.abstraction_layer.expressions import *
from nineml.abstraction_layer.conditions import *
from nineml.abstraction_layer.ports import *
from nineml.abstraction_layer.cond_parse import cond_parse
from nineml.abstraction_layer.expr_parse import expr_parse
from nineml.abstraction_layer.xmlns import *



class UnimplementedError(RuntimeError):
    pass

def dot_escape(s):

    dot_escape_table = {
    "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;",
    ">": "&gt;",
    "<": "&lt;",
    "(": "&#40;",
    ")": "&#41;",
    }

    return "".join(dot_escape_table.get(c,c) for c in s)


class Reference(object):
    
    def __init__(self, cls, name):
        self.cls = cls
        self.name = name
        assert name!=None, "Got reference to name=None."
    def get_ref(self):
        """ return self """
        return self

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.cls == other.cls and self.name == other.name

    def __repr__(self):
        return "Reference(%s, name='%s')" % (self.cls.__name__, self.name)

# This is a reference to the only regime that transitions to this regime
# The concept is used for the On function, so that a standalone do
# Can return to the previous regime on completion.
# It is for syntactic sugar, and requires no additional concepts in the XML ...

        
class Regime(RegimeElement):
    """A regime is something that can be joined by a transition.

    This is an Abstract base class.  Union and Sequence are subclasses for the user.
    This class does not define and element_name so it cannot be written to XML.

    """
    n = 0
    
    def __init__(self, *nodes, **kwargs):
        """A node may either be an Equation or a Regime.""" 
        self.name = kwargs.get("name")
        if self.name is None:
            self.name = "Regime%d" % Regime.n
        Regime.n += 1

        nodes = map(expr_to_obj,nodes)

        # user can define transitions emanating from this
        # regime
        t = kwargs.get('transitions')
        if t:
            self.transitions=set(t)
        else:
            self.transitions=set()

        events = kwargs.get('events')
        if events:
            # handle only one event more gracefully
            if isinstance(events,Event):
                events = (events,)
            events=set(events)
        else:
            events=set()

        # Events are transitions, union the two sets
        self.transitions = self.transitions.union(events) 

        for node in nodes:
            self.add_node(node)
                
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        
        sort_key = lambda node: node.name
        return reduce(and_, (self.name == other.name, 
                             sorted(self.nodes, key=sort_key) == sorted(other.nodes, key=sort_key),
                             sorted(self.transitions, key=sort_key) == sorted(other.transitions, key=sort_key)))

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.name)

    def _add_node_to_collection(self, node):
        raise UnimplementedError, "Regime is doesn't know how to collect nodes, use subclass Union or Sequence."

    def get_ref(self):
        """ Returns a reference to this regime """
        return Reference(Regime, self.name)


    def add_node(self, node):

        if isinstance(node, (RegimeElement)):
            if isinstance(node, Assignment) and node.self_referencing():
                raise ValueError, "Assignments in Regimes may not self reference.  Only in Events."
        else:
            raise ValueError, "Invalid node '%s' in Regime.add_node. " % repr(node)

        self._add_node_to_collection(node)



    def add_transition(self, t):
        """ Add a transition to the regime"""
        if isinstance(t, Transition):
            if t.from_ is None:
                t.from_=self
            if not t.from_==self:
                print "WARNING: transition whose from_ was reassigned to the Regime."
            assert t.to!=self, "transition '%s' assigns Regime '%s' to itself!." % (t.name, self.name)
        else:
            assert isinstance(t,Reference) and t.cls==Transition, "Regime.add_transition(t): t must be Transition or Reference(Transition, name)"
        
        self.transitions.add(t)

    @property
    def neighbors(self):
        """ Get all regimes we transition to """
        return [t.to for t in self.transitions_with_target]

    @property
    def transitions_with_target(self):
        """ Get all transitions which define a target"""
        for t in self.transitions:
            if t.to:
                yield t

    def get_transition_to(self,to):
        """ Returns transition if Regime transitions to Regime 'to', otherwise None """

        for t in self.transitions:
            if t.to == to:
                return t
        else:
            return None

    def neighbor_map(self):
        """Returns a map of neighbors to transitions, from self

        Such that neighbor_map[neighbor] is the transition from self to neighbor """

        d = {}
        for t in self.transitions:
            # transition might have no target
            if t.to:
                d[t.to] = t

        return d

    @property
    def equations(self):
        """
        Yields all the equations contained within this Regime or any of its
        children.

        As nodes_filter is a generator, so too is this function.
        """
        return self.nodes_filter(lambda x: isinstance(x,Equation))

    @property
    def bindings(self):
        """
        Yields all the bindings contained within this Regime or any of its
        children.

        As nodes_filter is a generator, so too is this function.
        """
        return self.nodes_filter(lambda x: isinstance(x,Binding))

    @property
    def odes(self):
        """
        Yields all odes in the regime or any of its children.
        
        As nodes_filter is a generator, so too is this function.
        """
        return self.nodes_filter(lambda x: isinstance(x,ODE))


    def nodes_filter(self, filter_func):
        """
        Yields all the nodes contained within this Regime or any of its
        children for which filter_func yields true.

        Example of valid filter_func:
        filter_func = lambda x: isinstance(x, Equation)
        
        """
        for node in self.nodes:
            if filter_func(node):
                yield node
            elif isinstance(node, Regime):
                for cnode in node.nodes_filter(filter_func):
                    yield cnode

    def regimes_in_graph(self, regimes_set=None):
        """ Set of all regimes by walking through transition graph
        starting with this regime

        regimes_set is None when called by user,
        but used in recursion to identify routes we've already been
        
        """

        # If we are starting out, create a regimes_set
        if regimes_set is None:
            regimes_set = set()

        # Add self to regimes set
        regimes_set.add(self)

        # Go through transitions of this regime
        for t in self.transitions:
            # if found a new regime, have it add itself and
            # all its new regimes recursively
                
            # transitions may have to=None
            if t.to:
                assert not isinstance(t.to, Reference), "Unresolved references.  Is this Regime part of a Component?"

                assert isinstance(t.to,Regime), "Regime graph contains a non-Regime: %s" % str(t.to)

                if t.to not in regimes_set:
                    t.to.regimes_in_graph(regimes_set)
                
        return regimes_set

    def to_xml(self):
        kwargs = {}
        return E(self.element_name,
                 name=self.name,
                 *[node.to_xml() for node in self.nodes],
                 **kwargs)

    @classmethod
    def from_xml(cls, element):
        assert element.tag == NINEML+cls.element_name
        nodes = []
        kwargs = {}
        tag_class_map = {}
        name = element.get("name")
        for node_cls in (ODE, Assignment, Sequence, Union, Binding):
            tag_class_map[NINEML+node_cls.element_name] = node_cls
        for elem in element.iterchildren():
            node_cls = tag_class_map[elem.tag]
            tmp = node_cls.from_xml(elem)
            nodes.append(tmp)

        if name is not None:
            kwargs["name"] = name
            
        return cls(*nodes, **kwargs)


    def dot_content(self,level=0):

        # template & namespace
        ns = {'level':level}
        t = '<tr><td align="left" port="n_%(level)d_%(node_id)s">%(node_content)s</td></tr>\\\n\t\t'

        # header
        level_pad = ''.join(['  ']*level)
        ns['node_id'] = 'root'
        ns['node_content'] = level_pad+self.__class__.__name__+dot_escape('(name="%s"'%self.name)
        contents = [t % ns]

        node_id = 0
        for n in self.nodes:
            if isinstance(n,Regime):
                contents +=[n.dot_content(level+1)]
            else:
                # render node contents
                ns['node_id'] = str(node_id)
                node_id+=1
                ns['node_content'] = level_pad+'  '+dot_escape(n.as_expr())
                contents += [t % ns]

        # footer
        ns['node_id'] = 'tail'
        ns['node_content'] = level_pad+dot_escape(')')
        contents += [t % ns]

        return ''.join(contents)


class Sequence(Regime):
    element_name = "sequence"
    
    def __init__(self, *nodes, **kwargs):
        raise ValueError, "The Sequence object has been discontinued."
        self.nodes = []
        Regime.__init__(self, *nodes, **kwargs)

    def _add_node_to_collection(self, node):
        self.nodes.append(node)
    

        
class Union(Regime):
    element_name = "union"
    
    def __init__(self, *nodes, **kwargs):
        self.nodes = set()
        Regime.__init__(self, *nodes, **kwargs)

    def _add_node_to_collection(self, node):
        self.nodes.add(node)


def On(condition, do=None,to=None):
    """ returns new Transition which goes to 'to' if condition is True.

    Equivalent to :
    Transition(from_=None,to=Reference(Regime,to),condition=condition)

    'On' is syntactic sugar for defining light regimes.

    The resulting Transition has from_=None, so it must be added to a Regime
    to be activated.
    
    """
    if do:
        # handle one do op more gracefully
        if isinstance(do,(str,EventPort)):
            do = (do,)
        return Transition(*do,to=to,condition=condition)
    else:
        return Transition(to=to,condition=condition)
        

class Transition(object):
    element_name = "transition"
    n = 0
    
    def __init__(self, *nodes, **kwargs):
        """
        Event/Transition

        nodes = is a collection of assignments, inplace operations, or EventPorts of mode="send"
                which happen when the condition triggers.
                
        'condition' may be be a string like "V>10" or an EventPort of mode="recv"

        from_ = Regime to transition from
        to = Regime to transition to (maybe None)
        name = name for transition, maybe None, in which case one is assigned.

        """

        #from_=None, to=None, condition=None, name=None
        from_ = kwargs.get("from_")
        to = kwargs.get("to")
        condition = kwargs.get("condition")
        name = kwargs.get("name")

        # handle to from_ as string
        if isinstance(to,str):
            to=Reference(Regime,to)
        if isinstance(from_,str):
            from_=Reference(Regime,from_)

        # check types
        if isinstance(from_, (Regime, type(None))):
            pass
        elif isinstance(from_, Reference) and issubclass(from_.cls,Regime):
            pass
        else:
            raise ValueError, "expected Regime, Reference(Regime,name), name as str, or None for kwarg 'from_', got '%s'" % repr(from_)
            
        if isinstance(to, (Regime, type(None))):
            pass
        elif isinstance(to, Reference) and issubclass(to.cls,Regime):
            pass
        else:
            raise ValueError, "expected Regime, Reference(Regime,name), name as str, or None for kwarg 'to', got '%s'" % repr(to)
            
        self.from_ = from_
        self.to = to

        if isinstance(condition,EventPort):
            self.condition=condition
            if condition.mode!="recv":
                raise ValueError, "Transition/Event condition as an EventPort: EventPort mode must be 'recv'"
        else:
            # cond_to_obj does type checking
            self.condition = cond_to_obj(condition)

        if not self.condition:
            raise ValueError, "Transition condition may not be none"

        self.name = name or ("Transition%d" % Transition.n)
        Transition.n += 1

        self.nodes = []
        for node in nodes:
            self.add_node(node)

    def add_node(self, node):
        if isinstance(node,str):
            node = expr_to_obj(node)
        
        if isinstance(node, (Assignment, Inplace)):
            self.nodes.append(node)
        elif isinstance(node, EventPort):
            if node.mode=="recv":
                raise ValueError, "EventPort node '%s' must have mode='send'." % repr(node)
            self.nodes.append(node)
        else:
            raise ValueError, "Event node '%s' not of valid type." % repr(node)

    @property
    def event_ports(self):
        """ Yields all EventPorts in the Event"""
        if isinstance(self.condition,EventPort):
            yield self.condition
        for p in self.nodes_filter(lambda x: isinstance(x,EventPort)):
            yield p

    @property
    def equations(self):
        """ Yields all equations in the Event"""
        return self.nodes_filter(lambda x: isinstance(x,Equation))

    def nodes_filter(self, filter_func):
        """
        Yields all the nodes contained within this Regime or any of its
        children for which filter_func yields true.

        Example of valid filter_func:
        filter_func = lambda x: isinstance(x, Equation)
        
        """
        for node in self.nodes:
            if filter_func(node):
                yield node
        

    def __repr__(self):
        return "Transition(from %s to %s if %s)" % (self.from_, self.to, self.condition)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        # to prevent infinite loop, one should olny check if
        # the references from_,to are equal, not the objects

        try:
            from_eq = self.from_.get_ref() == other.from_.get_ref()
        except AttributeError:
            # one is None, so it is OK to check equality of the objects 
            from_eq = self.from_==other.from_

        try:
            to_eq = self.to.get_ref() == other.to.get_ref()
        except AttributeError:
            # one is None, so it is OK to check equality of the objects
            to_eq = self.to==other.to

            
        sort_key = lambda node: node.name

        return reduce(and_, (self.name == other.name,
                             from_eq,
                             to_eq,
                             self.condition == other.condition,
                             sorted(self.nodes, key=sort_key) == sorted(other.nodes, key=sort_key)))

    def to_xml(self):
        attrs = {"name": self.name}
        args = []

        # TODO this duality of EventPorts and Conditions
        # should be cleaned up
        if isinstance(self.condition,EventPort):
            args+=[E("condition-on-event-port", self.condition.to_xml())]
        else:
            attrs["condition"] = self.condition.cond

            
        if self.to:
            attrs['to'] = self.to.name
        if self.from_:
            attrs['from'] = self.from_.name
        
        return E(self.element_name, *args+[node.to_xml() for node in self.nodes], **attrs)

##     def resolve(self, regimes):
##         for attr_name in ("from_", "to"):
##             ref = getattr(self, attr_name)
##             if isinstance(ref, Reference):
##                 resolved_obj = regimes[ref.name]
##                 assert isinstance(resolved_obj, ref.cls)
##                 setattr(self, attr_name, resolved_obj)

##     def resolve_condition(self):
##         if self.condition in ('true', 'false'):
##             return eval(self.condition.title())
##         else:
##             return self.condition


    @classmethod
    def from_xml(cls, element):
        assert element.tag == NINEML+cls.element_name
        from_ = element.get("from")
        if from_:
            from_ = Reference(Regime,from_ )
        to = element.get("to")
        if to:
            to = Reference(Regime,to )

        # Handling condition="V>Vth", but also EventPort as condition
        condition = element.get("condition")
        on_event_port = element.findall(NINEML+"condition-on-event-port")
        if not condition and not on_event_port:
            raise ValueError, "Transition did not define condition attribute, or condition-on-event-port element"
        if condition and on_event_port:
            raise ValueError, "Transition defined both condition attribute, and condition-on-event-port element"
        if len(on_event_port)>1:
            raise ValueError, "multiple condition-on-event-port elements"
        if on_event_port:
            oep = on_event_port[0]
            ep_elems = oep.findall(NINEML+EventPort.element_name)
            if len(ep_elems)>1:
                raise ValueError, "condition-on-event-port defined multiple event-port elements"
            condition = EventPort.from_xml(ep_elems[0])

            
        name = element.get("name")
        nodes = []
        tag_class_map = {}
        for node_cls in (EventPort, Assignment, Inplace):
            tag_class_map[NINEML+node_cls.element_name] = node_cls
        for elem in element.iterchildren():
            if elem.tag==NINEML+"condition-on-event-port": continue
            node_cls = tag_class_map[elem.tag]
            tmp = node_cls.from_xml(elem)
            nodes.append(tmp)
        
        return cls(*nodes,from_=from_, to=to, condition=condition, name=name)

Event = Transition

class Component(object):
    element_name = "component"
    
    def __init__(self, name, parameters = [], regimes = [], transitions = [], events=[],
                 ports = [], bindings = []):
        """
        Regime graph should not be edited after contructing a component

        *TODO*: if the user maintains a ref to a regime in regimes,
        etc. they can violate this.  Code generators will need to
        query regimes, transtions, so we can't privatize self
        attributes {_regimes, _transitions, _regime_map,
        _transition_map} by prefixing with "_".

        We should do some privatizing for regimes, transitions, or do a deepcopy here.
        We could make regimes and transitions tuples, and expose only read-only apis in
        Regime and Transition class.  Then the _map could be made a sort of ImmutableDict.
        *END TODO*


        Specifying Regimes & Transitions
        --------------------------------

        The user passed 'regimes' and 'transitions'|'events' should contain true objects, i.e.
        they may not contain References. 
        
        Options to the user:
        
        1) provide both 'regimes' and 'transitions' (references will be resolved)
        2) provide 'regimes' only (in which case there must be no unresolved references),
        3) provide 'transitions' only (in which case there must be at least
           one transition in the model, and no unresolved references),

        transitions and events are synonymous.

        """

        self.name = name

        # check for empty component, we do not support inplace building of a component.
        if not regimes and not transitions and not events:
            raise ValueError, "Component constructor needs at least 'regimes'"+\
                  "or 'transitions' or 'events' to build component graph."

        # add to transitions from regimes
        # get only true transition objects (not references) from regimes
        # these will be added to transition map in next step
        trans_objects = [t for r in regimes for t in r.transitions if isinstance(t,Transition)]
        # model with no transitions is indeed allowed.

        trans_refs = [t for t in transitions if isinstance(t,Reference)]
        assert not trans_refs, "Component constructor: kwarg 'transitions' may not"+\
               "contain references."

        transitions = set(transitions).union(set(events))
        transitions.update(trans_objects)

        # add to regimes from transitions
        # get only true regime objects (not references) from transitions
        # these will be added to regime map in next step
        regime_objects = [r for t in transitions for r in (t.to,t.from_) if isinstance(r,Regime)]

        if not regimes:
            assert regime_objects, "Cannot build regime set: User supplied only Transitions "+\
                   "to Component constructor, but all 'to','from_' attributes are references!"
        regime_refs = [r for r in regimes if isinstance(r,Reference)]
        assert not regime_refs, "Component constructor: kwarg 'regimes' may not contain references."

        regimes = set(regimes)
        regimes.update(regime_objects)

        # build regime map
        self.regime_map = {}
        for r in regimes:
            if self.regime_map.has_key(r.name):
                raise ValueError, "Regime collection has Regimes with colliding names."
            self.regime_map[r.name] = r

        # build transitions map
        self.transition_map = {}
        for t in transitions:
            if self.transition_map.has_key(t.name):
                raise ValueError, "Transition collection has Transitions with colliding names."
            self.transition_map[t.name] = t
               
        # store final regime and transition sets for this component
        self.regimes = set(regimes)
        self.transitions = set(transitions)

        # We have extracted all implicit knowledge of graph members, proceed to
        # resolve references.
        self.resolve_references()


        # check that there is an island regime only if there is only 1 regime
        island_regimes = set([r for r in self.regimes if not list(r.transitions_with_target) and\
                              not self.get_regimes_to(r)])
        if island_regimes:
            assert len(self.regimes)==1, "User Error: Component contains island regimes"+\
                   "and more than one regime."

        # Allow strings for bindings, map using expr_to_obj
        # Eliminate duplicates

        # This should not be a set, but a list!
        # We resolve later colliding bindings
        bindings = map(expr_to_obj,set(bindings))
        for r in self.regimes:
            bindings+=list(r.bindings)
        #self.bindings = bindings

        # build bindings map
        bindings_map = {}
        for b in bindings:
            assert isinstance(b, Binding), "Received invalid binding."
            if b.name in bindings_map and b.as_expr()!=bindings_map[b.name].as_expr():
                raise ValueError, "Multiple non-equal bindings on '%s' " % b.name
            bindings_map[b.name] = b
        self.bindings_map = bindings_map

        # We should not do this for the user
        #self.backsub_bindings()

        # check bindings only have static parameters and functions on rhs
        self.check_binding_expressions()

        # check we aren't redefining math symbols (like e,pi)
        self.check_non_parameter_symbols()

        # now would be a good time to backsub expressions
        # but we should not do this for the user.
        #self.backsub_equations()

        # Up till now, we've inferred parameters
        # Now let's check what the user provided
        # is consistant and finally set self.parameters
        if parameters:
            if self.user_parameters!=set(parameters):
                raise ValueError, "Declared parameter list %s does not match inferred parameter list %s." % (str(sorted(parameters)),str(sorted(self.user_parameters)))

        self.parameters = self.user_parameters
        for p in ports:
            if not isinstance(p,AnalogPort):
                raise ValueError, "Component ports attribute can contain only AnalogPort objects.  EventPorts go in Event conditions(recv) and Event nodes (send)"
            # may only write to user_parameters
            if p.mode=="recv" and p.symbol not in self.user_parameters:
                raise ValueError, "'recv' AnalogPorts may target parameters, but not binding symbols, ODE lhs vars, or lhs of Assignments/Inplace ops."

            if p.symbol not in self.non_parameter_symbols and p.symbol not in self.user_parameters:
                raise ValueError, "'send' AnalogPorts must source from a defined symbol."
                

        self.analog_ports = ports
        
        
        # we should check that parameters is correct
        # even better, we could auto-generate parameters

    def get_regimes_to(self,regime):
        """ Gets as a list all regimes that transition to regime"""
        
        return [t.from_ for t in self.transitions if t.to==regime]


    def backsub_bindings(self):
        """ This function finds bindings with undefined functions, and uses
        the binding_map to attempt to resolve them. """

        # build binding dependency tree
        # and perform substitution, recursively
        def build_and_resolve_bdtree(b):
            _bd_tree = {}
            for f in b.missing_functions:
                if f in self.bindings_map:
                    _bd_tree[f] = build_and_resolve_bdtree(self.bindings_map[f])
                    # resolve (lower level is already resolved now) 
                    b.substitute_binding(self.bindings_map[f])
                    # re-calc functions
                    b.parse_rhs()
                else:
                    raise ValueError, "binding '%s' calls unresolvable functions." % b.as_expr()
            return _bd_tree  

        bd_tree = {}
        for b in self.bindings_map.itervalues():
            bd_tree[b.name] = build_and_resolve_bdtree(b)

    def backsub_equations(self):
        """ this function finds all undefined functions in equations, and uses
        the binding_map to resolve them """

        for e in self.equations:
            for f in e.missing_functions:
                if f in self.bindings_map:
                    e.substitute_binding(self.bindings_map[f])
                else:
                    raise ValueError, "Equation '%s' calls unresolvable functions." % e.as_expr()

            e.parse_rhs()

        # There should be no missing functions now.
        assert [f for e in self.equations for f in e.missing_functions] == []

            
    def resolve_references(self):
        """ Uses self.regimes_map and self.transitions_map to resolve references in self.regimes and self.transitions"""

        # resolve transition from_=None to parent regime
        for r in self.regimes:
            for t in r.transitions:
                if t.from_==None:
                    t.from_=r

        # resolve regime references in transitions:
        for t in self.transitions:
            for attr in ('to','from_'):
                ref = t.__getattribute__(attr)
                # transition defines no to,from
                if ref==None: continue
                if not isinstance(ref,Regime):
                    assert isinstance(ref,Reference) and issubclass(ref.cls,Regime), "Expected Regime reference or Regime"
                    t.__setattr__(attr,self.regime_map[ref.name])

        # resolve transition references in regimes

        for r in self.regimes:
            for t in r.transitions:
                if isinstance(t, Transition ): continue
                assert isinstance(t,Reference) and r.cls==Transition, "Expected Transition reference or Transition" 
                r.transitions.remove(t)
                r.transitions.add(self.transition_map[t.name])

        # add transitions to regimes:
        for t in self.transitions:
            t.from_.add_transition(t)
            


    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        sort_key = lambda node: node.name

        return reduce(and_, (self.name == other.name,
                             self.parameters == other.parameters,
                             sorted(self.transitions, key=sort_key) == sorted(other.transitions, key=sort_key),
                             sorted(self.regimes, key=sort_key) == sorted(other.regimes, key=sort_key),
                             sorted(self.bindings, key=sort_key) == sorted(other.bindings, key=sort_key)))

   
    @property
    def equations(self):
        #for transition in self.transitions:
        #    for regime in transition.from_, transition.to:
        for r in self.regimes:
            for t in r.transitions:
                for eq in t.equations:
                    yield eq
            for eq in r.equations:
                yield eq

    @property
    def event_ports(self):
        """ return all event ports in regime events"""
        for t in self.transitions:
            for ep in t.event_ports:
                    yield ep



    @property
    def conditions(self):
        """ Returns all conditions """
        # TODO events
        for t in self.transitions:
            yield t.condition

    @property
    def bindings(self):
        return self.bindings_map.itervalues()


    def check_binding_expressions(self):
        """ Bound symbols (which are static when running the model)
        can depend only on 'user parameters' (which are static when running the model)

        This parses the binding rhs expressions to verify this is so.
        """

        params = self.user_parameters
        
        for binding in self.bindings:
            # It is up to the user to call backsub at the appropriate time,
            # or implement other facilities for resolving user defined functions
            # bindings ...
            # There for the following check is removed:
            #for f in binding.missing_functions:
            #    raise ValueError, "Binding '%s' calls undefined function '%s' " % str(binding.as_expr(),f)

            non_param_names = self.non_parameter_symbols.intersection(binding.names)
            # may reference other bindings
            non_param_names = non_param_names.difference(self.bindings_map.iterkeys())
            if non_param_names:
                raise ValueError, "Binding symbols referencing variables is illegal: %s" % str(non_param_names)

    def check_non_parameter_symbols(self):
        """ Check that non-parameters symbols are not conflicting
        with math_namespace symbols """
        if self.non_parameter_symbols.intersection(math_namespace.symbols)!=set():
            raise ValueError, "Non-parameters symbols (variables and bound symbols) may "+\
                  "not redefine math symbols (such as 'e','pi')"
            
                

    @property
    @cache
    def user_parameters(self):
        """ User parameters for the component. """
        # TODO: cache once determined
        # compare to the parameters lists declared by the user 

        # parse the math blocks


        symbols = set([])
        for e in self.equations:
            symbols.update(e.names)

        # now same for conditions
        for c in self.conditions:
            symbols.update(c.names)

        # now same for bindings
        for b in self.bindings:
            symbols.update(b.names)


        symbols = symbols.difference(self.non_parameter_symbols)
        symbols = symbols.difference(math_namespace.symbols)
        return symbols.difference(math_namespace.reserved_symbols)

                 
    @property
    @cache
    def non_parameter_symbols(self):
        """ All bindings, assignment and inplace left-hand-sides, plus X for ODE dX/dt = ... """ 
        # TODO: cache once determined
        symbols = set([])
        symbols.update(self.variables)
        symbols.update(self.bound_symbols)
        return symbols

    @property
    @cache
    def variables(self):
        symbols = set([])
        symbols.update(self.integrated_variables)
        symbols.update(self.assigned_variables)
        symbols.update(self.independent_variables)
        return symbols

    @property
    @cache
    def state_variables(self):
        symbols = set([])
        symbols.update(self.integrated_variables)
        symbols.update(self.assigned_variables)
        return symbols


    @property
    @cache
    def bound_symbols(self):
        # TODO: cache once determined
        """ Return symbols which are subject to bindings (static assignments)"""
        # construct set of keys (bound symbols)
        statics = set(self.bindings_map)

        # check user is not writing to bound variables
        if statics.intersection(self.integrated_variables)!=set():
            raise ValueError, "Error: user bound symbols which appear on lhs of ODEs"
        if statics.intersection(self.assigned_variables)!=set():
            raise ValueError, "Error: user bound symbols which appear on lhs of Assignments"+\
                  "and Inplace OPs"
        
        return statics

    @property
    @cache
    def assigned_variables(self):
        """ All assignment and inplace lhs' (which may also be ODE integrated variables),
        but not bindings (which are not variables, but static) """

        # TODO: cache once determined
        variables = set([])
        for equation in self.equations:
            if isinstance(equation, (Assignment,Inplace)):
                variables.add(equation.to)
        return variables

    @property
    @cache
    def independent_variables(self):
        """ All X for ODE dY/dX """
        # TODO: cache once determined
        variables = set([])
        for r in self.regimes:
            for eq in r.odes:
                variables.add(eq.indep_variable)
        return variables

    
    @property
    @cache
    def integrated_variables(self):
        """ All X for ODE dX/dt """
        # TODO: cache once determined
        variables = set([])
        for equation in self.equations:
            if isinstance(equation, ODE):
                variables.add(equation.dependent_variable)
        return variables
    
    def to_xml(self):
        elements = [E.parameter(name=p) for p in self.parameters] + \
                   [p.to_xml() for p in self.analog_ports] +\
                   [r.to_xml() for r in self.regimes] + \
                   [b.to_xml() for b in self.bindings] +\
                   [t.to_xml() for t in self.transitions]
        attrs = {"name": self.name}
        return E(self.element_name, *elements, **attrs)
       
    @classmethod
    def from_xml(cls, element):
        """
        Parse an XML ElementTree structure and return a Component instance.
        
        `element` - should be an ElementTree Element instance.
        
        See:
            http://docs.python.org/library/xml.etree.elementtree.html
            http://codespeak.net/lxml/
        """
        assert element.tag == NINEML+cls.element_name
        parameters = [p.get("name") for p in element.findall(NINEML+"parameter")]
        bindings = [Binding.from_xml(b) for b in element.findall(NINEML+Binding.element_name)] 

        regimes = []
        for regime_cls in (Sequence, Union):
            for e in element.findall(NINEML+regime_cls.element_name):
                regimes.append(regime_cls.from_xml(e))

        analog_ports = []
        for port_cls in (AnalogPort,):
            for e in element.findall(NINEML+port_cls.element_name):
                analog_ports.append(port_cls.from_xml(e))

        transitions = [Transition.from_xml(t) for t in element.findall(NINEML+Transition.element_name)]

        # allocate new component
        new_comp = cls(element.get("name"), parameters, regimes=regimes, transitions=transitions, bindings=bindings, ports=analog_ports)

        return new_comp


    def write(self, file):
        """
        Export this model to a file in 9ML XML format.

        file is filename or file object.
        """
        doc = E.nineml(self.to_xml(), xmlns=nineml_namespace)
        etree.ElementTree(doc).write(file, encoding="UTF-8",
                                     pretty_print=True, xml_declaration=True)

    def to_dot(self,out, show_contents=True):
        """ Write a DOT graph representation of component

        http://en.wikipedia.org/wiki/DOT_language

        Convert a dot file to an image using, i.e.:
          dot -Tsvg spike_generator.dot -o spike_generator.svg
          dot -Tpng spike_generator.png -o spike_generator.png

        """

        # if out is a str, make a file
        if isinstance(out,str):
            out = file(out,'w')

        out.write("""digraph "NineML Component '%s'" {\n""" % self.name)

        out.write('\toverlap = "scale";\n')

        regime_id = dict([(kv[0],i) for i,kv in enumerate(self.regime_map.iteritems())])


        if show_contents:

            out.write('\tgraph [fontsize=30 labelloc="t" label="" splines=true overlap=false rankdir = "LR"];\n\tratio = auto\n');
            props = 'style = "filled, bold" penwidth = 1 fillcolor = "white" fontname = "Courier New" shape = "Mrecord" '
            # regime template
            t_regime = '\t"%(node)s" [ style = "filled, bold" penwidth = 1 fillcolor = "white" fontname = "Courier New" '+\
                       'shape = "Mrecord" \\\n\t\tlabel =<<table border="0" cellborder="0" cellpadding="3" bgcolor="white">'+\
                       '<tr><td bgcolor="black" \\\n\t\talign="center" colspan="2"><font color="white">'+\
                       '%(regime_name)s</font></td></tr>\\\n\t\t%(contents)s</table>> ];\n ' 
            # to fill: node, regime_name, contents
            ns = {}

            for r in self.regimes:
                
                ns['node'] = "regime_%d" % regime_id[r.name]
                ns['regime_name'] = r.name
                ns['contents'] = r.dot_content()
                out.write(t_regime % ns)
        
        for t in self.transitions:
            if show_contents:
    
                out.write('\tregime_%d -> regime_%d [label="%s @ %s"];\n' % (regime_id[t.from_.name], regime_id[t.to.name],
                                                                   t.name.encode('utf-8'), t.condition.encode('utf-8')))
            else:
                out.write('\tregime_%d -> regime_%d [label="%s"];\n' % (regime_id[t.from_.name], regime_id[t.to.name],
                                                                   t.name.encode('utf-8'), t.condition.encode('utf-8')))

        out.write('}')


        
        
        
#def resolve_reference(ref, *where):
#        val = None
#        for D in where:
#            if ref in D:
#                val = D[ref]
#                break
#        if val:
#            return val
#        else:
#            raise Exception("Can't resolve reference %s" % ref)

def parse(filename):
    doc = etree.parse(filename)
    root = doc.getroot()
    assert root.nsmap[None] == nineml_namespace
    component = root.find(NINEML+"component")
    return Component.from_xml(component)

