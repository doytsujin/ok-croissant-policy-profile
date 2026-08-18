"""Running both authorities on one request, and recording the disagreement.

The caller-side plane and the data-side descriptor each decide the same request
from what they know. This module runs both and produces one receipt.

Precedence is the open question. Neither vendor material nor the descriptor
literature says which authority wins when they disagree, or whether the
disagreement is recorded at all, so the rules are enumerated here rather than
assumed:

    deny-overrides    permit only if both permit          (conjunction)
    caller-overrides  the caller's verdict is final       (a control plane that is the only enforcement point)
    data-overrides    the dataset's verdict is final      (a gate with no identity model)
    caller-only       the dataset is never consulted      (today's agent control plane)
    data-only         the caller is never consulted       (today's admission gate)

The last two are not really precedence rules. They are the two products that
exist, written in the same vocabulary so that the cost of running only one of
them can be counted instead of argued about.

The agreement class is separate from the verdict and is the part worth keeping.
"Both refused" and "only the dataset refused" produce the same outcome under
deny-overrides and mean entirely different things to whoever reads the log: the
second one is a request the caller's own governance would have let through.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .caller import DATASET_KEY, CallerScope
from .parse import to_descriptor
from .reference import load_gate

DENY_OVERRIDES = "deny-overrides"
CALLER_OVERRIDES = "caller-overrides"
DATA_OVERRIDES = "data-overrides"
CALLER_ONLY = "caller-only"
DATA_ONLY = "data-only"

PRECEDENCE_RULES = (
    DENY_OVERRIDES,
    CALLER_OVERRIDES,
    DATA_OVERRIDES,
    CALLER_ONLY,
    DATA_ONLY,
)

AGREE_PERMIT = "AGREE_PERMIT"
AGREE_REFUSE = "AGREE_REFUSE"
CALLER_ONLY_REFUSED = "CALLER_ONLY_REFUSED"
DATA_ONLY_REFUSED = "DATA_ONLY_REFUSED"


@dataclass
class JointDecision:
    action: str
    caller_id: str
    dataset_id: str
    caller: object = None
    data: object = None
    agreement: str = ""
    verdicts: dict = field(default_factory=dict)

    @property
    def disagreed(self) -> bool:
        return self.agreement in (CALLER_ONLY_REFUSED, DATA_ONLY_REFUSED)

    def effective(self, rule: str) -> str:
        return self.verdicts[rule]

    def unsafe_under(self, rule: str) -> bool:
        """Does this rule admit a request one of the authorities refused?

        This is the whole quantity the experiment is about. A rule that never
        does this is safe in the only sense either authority would recognise;
        one that does is a governance gap with a count attached.
        """
        _, _, gate_mod = load_gate()
        if self.verdicts[rule] != gate_mod.PERMIT:
            return False
        return gate_mod.REFUSE in (self.caller.verdict, self.data.verdict)

    def as_record(self, rule: str = DENY_OVERRIDES) -> dict:
        """One receipt, two authorities.

        Both sides' conditions are carried, including the passing ones and
        including the side that permitted. A joint record that keeps only the
        refusing half cannot show that the other authority was consulted, and
        showing that is the reason to have a joint record rather than two.
        """
        def side(decision) -> dict:
            record = decision.as_record()
            record.pop("evalMicros", None)
            return record

        return {
            "action": self.action,
            "callerId": self.caller_id,
            "datasetId": self.dataset_id,
            "agreement": self.agreement,
            "precedence": rule,
            "verdict": self.verdicts[rule],
            "verdictsByPrecedence": dict(self.verdicts),
            "caller": side(self.caller),
            "data": side(self.data),
        }


def decide(
    scope: CallerScope,
    doc: dict,
    action: str,
    context: dict,
    *,
    data_descriptor=None,
    caller_descriptor=None,
) -> JointDecision:
    """Evaluate one request against both authorities.

    The caller's context is the request context plus the dataset's *name*: an
    agent control plane knows which dataset it is being pointed at and can scope
    on that. It is not given the dataset's state, because that is precisely what
    does not travel with the caller, and handing it over would model a product
    that does not exist.

    Both descriptors can be passed in already translated. A long-lived gate
    translates each once and reuses it, and timing the conjunction against
    single-sided decisions is only a like-for-like comparison when both sides
    are in the same regime -- otherwise the conjunction is charged for document
    parsing that the baseline was not.
    """
    _, _, gate_mod = load_gate()

    if data_descriptor is None:
        data_descriptor = to_descriptor(doc)
    if caller_descriptor is None:
        caller_descriptor = scope.to_descriptor()
    dataset_id = data_descriptor.dataset_id

    caller_context = dict(context)
    caller_context.setdefault(DATASET_KEY, dataset_id)

    caller_decision = gate_mod.authorize(caller_descriptor, action, caller_context)
    data_decision = gate_mod.authorize(data_descriptor, action, context)

    caller_ok = caller_decision.permitted
    data_ok = data_decision.permitted
    if caller_ok and data_ok:
        agreement = AGREE_PERMIT
    elif not caller_ok and not data_ok:
        agreement = AGREE_REFUSE
    elif not caller_ok:
        agreement = CALLER_ONLY_REFUSED
    else:
        agreement = DATA_ONLY_REFUSED

    permit, refuse = gate_mod.PERMIT, gate_mod.REFUSE
    verdicts = {
        DENY_OVERRIDES: permit if (caller_ok and data_ok) else refuse,
        CALLER_OVERRIDES: caller_decision.verdict,
        DATA_OVERRIDES: data_decision.verdict,
        CALLER_ONLY: caller_decision.verdict,
        DATA_ONLY: data_decision.verdict,
    }

    return JointDecision(
        action=action,
        caller_id=scope.caller_id,
        dataset_id=dataset_id,
        caller=caller_decision,
        data=data_decision,
        agreement=agreement,
        verdicts=verdicts,
    )
