
from nineml.abstraction_layer import math_namespace

class RegimeElement(object):
    """ Base class for all things that can be elements of a regime """
    pass


class Expression(RegimeElement):

    def parse_rhs(self):
        """ parses and checks validity of rhs """
        from nineml.abstraction_layer.expr_parse import expr_parse

        self.names, self.funcs, self.python_func = expr_parse(self.rhs)

        # Parser now does this check
        
        #undef_funcs = funcs.difference(math_namespace.functions)
        #if undef_funcs:
        #    funcs.difference(math_namespace.functions)
        #    raise ValueError, "In expression '%s', undefined functions: %s" % \
        #          (e.as_expr(),repr(list(undef_funcs)))


class Binding(Expression):
    # this is very similar to Assignment. Maybe we don't need it.
    # EM: In the context of NEST and GPU code generation, bindings make sense:
    #  They are constants, i.e. a binding which takes state vars or ports in rhs
    #  should throw an exception.
    #  Users can specify them manually for eash of short hands,
    #  but automatic symbolic symplification of the expressions may well produce
    #  new bindings which can be pre-calculated outside of the integration loop.
    #
    #  Let's keep this in mind, and keep Bindings as we move forward!
    
    element_name = "binding"
    
    def __init__(self, name, value):

        self.name = name
        self.value = value

        if name in math_namespace.symbols:
            raise ValueError, "binding '%s' redefines math symbols (such as 'e','pi')" % self.as_expr()

        self.parse_rhs()

        if name in self.names:
            raise ValueError, "Binding expression '%s': may not self reference." % name



    @property
    def rhs(self):
        return self.value

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.name == other.name and self.value == other.value

    def to_xml(self):
        return E(self.element_name,
                 E("math-inline", self.value),
                 name=self.name)

    def as_expr(self):
        return "%s := %s" % (self.name, self.value)

    @classmethod
    def from_xml(cls, element):
        return cls(element.get("name"), element.find(NINEML+"math-inline").text)




            
class Equation(Expression):
    pass
        

class ODE(Equation):
    """
    Represents a first-order, ordinary differential equation.
    """
    element_name = "ode"
    n = 0
    
    def __init__(self, dependent_variable, indep_variable, rhs, name=None):
        self.dependent_variable = dependent_variable
        self.indep_variable = indep_variable
        self.rhs = rhs

        if self.dependent_variable in math_namespace.symbols:
            raise ValueError, "ODE '%s' redefines math symbols (such as 'e','pi')" % self.as_expr()

        self.name = name or ("ODE%d" % ODE.n)
        ODE.n += 1
        self.parse_rhs()


        
    def __repr__(self):
        return "ODE(d%s/d%s = %s)" % (self.dependent_variable,
                                      self.indep_variable,
                                      self.rhs)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return reduce(and_, (self.name == other.name,
                             self.dependent_variable == other.dependent_variable,
                             self.indep_variable == other.indep_variable,
                             self.rhs == other.rhs))


    @property
    def lhs(self):
        return "d%s/d%s" % (self.dependent_variable, self.indep_variable)
    
    def as_expr(self):
        return "d%s/d%s = %s" % (self.dependent_variable,
                                 self.indep_variable,
                                 self.rhs)

    def to_xml(self):
        return E(self.element_name,
                 E("math-inline", self.rhs),
                 name=self.name,
                 dependent_variable=self.dependent_variable,
                 independent_variable = self.indep_variable)

    @classmethod
    def from_xml(cls, element):
        assert element.tag == NINEML+cls.element_name
        rhs = element.find(NINEML+"math-inline").text
        return cls(element.get("dependent_variable"),
                   element.get("independent_variable"),
                   rhs,
                   name=element.get("name"))
    

class Assignment(Equation):
    element_name = "assignment"
    n = 0
    
    @property
    def rhs(self):
        return self.expr

    def __init__(self, to, expr, name=None):
        self.to = to
        self.expr = expr
        self.name = name or ("Assignment%d" % Assignment.n)

        if self.to in math_namespace.symbols:
            raise ValueError, "Assignment '%s' redefines math symbols (such as 'e','pi')" % self.as_expr()

        Assignment.n += 1

        self.parse_rhs()

    def self_referencing(self):
        """ Returns True if the assignment is of the form U = f(U,...), otherwise False"""
        return self.to in self.names

    def __repr__(self):
        return "Assignment('%s', '%s')" % (self.to, self.expr)

    def as_expr(self):
        return "%s = %s" % (self.to,
                            self.expr)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return reduce(and_, (self.name == other.name,
                             self.to == other.to,
                             self.expr == other.expr))

    def to_xml(self):
        return E(self.element_name,
                 E("math-inline", self.expr),
                 name=self.name,
                 to=self.to)
                 
    @classmethod
    def from_xml(cls, element):
        assert element.tag == NINEML+cls.element_name
        math = element.find(NINEML+"math-inline").text
        return cls(to=element.get("to"), name=element.get("name"),
                   expr=math)



