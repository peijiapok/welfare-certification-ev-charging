"""A deliberately conservative, exact p-only certificate for the P3c model.

The guarantee assumes the fixed P3c two-offer physical process, procurement
costs, logistic response law, persistent driver, and predictable p-probes.
It is a one-sided sequential composite test, not a full confidence set.
An r response is observable but deliberately does not enter this test.

Under the model, p > 2/3 implies the candidate's expected benefit is strictly
greater than 161/41100 credits, and its expected unmet energy is at most
1/200 kWh per deployment episode. The latter is a sufficient service bound,
not an exact maximum. The collection budget must be accounted for separately.
"""

from dataclasses import dataclass
from fractions import Fraction


ALPHA = Fraction(1, 20)
ALTERNATIVE = Fraction(22, 25)
NULL_BOUND = Fraction(2, 3)
BENEFIT_LOWER_BOUND = Fraction(161, 41100)
SERVICE_UPPER_BOUND = Fraction(1, 200)


def _validate_count(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("counts must be nonnegative integers")


def likelihoods(accepts: int, rejects: int) -> tuple[Fraction, Fraction]:
    """Return alternative likelihood and maximum likelihood over p <= 2/3.

    For no observations both likelihoods equal one. Integer powers follow
    the usual empty-product convention, including 0**0 == 1.
    """
    _validate_count(accepts)
    _validate_count(rejects)
    n = accepts + rejects
    if n == 0:
        return Fraction(1), Fraction(1)
    q = min(Fraction(accepts, n), NULL_BOUND)
    alternative = ALTERNATIVE ** accepts * (1 - ALTERNATIVE) ** rejects
    maximum_null = q ** accepts * (1 - q) ** rejects
    return alternative, maximum_null


def _strict_crossing(alternative: Fraction, maximum_null: Fraction) -> bool:
    """Test L_alt / L_null > 1/alpha without division or rounding."""
    return ALPHA * alternative > maximum_null


@dataclass(frozen=True)
class Decision:
    """Gate result; the lower bound is available only when certified."""

    p_excluded: bool
    service_sufficient: bool
    certified: bool
    benefit_strictly_above: Fraction | None


class PProbeCertificate:
    """Update from public feedback; no hidden parameter or reward is needed."""

    def __init__(self) -> None:
        self.accepts = 0
        self.rejects = 0

    def observe(self, contrast: str, accepted: bool) -> None:
        """Record a p or r response; r is intentionally ignored.

        Probe selection may depend on previous public history, but selection
        must precede the current response. This class does not choose offers.
        """
        if contrast not in ("p", "r"):
            raise ValueError("contrast must be 'p' or 'r'")
        if type(accepted) is not bool:
            raise ValueError("accepted must be a boolean")
        if contrast == "p":
            if accepted:
                self.accepts += 1
            else:
                self.rejects += 1

    def evaluate(self, service_epsilon: Fraction) -> Decision:
        """Evaluate the current prefix with an exact per-episode allowance.

        This gate is not automatically latched: a controller wishing to stop
        at the first certificate must record and act on that decision. A later
        prefix may fail even after an earlier prefix passed.
        """
        if isinstance(service_epsilon, bool) or not isinstance(
            service_epsilon, (int, Fraction)
        ):
            raise ValueError("service_epsilon must be an integer or Fraction")
        if service_epsilon < 0:
            raise ValueError("service_epsilon must be nonnegative")
        alternative, maximum_null = likelihoods(self.accepts, self.rejects)
        p_excluded = _strict_crossing(alternative, maximum_null)
        service_sufficient = service_epsilon >= SERVICE_UPPER_BOUND
        certified = p_excluded and service_sufficient
        return Decision(
            p_excluded=p_excluded,
            service_sufficient=service_sufficient,
            certified=certified,
            benefit_strictly_above=BENEFIT_LOWER_BOUND if certified else None,
        )
