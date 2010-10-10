class Condition(object):

    element_name = "condition"
    n = 0
    
    def __init__(self, cond, name=None):

        from nineml.abstraction_layer.cond_parse import cond_parse

        self.cond = cond
        self.name = name or ("Condition%d" % Condition.n)
        Condition.n += 1
        
        self.names, self.funcs, self.python_func = cond_parse(cond)

        if self.names==set() and self.funcs==set():
            val = self.python_func()
            if val==False:
                raise ValueError, "condition is never true."
            else:
                assert val==True
                raise ValueError, "condition is always true."

    def __repr__(self):
        return "Condition('%s')" % (self.cond)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return reduce(and_, (self.name == other.name,
                             self.cond == other.cond))


##     def to_xml(self):
##         return E(self.element_name,
##                  E("conditional-inline", self.cond),
##                  name=self.name)
                 
##     @classmethod
##     def from_xml(cls, element):
##         assert element.tag == NINEML+cls.element_name
##         math = element.find(NINEML+"conditional-inline").text
##         return cls(math, name=element.get("name"))



def cond_to_obj(cond_str):

    if isinstance(cond_str,Condition):
        return cond_str

    return Condition(cond_str.strip())

    
