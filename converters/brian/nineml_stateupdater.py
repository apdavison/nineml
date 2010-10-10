
import brian.stateupdater
import nineml.abstraction_layer as nineml


def regime_equations(regime, level=1, **kwargs):
    """Return Brian Equations object from a Regime"""

    eqns = []
    for e in regime.equations:
        eqn = e.as_expr()
        # bindings need ':=' replaced with '='
        if isinstance(e, nineml.Binding):
            eqn.replace(':=','=')
        # TODO: handling units
        eqns.append(eqn+' : 1')
    return brian.equations.Equations(eqns,level=level,**kwargs)


class FakeNeuronGroup(object):
    
    def __init__(self, P, remap):

        self.P = P
        self.remap = remap
        self.clock = P.clock

        self._S = 

    @property
    def _S(self):
        pass
    
    @property
    def _dS(self):
        pass

    def state_(self,var):
        return self.P._S[self.remap[var]]

# clock
# ._dS
# ._S
# .state_(var)



class NineMLStateUpdater(brian.stateupdater.StateUpdater):
    """
    Creates a StateUpdater from a NineML component.

    Each regime of the component is given a Stat

    """

    def __init__(self, nineml_component,
                 regime_updater_cls=brian.stateupdater.NonlinearStateUpdater, **kwargs):
        '''
        Creates a StateUpdater from a nineml Component

        Each regime is given an updater of type regime_updater_cls
        '''
        if not isinstance(nineml_component,nineml.Component)
        self.component = nineml_component
        clock = kwargs.get("clock")
        self.base_regime = kwargs.get("base_regime")
        if not isinstance(self.base_regime, nineml.Regime):
            raise ValueError, "Please provide kwarg 'base_regime' for NineML StateUpdater"

        # need to assign regimes an index, so convert to a list
        self.regimes = list(self.component.regimes)

        # create a sub-updater for equations for
        # each regime
        self.sub_up_map = {}
        self.regime2id_map = {}
        for i,r in enumerate(self.regimes):
            # level=2 should get us to the namespace calling this constructer
            # TODO:for compile=True ... sub-regimes don't get correct _S, _dS for __call__ ...
            self.sub_up_map[r]=regime_updater_cls(regime_equations(r,level=2),compile=False,**kwargs)
            self.regime2id_map[r]=i
            

        # TODO: state vars for spike output, spike input only if ports
        # spike_output must be first as it is the threshold variable.
        self.special_state_vars = ["__9ml_spike_output","__9ml__regime","__9ml__spike_input"]
        self.state_vars = self.special_state_vars+list(self.component.state_variables)+\
                          list(self.component.bound_variables)

        # assign place in state vector for each state var
        self.sv_map = {}
        i=0
        for sv in self.state_vars:
            self.sv_map[i]=sv
            i+=1

            
    def rest(self, P):
        '''
        Sets the variables at rest.
        '''
        self.sub_up_map[self.base_regime].rest(P)
        # set regime state
        self._S[1,:]=float(self.regime2id_map[self.base_regime])

    def __call__(self, P):
        '''
        Updates the state variables.
        Careful here: always use the slice operation for affectations.
        P is the neuron group.
        '''
        
        # different neurons can be in different regimes
        # need to pick them out somehow

    def __repr__(self):
        return 'Leaky integrate-and-fire StateUpdater'

    def __len__(self):
        '''
        Number of state variables
        '''
        return len(self.state_vars)

