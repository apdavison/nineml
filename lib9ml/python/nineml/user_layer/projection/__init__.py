from operator import and_
from ..base import BaseULObject, E, NINEML
from ..utility import check_tag
import nineml.user_layer.population
from ..components import BaseComponent
from ..dynamics import SynapseType, ConnectionType
import nineml.user_layer.containers
from ...abstraction_layer.connection_generator import *
from .cg_closure import alConnectionRuleFromURI
from .utilities import *
from .grids import *


class Projection(BaseULObject):

    """
    A collection of connections between two Populations.

    If the populations contain spiking nodes, this is straightforward. If the
    populations contain groups, it is not so obvious. I guess the
    interpretation is that connections are made to all the populations within
    all the groups, recursively.
    """
    element_name = "Projection"
    defining_attributes = ("name", "source", "target", "rule",
                           "synaptic_response", "connection_type",
                           "synaptic_response_ports", "connection_ports")

    def __init__(self, name, source, target, rule, synaptic_response,
                 connection_type, synaptic_response_ports, connection_ports):
        """
        Create a new projection.

        name - a name for this Projection
        source - the presynaptic Population
        target - the postsynaptic Population
        rule - a ConnectionRule instance, encapsulating an algorithm for wiring
               up the connections.
        synaptic_response - a PostSynapticResponse instance that will be used
                            by all connections.
        connection_type - a ConnectionType instance that will be used by all
                          connections.
        synaptic_response_ports - a list of tuples (synapse_port, neuron_port)
                                  giving the ports that should be connected
                                  between post-synaptic response component and
                                  neuron component.
        connection_ports - a list of tuples (plasticity_port, synapse_port)
                           giving the ports that should be connected between
                           plasticity/connection component and post-synaptic
                           response component.
        """
        self.name = name
        self.references = {}
        self.source = source
        self.target = target
        self.rule = rule
        self.synaptic_response = synaptic_response
        self.connection_type = connection_type
        self.synaptic_response_ports = synaptic_response_ports
        self.connection_ports = connection_ports
        for name, cls_list in (('source',
                                (nineml.user_layer.population.Population,
                                 nineml.user_layer.containers.PopulationSelection)),
                               ('target',
                                (nineml.user_layer.population.Population,
                                 nineml.user_layer.containers.PopulationSelection)),
                               ('rule', (ConnectionRule,)),
                               ('synaptic_response', (SynapseType,)),
                               ('connection_type', (ConnectionType,))):
            attr = getattr(self, name)
            if isinstance(attr, cls_list):
                self.references[name] = attr.name
            elif isinstance(attr, basestring):
                setattr(self, name, None)
                self.references[name] = attr
            else:
                raise TypeError("Invalid type for %s: %s" % (name, type(attr)))

    def __eq__(self, other):
        test_attributes = ["name", "source", "target",
                           "rule", "synaptic_response", "connection_type",
                           "synaptic_response_ports", "connection_ports"]
        # to avoid infinite recursion, we do not include source or target in
        # the tests if they are Groups
        if isinstance(self.source, nineml.user_layer.containers.Network):
            test_attributes.remove("source")
        if isinstance(self.target, nineml.user_layer.containers.Network):
            test_attributes.remove("target")
        return reduce(and_, (getattr(self, attr) == getattr(other, attr)
                             for attr in test_attributes))

    def get_components(self):
        components = []
        for name in ('rule', 'synaptic_response', 'connection_type'):
            component = getattr(self, name)
            if component is not None:
                components.append(component)
        return components

    def to_xml(self):
        return E(self.element_name,
                 E.Source(E.Reference(self.source.name)),
                 E.Destination(E.Reference(self.target.name)),
                 E.Connectivity(E.Reference(self.rule.name)),
                 E.Response(E.Reference(self.synaptic_response.name)),
                 E.Plasticity(E.Reference(self.connection_type.name)),
                 E.response_ports(*[E.port_connection(port1=a, port2=b)
                                    for a, b in self.synaptic_response_ports]),
                 E.connection_ports(*[E.port_connection(port1=a, port2=b)
                                      for a, b in self.connection_ports]),
                 name=self.name)

    @classmethod
    def from_xml(cls, element, context):
        check_tag(element, cls)
        return cls(name=element.attrib["name"],
                   source=element.find(NINEML + "Source").text,
                   target=element.find(NINEML + "Destination").text,
                   rule=context.resolve_ref(element.find(NINEML + "Connectivity"),
                                            ConnectionRule),
                   synaptic_response=context.resolve_ref(
                                            element.find(NINEML + "Response"),
                                            SynapseType),
                   connection_type=context.resolve_ref(
                                           element.find(NINEML + "Plasticity"),
                                           ConnectionType),
                   synaptic_response_ports=tuple((pc.attrib["port1"],
                                                  pc.attrib["port2"])
                                                 for pc in element.find(
                                                   NINEML + "response_ports")),
                   connection_ports=tuple((pc.attrib["port1"],
                                           pc.attrib["port2"])
                                          for pc in element.find(
                                                 NINEML + "connection_ports")))

    def to_csa(self):
        if self.rule.is_csa:
            # should allow different distance functions, specified somewhere in
            # the user layer
            distance_func = _csa.euclidMetric2d
            src_geometry = self.source.positions.structure.\
                                                   to_csa()(self.source.number)
            tgt_geometry = self.target.positions.structure.\
                                                   to_csa()(self.target.number)
            distance_metric = distance_func(src_geometry, tgt_geometry)
            _csa.cset(self.rule.to_csa() * distance_metric)
        else:
            raise Exception("Connection rule does not use Connection Set "
                            "Algebra")


class ConnectionRule(BaseComponent):

    """
    Component representing an algorithm for connecting two populations of
    nodes.
    """
    abstraction_layer_module = 'connection_generator'
