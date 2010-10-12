

from nineml.abstraction_layer.xmlns import *



from nineml.abstraction_layer import math_namespace

class RegimeElement(object):
    """ Base class for all things that can be elements of a regime """
    pass


class Expression(object):

    def parse_rhs(self):
        """ parses and checks validity of rhs """
        from nineml.abstraction_layer.expr_parse import expr_parse

        self.names, self.funcs = expr_parse(self.rhs)

        # Parser now does this check
        
        #undef_funcs = funcs.difference(math_namespace.functions)
        #if undef_funcs:
        #    funcs.difference(math_namespace.functions)
        #    raise ValueError, "In expression '%s', undefined functions: %s" % \
        #          (e.as_expr(),repr(list(undef_funcs)))

    def python_func(self,namespace={}):
        """ Returns a python callable which evaluates the expression in namespace and returns the result """
        return eval("lambda %s: %s" % (','.join(self.names),self.rhs), math_namespace.namespace,namespace)


class Binding(Expression, RegimeElement):
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
    
    def __init__(self, lhs,rhs):

        import re

        self.name, self.args, self.value = Binding.parse(lhs + ":=" + rhs)

        if self.name in math_namespace.symbols:
            raise ValueError, "binding '%s' redefines math symbols (such as 'e','pi')" % self.as_expr()

        self.parse_rhs()

        # remove args from names 
        self.names.difference_update(self.args)

        if self.name in self.names:
            raise ValueError, "Binding expression '%s': may not self reference." % self.name

        if self.name in self.args:
            raise ValueError, "Binding expression '%s': function binding has argument symbol = binding symbol." % self.name

    @classmethod
    def match(cls,s):
        """ Checks the syntax of the lhs to be that of a binding
        rhs parsing is not yet performed """

        try:
            cls.parse(s)
        except ValueError:
            return False

        return True

    @classmethod
    def parse(cls,s):
        """ Determines if the lhs is a symbol binding, or function binding

        If symbol:

        return symbol, (), rhs

        If function:

        return symbol, args, rhs
        where args is a tuple of function argument symbols
        """

        import re
        
        if s.count(':=')!=1:
            raise ValueError, "Invalid binding syntax. Must contain ':=' once"

        lhs,rhs = s.split(":=")

        lhs = lhs.strip()
        rhs = rhs.strip()

        p_binding_symbol = re.compile("^[a-zA-Z_]+[a-zA-Z_0-9]*$")

        # not a function
        if p_binding_symbol.match(lhs):
            return lhs,(),rhs

        # lha matches a function?

        func_regex = r"[a-zA-Z_]+[a-zA-Z_0-9]*[ ]*\([ ]*([a-zA-Z_]+[a-zA-Z_0-9]*)([ ]*,[ ]*[a-zA-Z_]+[a-zA-Z_0-9]*)*[ ]*\)"

        p_binding_func = re.compile(func_regex)

        if not p_binding_func.match(lhs):
            raise ValueError, "Invalid binding lhs syntax '%s'. Not symbol binding, and not a function" % lhs

        symbol,rest = lhs.split("(")
        symbol = symbol.strip()

        args = rest.split(",")
        args[-1] = args[-1].replace(")","")
        args = [arg.strip() for arg in args]
        
        return symbol,tuple(args),rhs
        
    @property
    def rhs(self):
        return self.value

    @property
    def lhs(self):
        if self.args:
            return self.name+"("+", ".join(self.args)+")"
        else:
            return self.name


    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.name == other.name and self.value == other.value

    def to_xml(self):
        return E(self.element_name,
                 E("math-inline", self.value),
                 name=self.lhs)

    def as_expr(self):
        return "%s := %s" % (self.name, self.value)

    @classmethod
    def from_xml(cls, element):
        return cls(element.get("name"), element.find(NINEML+"math-inline").text)




            
class Equation(Expression):
    pass
        

class ODE(Equation, RegimeElement):
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
        from operator import and_

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
    

class Assignment(Equation, RegimeElement):
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
        from operator import and_

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
        from operator import and_

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
    if isinstance(s,(RegimeElement,Inplace)):
        return s

    # strip surrounding whitespace
    s = s.strip()

    # Do we have a binding?
    if Binding.match(s):
        lhs, rhs = [x.strip() for x in s.split(":=")]
        return Binding(lhs, rhs)

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
        
    # If we get here, what do we have?
    raise ValueError, "Cannot map expr '%s' to a nineml Expression" % s

