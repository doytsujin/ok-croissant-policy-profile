"""C4: the capability schema is derived from the policy, so it cannot drift.

The failure this guards against is a registry entry that says `minimum: 20`
while the gate enforces 30. The only durable fix is to make the two the same
object, and the only way to show that is to change the policy and watch the
schema follow.
"""

from __future__ import annotations

import copy
import unittest

from support import corpus

from croissant_policy import capabilities, emit, parse
from croissant_policy.reference import load_gate

_, _, gate_mod = load_gate()


class CapabilityProjection(unittest.TestCase):
    def setUp(self):
        self.corpus = corpus()
        self.docs = {k: emit.emit(v) for k, v in self.corpus.items()}

    def test_one_capability_per_permissible_action(self):
        for name, doc in self.docs.items():
            with self.subTest(dataset=name):
                tools = capabilities.project(doc)
                actions = doc["cpol:policy"]["cpol:permissibleAction"]
                self.assertEqual(len(tools), len(actions))
                self.assertEqual(
                    [t["name"] for t in tools],
                    [f"{name}.{a['cpol:actionName']}" for a in actions],
                )

    def test_operators_become_their_json_schema_constraint(self):
        tools = {t["name"]: t for t in capabilities.project(self.docs["raw-reads"])}
        trim = tools["raw-reads.trim"]["inputSchema"]
        self.assertEqual(trim["properties"]["minReadLength"], {"type": "number", "minimum": 20})
        self.assertEqual(trim["properties"]["platform"], {"enum": ["illumina"]})
        self.assertEqual(trim["required"], ["minReadLength", "platform"])
        self.assertTrue(trim["additionalProperties"])

    def test_required_states_appear_in_the_description(self):
        tools = {t["name"]: t for t in capabilities.project(self.docs["raw-reads"])}
        self.assertIn("TRIMMED", tools["raw-reads.align"]["description"])

    def test_schema_follows_the_policy(self):
        # The drift test. Move the threshold in the document and the advertised
        # constraint moves with it, because there is only one of them.
        doc = copy.deepcopy(self.docs["raw-reads"])
        for action in doc["cpol:policy"]["cpol:permissibleAction"]:
            for condition in action.get("cpol:condition", []):
                if condition["cpol:conditionName"] == "minReadLength":
                    condition["cpol:expected"] = 99
        tools = {t["name"]: t for t in capabilities.project(doc)}
        self.assertEqual(
            tools["raw-reads.trim"]["inputSchema"]["properties"]["minReadLength"]["minimum"], 99
        )
        # ...and the gate now refuses what it used to admit, from the same edit.
        self.assertTrue(parse.authorize(doc, "trim", {"minReadLength": 20,
                                                      "platform": "illumina"}).verdict
                        == gate_mod.REFUSE)

    def test_satisfying_the_schema_is_not_a_substitute_for_the_gate(self):
        # A caller can satisfy every advertised constraint and still be refused
        # on the state precondition, which the schema deliberately cannot carry.
        doc = self.docs["raw-reads"]
        decision = parse.authorize(doc, "align", {"minMapQ": 30, "referenceBuild": "GRCh38"})
        self.assertEqual(decision.verdict, gate_mod.REFUSE)
        self.assertEqual(decision.reason_class, gate_mod.STATE)

    def test_an_unknown_operator_advertises_an_unsatisfiable_parameter(self):
        doc = copy.deepcopy(self.docs["raw-reads"])
        doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0]["cpol:operator"] = (
            "cpol:matches"
        )
        tool = capabilities.project(doc)[0]
        self.assertEqual(tool["inputSchema"]["properties"]["platform"]["not"], {})

    def test_capability_name_and_description_can_be_overridden(self):
        doc = copy.deepcopy(self.docs["raw-reads"])
        action = doc["cpol:policy"]["cpol:permissibleAction"][0]
        action["cpol:capabilityName"] = "reads.quality_control"
        action["cpol:description"] = "Quality-control the reads."
        tool = capabilities.project(doc)[0]
        self.assertEqual(tool["name"], "reads.quality_control")
        self.assertEqual(tool["description"], "Quality-control the reads.")


if __name__ == "__main__":
    unittest.main()
