"""Fixed exogenous six-reset AB/BA calendar; indices are zero based."""


def plan(index, variant):
    """Return (role, physical plan), varying only reset 5 by exposure policy."""
    if type(index) is not int or index < 0 or variant not in ('natural', 'forced'):
        raise ValueError('invalid schedule input')
    cycle = (('AB', 'first_p'), ('BA', 'second_r'), ('AB', 'first_third'),
             ('BA', 'first_p'), ('AB', 'candidate' if variant == 'natural' else 'second_r'),
             ('BA', 'first_third'))
    return cycle[index % len(cycle)]


def prior_plan(index, certified):
    """Use the fixed AB candidate only on AB calendar roles when certified."""
    if type(certified) is not bool:
        raise ValueError('certified must be bool')
    role, _ = plan(index, 'natural')
    return role, 'candidate' if certified and role == 'AB' else 'baseline'
