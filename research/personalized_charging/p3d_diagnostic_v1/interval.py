"""Small, bounded Decimal interval arithmetic; no binary float inputs."""
from dataclasses import dataclass
from decimal import (Decimal, Context, localcontext, ROUND_FLOOR, ROUND_CEILING,
                     ROUND_HALF_EVEN, InvalidOperation, DivisionByZero, Overflow)

PRECISION = 40

def context(rounding):
    c = Context(prec=PRECISION, rounding=rounding, Emin=-999, Emax=999)
    for trap in (InvalidOperation, DivisionByZero, Overflow):
        c.traps[trap] = True
    return c


def directed(rounding, operation):
    with localcontext(context(rounding)) as c:
        value = operation(c)
    if not value.is_finite():
        raise ArithmeticError('nonfinite arithmetic')
    return value


def decimal(value):
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str):
        result = Decimal(value)
    else:
        raise TypeError('Decimal inputs must be exact decimal strings')
    if not result.is_finite():
        raise ArithmeticError('nonfinite input')
    return result


@dataclass(frozen=True)
class I:
    lo: Decimal
    hi: Decimal

    def __init__(self, lo, hi=None):
        object.__setattr__(self, 'lo', decimal(lo))
        object.__setattr__(self, 'hi', decimal(lo if hi is None else hi))
        if self.lo > self.hi:
            raise ValueError('reversed interval')

    @staticmethod
    def cast(value):
        return value if isinstance(value, I) else I(value)

    def __add__(self, other):
        other = self.cast(other)
        return I(directed(ROUND_FLOOR, lambda c: c.add(self.lo, other.lo)),
                 directed(ROUND_CEILING, lambda c: c.add(self.hi, other.hi)))

    __radd__ = __add__

    def __neg__(self):
        return I(self.hi.copy_negate(), self.lo.copy_negate())

    def __sub__(self, other):
        return self + (-self.cast(other))

    def __rsub__(self, other):
        return self.cast(other) - self

    def __mul__(self, other):
        other = self.cast(other)
        pairs = [(a, b) for a in (self.lo, self.hi) for b in (other.lo, other.hi)]
        return I(min(directed(ROUND_FLOOR, lambda c, a=a, b=b: c.multiply(a, b)) for a, b in pairs),
                 max(directed(ROUND_CEILING, lambda c, a=a, b=b: c.multiply(a, b)) for a, b in pairs))

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = self.cast(other)
        if other.lo <= Decimal('0') <= other.hi:
            raise ArithmeticError('interval division through zero')
        reciprocal = I(directed(ROUND_FLOOR, lambda c: c.divide(Decimal('1'), other.hi)),
                       directed(ROUND_CEILING, lambda c: c.divide(Decimal('1'), other.lo)))
        return self * reciprocal

    def exp(self):
        if self.lo < Decimal('-100') or self.hi > Decimal('100'):
            raise ArithmeticError('exponent outside declared safe domain')
        # Decimal.exp is correctly rounded HALF_EVEN, independent of rounding mode.
        # One adjacent representable number on each side encloses the exact value.
        lower = directed(ROUND_HALF_EVEN, lambda c: c.exp(self.lo))
        upper = directed(ROUND_HALF_EVEN, lambda c: c.exp(self.hi))
        return I(directed(ROUND_FLOOR, lambda c: c.next_minus(lower)),
                 directed(ROUND_CEILING, lambda c: c.next_plus(upper)))

    def midpoint(self):
        value = directed(ROUND_HALF_EVEN, lambda c: c.divide(c.add(self.lo, self.hi), Decimal('2')))
        if not self.lo <= value <= self.hi:
            raise ArithmeticError('midpoint escaped interval')
        return value

    def width(self):
        return directed(ROUND_CEILING, lambda c: c.subtract(self.hi, self.lo))

    def json(self):
        return [str(self.lo), str(self.hi)]


def sigmoid(x):
    return I('1') / (I('1') + (-x).exp())


def overlap(a, b):
    return max(a.lo, b.lo) <= min(a.hi, b.hi)