class Inplace(Equation):
    element_name = "inplace"
    n = 0
    op_name_map = {'+=':'Add','-=':'Sub','*=':'Mul','/=':'Div'}

    op = "+="
    
    @property
    def rhs(self):
        return self.expr

    def __init__(self, to, op, expr, name=None):
        
        self.to = to
        self.op = op

        # catch invalid ops and give the user feedback
        try:
            self.op_name = self.op_name_map[op]
        except KeyError:
            raise ValueError, "Unsupported inplace operation '%s', supported ops: %s" %(self.op_name, str(self.op_name_map))
        
        self.expr = expr

        if self.to in math_namespace.symbols:
            raise ValueError, "Inplace '%s' operates on math symbols (such as 'e','pi')" % self.as_expr()

        self.name = name or ("Inplace%s%d" % (self.op_name,Inplace.n))
        Inplace.n += 1
        self.parse_rhs()


    def __repr__(self):
        return "Inplace('%s', '%s', '%s')" % (self.to,self.op,self.expr)

    def as_expr(self):
        return "%s %s %s" % (self.to,self.op, self.expr)


    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return reduce(and_, (self.name == other.name,
                             self.to == other.to,
                             self.op == other.op,
                             self.expr == other.expr))

    def to_xml(self):
        return E(self.element_name,
                 E("math-inline", self.expr),
                 name=self.name,
                 to=self.to, op=self.op)
                 
    @classmethod
    def from_xml(cls, element):
        assert element.tag == NINEML+cls.element_name
        math = element.find(NINEML+"math-inline").text
        return cls(to=element.get("to"), op=element.get("op"), expr=math,
                   name=element.get("name"))

# factories for Inplace ops
def InplaceAdd(to,expr):
    return Inplace(to,'+=',expr)

def InplaceSub(to,expr):
    return Inplace(to,'-=',expr)

def InplaceMul(to,expr):
    return Inplace(to,'*=',expr)

def InplaceDiv(to,expr):
    return Inplace(to,'/=',expr)


def expr_to_obj(s, name = None):
    """ Construct nineml objects from expressions """ 

    import re

    # Is our job already done?
    if isinstance(s,Expression):
        return s

    # strip surrounding whitespace
    s = s.strip()

    # re for an expression -> groups into lhs, op, rhs
    p_eqn = re.compile(r"(?P<lhs>[a-zA-Z_]+[a-zA-Z_0-9]*(/?[a-zA-Z_]+[a-zA-Z_0-9]*)?)\s*(?P<op>[+\-*/:]?=)\s*(?P<rhs>.*)")
    # re for lhs for ODE
    p_ode_lhs = re.compile(r"(?:d)([a-zA-Z_]+[a-zA-Z_0-9]*)/(?:d)([a-zA-Z_]+[a-zA-Z_0-9]*)")


    m = p_eqn.match(s)
    if not m:
        raise ValueError, "Not a valid nineml expression: %s" % s

    # get lhs, op, rhs
    lhs, op, rhs = [m.group(x) for x in ['lhs','op','rhs']]

    # do we have an ODE?
    m = p_ode_lhs.match(lhs)
    if m:
        if op!="=":
            raise ValueError, "ODE lhs, but op not '=' in %s" % s

        dep_var = m.group(1)
        indep_var = m.group(2)
        return ODE(dep_var,indep_var,rhs, name = name)

    # Do we have an Inplace op?
    if op in Inplace.op_name_map.keys():
        return Inplace(lhs,op,rhs, name = name)

    # Do we have an assignment?
    if op=="=":
        return Assignment(lhs,rhs, name = name)

    # Do we have a binding?
    if op==":=":
        return Binding(lhs,rhs)

        
    # If we get here, what do we have?
    raise ValueError, "Cannot map expr '%s' to a nineml Expression" % s


