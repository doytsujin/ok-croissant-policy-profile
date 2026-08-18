"""Emission and parsing: the translation is exact and loses nothing quietly.

Round-tripping is not required by the profile -- a document is conforming
whether or not it came from a native descriptor. It is tested because it is the
cheapest available check that the mapping is total. If a field goes missing on
the way out, the round trip is where it shows up, rather than in a decision
record six months later that is missing a custodian.
"""

from __future__ import annotations

import copy
import json
import unittest

from support import corpus

from croissant_policy import emit, parse
from croissant_policy.vocab import CROISSANT_IRI, PROFILE_IRI


class RoundTrip(unittest.TestCase):
    def test_every_descriptor_round_trips_exactly(self):
        for name, native in corpus().items():
            with self.subTest(dataset=name):
                self.assertEqual(parse.to_native_json(emit.emit(native)), native)

    def test_the_round_trip_is_stable(self):
        for name, native in corpus().items():
            with self.subTest(dataset=name):
                once = emit.emit(native)
                twice = emit.emit(parse.to_native_json(once))
                self.assertEqual(once, twice)

    def test_provenance_keys_without_a_standard_term_are_still_carried(self):
        native = copy.deepcopy(corpus()["raw-reads"])
        native["provenance"]["ethicsApproval"] = "REB-2026-0041"
        doc = emit.emit(native)
        self.assertIn(
            {"@type": "sc:PropertyValue", "name": "provenance.ethicsApproval",
             "value": "REB-2026-0041"},
            doc["additionalProperty"],
        )
        self.assertEqual(parse.to_native_json(doc), native)


class EmissionRefusals(unittest.TestCase):
    def test_a_condition_with_two_operators_is_refused_at_emit(self):
        # gate/policy.py checks operators in a fixed order and applies the
        # first it finds, so a second one is a rule that is written down and
        # never enforced. Emitting it would launder that into a standard.
        native = copy.deepcopy(corpus()["raw-reads"])
        native["permissibleActions"][0]["conditions"]["platform"] = {
            "in": ["illumina"], "equals": "nanopore",
        }
        with self.assertRaises(emit.EmitError) as ctx:
            emit.emit(native)
        self.assertIn("only", str(ctx.exception))

    def test_an_unrecognised_native_operator_survives_as_an_unknown_operator(self):
        # The native evaluator refuses on it; so must the emitted document.
        # Equivalence has to hold for the bad descriptors too.
        native = copy.deepcopy(corpus()["raw-reads"])
        native["permissibleActions"][0]["conditions"]["platform"] = {"matches": "ill.*"}
        doc = emit.emit(native)
        condition = doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0]
        self.assertEqual(condition["cpol:operator"], "cpol:matches")

    def test_a_descriptor_missing_a_required_field_is_refused(self):
        for field in ("datasetId", "version", "state"):
            with self.subTest(missing=field):
                native = copy.deepcopy(corpus()["raw-reads"])
                del native[field]
                with self.assertRaises(emit.EmitError):
                    emit.emit(native)


class DocumentShape(unittest.TestCase):
    def setUp(self):
        self.doc = emit.emit(corpus()["raw-reads"])

    def test_it_claims_both_conformance_targets(self):
        self.assertEqual(self.doc["conformsTo"], [CROISSANT_IRI, PROFILE_IRI])
        self.assertTrue(parse.conforms_to_profile(self.doc))

    def test_the_operand_term_is_typed_json(self):
        # Without @json a JSON-LD processor reads an array operand as a set of
        # nodes rather than as a value.
        self.assertEqual(
            self.doc["@context"]["cpol:expected"],
            {"@id": "cpol:expected", "@type": "@json"},
        )

    def test_it_is_serialisable_and_key_order_is_stable(self):
        first = json.dumps(emit.emit(corpus()["raw-reads"]))
        second = json.dumps(emit.emit(corpus()["raw-reads"]))
        self.assertEqual(first, second)

    def test_a_single_node_stands_in_for_a_one_element_array(self):
        # JSON-LD permits it, so the parser must accept it.
        doc = copy.deepcopy(self.doc)
        action = doc["cpol:policy"]["cpol:permissibleAction"][1]
        action["cpol:requiresState"] = "QC_PASSED"
        action["cpol:condition"] = action["cpol:condition"][0]
        native = parse.to_native_json(doc)
        trim = [a for a in native["permissibleActions"] if a["name"] == "trim"][0]
        self.assertEqual(trim["requiresState"], ["QC_PASSED"])
        self.assertEqual(trim["conditions"], {"minReadLength": {"min": 20}})

    def test_a_document_without_a_name_cannot_be_parsed(self):
        doc = copy.deepcopy(self.doc)
        del doc["name"]
        with self.assertRaises(parse.ProfileError):
            parse.to_native_json(doc)


if __name__ == "__main__":
    unittest.main()
