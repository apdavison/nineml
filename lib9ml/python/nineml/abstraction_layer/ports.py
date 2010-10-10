
from nineml.helpers import curry

class Port(object):
    """ Base class for EventPort and AnalogPort, etc."""
    element_name = "port"
    modes = ('send','recv','reduce')
    reduce_op_map = {'add':'+', 'sub':'-', 'mul':'*', 'div':'/',
                     '+':'+', '-':'-', '*':'*', '/':'/'}

    def __init__(self, internal_symbol, mode='send', op=None):
        self.symbol = internal_symbol
        self.mode = mode
        self.reduce_op = op
        if self.mode not in self.modes:
            raise ValueError, "Port(symbol='%s')"+\
                  "specified undefined mode: '%s'" %\
                  (self.symbol, self.mode)
        if self.mode=='reduce':
            if reduce_op not in reduce_op_map.keys():
                raise ValueError, "Port(symbol='%s')"+\
                      "specified undefined reduce_op: '%s'" %\
                      (self.symbol, str(self.reduce_op))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.symbol == other.symbol and self.mode == other.mode\
               and self.reduce_op == other.reduce_op

    def __repr__(self):
        if self.reduce_op:
            return "Port(symbol='%s', mode='%s', op='%s')" % \
                   (self.symbol, self.mode, self.reduce_op)
        else:
            return "Port(symbol='%s', mode='%s')" % (self.symbol, self.mode)

    def __eq__(self, other):
        return Port.__eq__(self, other) and self.condition==other.condition

    def to_xml(self, **kwargs):
        if self.reduce_op:
            kwargs['op']=self.reduce_op
        return E(self.element_name, symbol=self.symbol,
                 mode=self.mode, **kwargs)

    #@property
    #def name(self):
    #    return self.element_name+"_"+self.symbol

    @classmethod
    def from_xml(cls,element):
        assert element.tag == NINEML+cls.element_name
        symbol = element.get("symbol")
        mode = element.get("mode")
        reduce_op = element.get("op")
        return cls(symbol,mode,reduce_op)


class AnalogPort(Port):
    """ Port which may be in a Regime """
    pass

class EventPort(Port):
    """ Port which may be in an Event """
    pass


# Syntactic sugar
SpikeOutputEvent = curry(EventPort, 'spike_output')
SpikeInputEvent = curry(EventPort, 'spike_input', mode="recv")
ReducePort = curry(AnalogPort,mode="reduce")
RecvPort = curry(AnalogPort,mode="recv")
