"""Re-deciding stored records against a later policy.

The tests below are built from the real descriptor corpus and real decisions
produced by the reference gate, then re-decided against a *modified* copy of
the policy. Nothing here hand-writes a receipt: a receipt that was not produced
by the gate would not prove that the gate's own output carries enough to
re-decide from, which is the entire claim.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from support import corpus

from croissant_policy import recheck
from croissant_policy.parse import to_descriptor
from croissant_policy.reference import load_gate


def _native_to_descriptor(native: dict):
    descriptor_mod, _, _ = load_gate()
    return descriptor_mod.Descriptor.from_json(native)


def _action_node(native: dict, name: str) -> dict:
    for node in native.get("permissibleActions", []):
        if node.get("name") == name:
            return node
    raise KeyError(name)


def _permit_context(native: dict, action: str) -> dict:
    """A context that satisfies every condition of the action."""
    ctx = {}
    for name, spec in _action_node(native, action)["conditions"].items():
        if not isinstance(spec, dict):
            ctx[name] = spec
        elif "min" in spec:
            ctx[name] = spec["min"]
        elif "max" in spec:
            ctx[name] = spec["max"]
        elif "in" in spec:
            ctx[name] = spec["in"][0]
        elif "equals" in spec:
            ctx[name] = spec["equals"]
        elif "present" in spec:
            ctx[name] = "something"
    return ctx


def _permit_record(gate, native: dict, action: str) -> dict:
    """A real permit record for `action`, produced by the reference gate."""
    d = _native_to_descriptor(native)
    requires = _action_node(native, action).get("requiresState")
    if requires:
        d = replace(d, state=requires[0])
    decision = gate.authorize(d, action, _permit_context(native, action))
    assert decision.verdict == gate.PERMIT, "fixture must permit first"
    return decision.as_record()


def _first_conditioned_action(native: dict):
    """A dataset/action whose policy actually has conditions to tighten."""
    for node in native.get("permissibleActions", []):
        if node.get("conditions"):
            return node.get("name"), node
    return None, None


class RecheckTest(unittest.TestCase):
    def setUp(self):
        _, _, self.gate = load_gate()
        self.corpus = corpus()
        for native in self.corpus.values():
            action, spec = _first_conditioned_action(native)
            if action:
                self.native = native
                self.action = action
                self.spec = spec
                break
        else:  # pragma: no cover - corpus would have to change
            self.skipTest("no conditioned action in the corpus")

    def _permit_context(self, native, action):
        return _permit_context(native, action)

    def _decide(self, native, action, ctx):
        d = _native_to_descriptor(native)
        requires = _action_node(native, action).get("requiresState")
        if requires:
            d = replace(d, state=requires[0])
        return self.gate.authorize(d, action, ctx)

    # ---- the core claim ------------------------------------------------

    def test_identical_policy_leaves_every_decision_unchanged(self):
        ctx = self._permit_context(self.native, self.action)
        decision = self._decide(self.native, self.action, ctx)
        record = decision.as_record()

        descriptor = _native_to_descriptor(self.native)
        requires = _action_node(self.native, self.action).get("requiresState")
        if requires:
            descriptor = replace(descriptor, state=requires[0])

        result = recheck.recheck_one(record, descriptor)
        self.assertEqual(result.outcome, recheck.UNCHANGED)
        self.assertEqual(result.then, result.now)

    def test_tightening_a_threshold_newly_refuses(self):
        """The finding the tool exists to surface."""
        name, spec = next(
            (n, s)
            for n, s in self.spec["conditions"].items()
            if isinstance(s, dict) and "min" in s
        )
        ctx = self._permit_context(self.native, self.action)
        decision = self._decide(self.native, self.action, ctx)
        self.assertEqual(decision.verdict, self.gate.PERMIT, "fixture must permit first")
        record = decision.as_record()

        tightened = copy.deepcopy(self.native)
        _action_node(tightened, self.action)["conditions"][name] = {"min": spec["min"] + 1000}
        descriptor = _native_to_descriptor(tightened)

        result = recheck.recheck_one(record, descriptor)
        self.assertEqual(result.outcome, recheck.NEWLY_REFUSED)
        self.assertEqual(result.then, self.gate.PERMIT)
        self.assertEqual(result.now, self.gate.REFUSE)
        self.assertTrue(result.reasons, "a newly-refused decision must say why")

    def test_loosening_a_threshold_newly_permits(self):
        name, spec = next(
            (n, s)
            for n, s in self.spec["conditions"].items()
            if isinstance(s, dict) and "min" in s
        )
        ctx = self._permit_context(self.native, self.action)
        ctx[name] = spec["min"] - 1
        decision = self._decide(self.native, self.action, ctx)
        self.assertEqual(decision.verdict, self.gate.REFUSE, "fixture must refuse first")
        record = decision.as_record()

        loosened = copy.deepcopy(self.native)
        _action_node(loosened, self.action)["conditions"][name] = {"min": 0}
        descriptor = _native_to_descriptor(loosened)

        result = recheck.recheck_one(record, descriptor)
        self.assertEqual(result.outcome, recheck.NEWLY_PERMITTED)

    # ---- the honest limit ----------------------------------------------

    def test_a_new_condition_is_indeterminable_not_guessed(self):
        """The record cannot answer a question it was never asked."""
        ctx = self._permit_context(self.native, self.action)
        record = self._decide(self.native, self.action, ctx).as_record()

        extended = copy.deepcopy(self.native)
        _action_node(extended, self.action)["conditions"]["reviewedBy"] = {"present": True}
        descriptor = _native_to_descriptor(extended)

        result = recheck.recheck_one(record, descriptor)
        self.assertEqual(result.outcome, recheck.INDETERMINABLE)
        self.assertIn("reviewedBy", result.missing)
        self.assertIsNone(result.now, "an indeterminable recheck must not invent a verdict")

    def test_absent_observed_value_is_a_fact_not_a_gap(self):
        """`observed: null` says the fact was absent, which is information.

        This is the distinction INDETERMINABLE rests on: a condition that was
        checked and found missing is re-decidable; one never checked is not.
        """
        name = next(iter(self.spec["conditions"]))
        record = self._decide(self.native, self.action, {}).as_record()
        checked = {c["name"] for c in record["conditionsChecked"]}
        if name not in checked:
            self.skipTest("gate short-circuited before conditions")
        self.assertIn(name, recheck.facts(record))
        result = recheck.recheck_one(record, _native_to_descriptor(self.native))
        self.assertNotEqual(result.outcome, recheck.INDETERMINABLE)

    def test_state_refusal_carries_no_conditions(self):
        """A refusal that short-circuits is less re-decidable, and says so."""
        requires = _action_node(self.native, self.action).get("requiresState")
        if not requires:
            self.skipTest("action has no state precondition")
        descriptor = replace(
            _native_to_descriptor(self.native), state="A_STATE_THAT_IS_NOT_DECLARED"
        )
        decision = self.gate.authorize(descriptor, self.action, {})
        self.assertEqual(decision.verdict, self.gate.REFUSE)
        record = decision.as_record()
        self.assertEqual(record["conditionsChecked"], [])
        result = recheck.recheck_one(record, _native_to_descriptor(self.native))
        self.assertEqual(result.outcome, recheck.INDETERMINABLE)

    # ---- archive plumbing ----------------------------------------------

    def test_round_trip_through_a_jsonl_archive(self):
        ctx = self._permit_context(self.native, self.action)
        record = self._decide(self.native, self.action, ctx).as_record()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.jsonl"
            path.write_text(json.dumps(record) + "\n\n", encoding="utf-8")
            loaded = recheck.load_archive(path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["action"], self.action)

    def test_malformed_archive_line_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text("{not json}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                recheck.load_archive(path)

    def test_summary_counts_every_outcome(self):
        results = [
            recheck.Recheck("d", "a", None, recheck.UNCHANGED, "PERMIT", "PERMIT"),
            recheck.Recheck("d", "a", None, recheck.NEWLY_REFUSED, "PERMIT", "REFUSE"),
        ]
        totals = recheck.summary(results)
        self.assertEqual(totals["total"], 2)
        self.assertEqual(totals["counts"][recheck.NEWLY_REFUSED], 1)
        self.assertEqual(len(totals["newlyRefused"]), 1)


if __name__ == "__main__":
    unittest.main()


class ReportTest(unittest.TestCase):
    """The document, and the two things that must not blur."""

    def setUp(self):
        from croissant_policy import report

        self.report = report
        self.results = [
            recheck.Recheck("d", "a", None, recheck.UNCHANGED, "PERMIT", "PERMIT"),
            recheck.Recheck(
                "d", "a", None, recheck.NEWLY_REFUSED, "PERMIT", "REFUSE",
                reasons=("x: 1 violates >= 2",),
            ),
        ]
        self.totals = recheck.summary(self.results)

    def test_review_and_impact_differ_in_claim_not_arithmetic(self):
        review = self.report.render(self.results, self.totals, mode=recheck.REVIEW)
        impact = self.report.render(self.results, self.totals, mode=recheck.IMPACT)
        self.assertNotEqual(review, impact)
        for doc in (review, impact):
            self.assertIn("| Unchanged | 1 |", doc)
        # impact must not present past work as a finding
        self.assertIn("not a deviation list", impact)
        self.assertIn("were correctly admitted", impact)
        self.assertNotIn("not a deviation list", review)

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            self.report.render(self.results, self.totals, mode="sideways")

    def test_coverage_is_reported_before_the_counts(self):
        doc = self.report.render(self.results, self.totals)
        self.assertLess(doc.index("Coverage"), doc.index("## Result"))

    def test_low_coverage_marks_the_counts_as_a_lower_bound(self):
        results = self.results + [
            recheck.Recheck(
                "d", "a", None, recheck.INDETERMINABLE, "PERMIT", None,
                missing=("reviewedBy",),
            )
        ] * 8
        totals = recheck.summary(results)
        self.assertFalse(totals["dependable"])
        doc = self.report.render(results, totals)
        self.assertIn("lower bound", doc)
        self.assertIn("reviewedBy", doc)

    def test_full_coverage_is_dependable(self):
        self.assertTrue(self.totals["dependable"])
        self.assertEqual(self.totals["coverage"], 1.0)

    def test_coverage_of_empty_archive_is_not_a_division_by_zero(self):
        self.assertEqual(recheck.coverage([]), 1.0)


class CliModeTest(unittest.TestCase):
    """Impact mode must never break a build."""

    def setUp(self):
        _, _, self.gate = load_gate()
        self.corpus = corpus()

    def _archive_and_policy(self, tmp: Path):
        native = self.corpus["qc-report"]
        d = _native_to_descriptor(native)
        rec = self.gate.authorize(
            d, "aggregate", {"reportFormat": "multiqc", "minInputStages": 3}
        ).as_record()
        self.assertEqual(rec["verdict"], self.gate.PERMIT)
        archive = tmp / "a.jsonl"
        archive.write_text(json.dumps(rec) + "\n", encoding="utf-8")

        tightened = copy.deepcopy(native)
        _action_node(tightened, "aggregate")["conditions"]["minInputStages"] = {"min": 9}
        policy = tmp / "p.json"
        policy.write_text(json.dumps(tightened), encoding="utf-8")
        return archive, policy

    def test_review_exits_nonzero_impact_exits_zero(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            archive, policy = self._archive_and_policy(tmp)
            import contextlib, io

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                review = recheck.main([str(archive), "--policy", str(policy), "--mode", "review"])
                impact = recheck.main([str(archive), "--policy", str(policy), "--mode", "impact"])
        self.assertEqual(review, 1, "review mode is a CI gate and must fail")
        self.assertEqual(impact, 0, "impact mode estimates a change and must not fail a build")

    def test_report_file_is_written(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            archive, policy = self._archive_and_policy(tmp)
            out = tmp / "assessment.md"
            import contextlib, io

            with contextlib.redirect_stdout(io.StringIO()):
                recheck.main(
                    [str(archive), "--policy", str(policy), "--mode", "impact", "--report", str(out)]
                )
            doc = out.read_text(encoding="utf-8")
        self.assertIn("Policy change impact assessment", doc)
        self.assertIn("minInputStages", doc)


class ScopeTest(unittest.TestCase):
    """A policy decides the records it governs, and no others.

    The defect these cover was invisible on a single-dataset example and
    appeared on the first real archive: a receipt store holds every dataset's
    decisions, and the whole 285-record corpus put to one dataset's policy
    reported thirty fabricated findings at 100% coverage.
    """

    def setUp(self):
        _, _, self.gate = load_gate()
        self.corpus = corpus()
        conditioned = [
            (name, native)
            for name, native in self.corpus.items()
            if _first_conditioned_action(native)[0]
        ]
        if len(conditioned) < 2:
            self.skipTest("need two conditioned datasets in the corpus")
        (self.mine_id, self.mine), (self.other_id, self.other) = conditioned[:2]
        self.mine_action = _first_conditioned_action(self.mine)[0]
        self.other_action = _first_conditioned_action(self.other)[0]
        self.descriptor = _native_to_descriptor(self.mine)

    def _mixed(self):
        mine = _permit_record(self.gate, self.mine, self.mine_action)
        other = _permit_record(self.gate, self.other, self.other_action)
        return mine, other

    def test_a_foreign_record_is_set_aside(self):
        mine, other = self._mixed()
        governed, foreign = recheck.partition([mine, other], self.descriptor)
        self.assertEqual([recheck.record_dataset_id(r) for r in governed], [self.mine_id])
        self.assertEqual([recheck.record_dataset_id(r) for r in foreign], [self.other_id])

    def test_deciding_a_foreign_record_anyway_fabricates_a_finding(self):
        """Why partition() exists, asserted rather than described.

        The other dataset's action is not declared by this policy, so the gate
        refuses it -- correctly, for a request that was never made. Read as a
        recheck that is a permitted decision turned refusal: a deviation that
        did not happen.
        """
        _, other = self._mixed()
        result = recheck.recheck_one(other, self.descriptor)
        self.assertEqual(result.outcome, recheck.NEWLY_REFUSED)
        self.assertEqual(
            result.dataset_id,
            self.other_id,
            "a mislabelled record must still carry its own id, not the policy's",
        )

    def test_a_record_naming_no_dataset_is_set_aside(self):
        mine, _ = self._mixed()
        anonymous = {k: v for k, v in mine.items() if k != "datasetId"}
        self.assertIsNone(recheck.record_dataset_id(anonymous))
        governed, foreign = recheck.partition([anonymous], self.descriptor)
        self.assertEqual(governed, [])
        self.assertEqual(len(foreign), 1)

    def test_summary_counts_and_names_what_it_set_aside(self):
        mine, other = self._mixed()
        governed, foreign = recheck.partition([mine, other], self.descriptor)
        totals = recheck.summary(recheck.recheck_all(governed, self.descriptor), foreign)
        self.assertEqual(totals["total"], 1)
        self.assertEqual(totals["outOfScope"], 1)
        self.assertEqual(totals["outOfScopeDatasets"], {self.other_id: 1})

    def test_coverage_is_not_diluted_by_records_out_of_scope(self):
        """Coverage answers "could the governed records be decided", and the
        set-aside ones are not a gap in that answer."""
        mine, other = self._mixed()
        governed, foreign = recheck.partition([mine, other], self.descriptor)
        totals = recheck.summary(recheck.recheck_all(governed, self.descriptor), foreign)
        self.assertEqual(totals["coverage"], 1.0)

    def _cli(self, argv):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = recheck.main(argv)
        return code, buf.getvalue()

    def _write(self, tmp, records, native):
        archive = tmp / "a.jsonl"
        archive.write_text(
            "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
        )
        policy = tmp / "p.json"
        policy.write_text(json.dumps(native), encoding="utf-8")
        return archive, policy

    def test_cli_decides_only_the_governed_half_of_a_mixed_archive(self):
        mine, other = self._mixed()
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            archive, policy = self._write(tmp, [mine, other], self.mine)
            code, out = self._cli([str(archive), "--policy", str(policy), "--mode", "impact"])
        self.assertEqual(code, 0)
        self.assertIn("rechecked 1 stored decision", out)
        self.assertIn("set aside", out)
        self.assertIn(self.other_id, out)

    def test_cli_refuses_an_archive_it_governs_nothing_in(self):
        """Neither a pass nor an estimate: a mismatched invocation."""
        _, other = self._mixed()
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            archive, policy = self._write(tmp, [other], self.mine)
            review, out = self._cli([str(archive), "--policy", str(policy), "--mode", "review"])
            impact, _ = self._cli([str(archive), "--policy", str(policy), "--mode", "impact"])
        self.assertEqual(review, 2)
        self.assertEqual(impact, 2, "impact mode must not report an estimate of nothing")
        self.assertIn("none of the 1 record", out)

    def test_cli_empty_archive_is_not_a_mismatch(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            archive, policy = self._write(tmp, [], self.mine)
            code, _ = self._cli([str(archive), "--policy", str(policy), "--mode", "review"])
        self.assertEqual(code, 0)


class GroupingTest(unittest.TestCase):
    """Repetition is counted, not printed.

    An archive records the same decision on every task of every replicate. The
    real corpus turns one tightened threshold into ninety identical lines, and
    a document nobody can read is not evidence.
    """

    def _refusals(self, n, reason="x: 1 violates >= 2"):
        return [
            recheck.Recheck(
                "d", "trim", None, recheck.NEWLY_REFUSED, "PERMIT", "REFUSE",
                reasons=(reason,),
            )
        ] * n

    def test_identical_findings_collapse_to_one_entry_with_a_count(self):
        groups = recheck.grouped(self._refusals(90))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][1], 90)

    def test_different_reasons_stay_separate(self):
        groups = recheck.grouped(self._refusals(3) + self._refusals(1, "y: absent"))
        self.assertEqual(len(groups), 2)
        self.assertEqual([n for _, n in groups], [3, 1], "largest group first")

    def test_grouping_loses_no_decisions(self):
        results = self._refusals(90) + self._refusals(4, "y: absent")
        self.assertEqual(sum(n for _, n in recheck.grouped(results)), len(results))

    def test_indeterminable_groups_on_the_missing_facts(self):
        undecided = [
            recheck.Recheck(
                "d", "qc", None, recheck.INDETERMINABLE, "PERMIT", None,
                missing=("assay",),
            )
        ] * 128
        groups = recheck.grouped(undecided, by="missing")
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][1], 128)

    def test_the_report_states_each_finding_once_with_its_count(self):
        from croissant_policy import report

        results = self._refusals(90)
        doc = report.render(results, recheck.summary(results), mode=recheck.IMPACT)
        self.assertEqual(doc.count("x: 1 violates >= 2"), 1)
        self.assertIn("| 90 |", doc)

    def test_the_report_names_what_it_set_aside(self):
        from croissant_policy import report

        results = self._refusals(2)
        totals = recheck.summary(results, [{"datasetId": "qc-report"}] * 30)
        doc = report.render(results, totals, mode=recheck.IMPACT)
        self.assertIn("`qc-report` (30)", doc)
        self.assertIn("Records set aside", doc)


class DocumentLeakTest(unittest.TestCase):
    """The assessment is handed out, so it must not carry the host's paths.

    Same class of defect as the absolute paths that reached the public examples
    and the material staged for MLCommons, and the same fix: the file's name
    identifies it, its location identifies only the machine that emitted it.
    """

    def setUp(self):
        from croissant_policy import report

        self.report = report
        self.results = [
            recheck.Recheck("d", "a", None, recheck.UNCHANGED, "PERMIT", "PERMIT"),
        ]
        self.totals = recheck.summary(self.results)

    def _doc(self, archive):
        return self.report.render(self.results, self.totals, archive=archive)

    def test_the_archive_is_named_not_located(self):
        doc = self._doc("/run/media/chelex/DRIVE/receipts/decisions.jsonl")
        self.assertIn("decisions.jsonl", doc)
        self.assertNotIn("/run/media", doc)

    def test_no_absolute_path_survives_into_the_document(self):
        doc = self._doc("/tmp/somewhere/deep/archive.jsonl")
        offenders = [
            line for line in doc.splitlines()
            if "/" in line and any(part.startswith("/") for part in line.split("`"))
        ]
        self.assertEqual(offenders, [], "an absolute path reached the document")

    def test_an_unnamed_archive_still_renders(self):
        self.assertIn("(stdin)", self._doc(""))
