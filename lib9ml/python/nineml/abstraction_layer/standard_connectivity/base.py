"""
temporary implementation of "standard" connectivity library. Should probably integrate with connection_generator
"""


from nineml.abstraction_layer.components import BaseComponentClass


class ComponentClass(BaseComponentClass):

    def __init__(self, name, parameters=None, connection_rule=None):
        super(ComponentClass, self).__init__(name, parameters)
        self._connection_rule = connection_rule


