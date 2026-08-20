"""C2: strip the policy layer and a plain Croissant consumer still has a dataset.

The profile's whole claim to being additive rests on this. If removing `cpol:`
breaks the document, the profile is a fork of Croissant wearing Croissant's
name, and no downstream consumer should accept it.
"""

from __future__ import annotations

import json
import unittest

from support import corpus

from croissant_policy import emit
from croissant_policy.validate import strip, validate
from croissant_policy.vocab import (CROISSANT_CONTEXT, CROISSANT_IRI, PROFILE_IRI,
                                    claimed_iris)


class GracefulDegradation(unittest.TestCase):
    def setUp(self):
        self.docs = {k: emit.emit(v) for k, v in corpus().items()}

    def test_emitted_documents_conform(self):
        for name, doc in self.docs.items():
            with self.subTest(dataset=name):
                report = validate(doc)
                self.assertTrue(report.conforms, report.errors)

    def test_strip_leaves_no_trace_of_the_profile(self):
        for name, doc in self.docs.items():
            with self.subTest(dataset=name):
                self.assertNotIn("cpol", json.dumps(strip(doc)))

    def test_strip_leaves_a_loadable_dataset(self):
        for name, doc in self.docs.items():
            with self.subTest(dataset=name):
                bare = strip(doc)
                self.assertEqual(bare["@type"], "sc:Dataset")
                self.assertTrue(bare["name"])
                self.assertTrue(bare["description"])
                self.assertTrue(bare["distribution"])
                # Croissant's claim survives; the profile's goes with the
                # terms, so nothing advertises a policy that is no longer there.
                self.assertEqual(claimed_iris(bare["conformsTo"]), [CROISSANT_IRI])
                self.assertNotIn(PROFILE_IRI, claimed_iris(bare["conformsTo"]))

    def test_the_descriptive_half_survives_the_strip(self):
        # Everything except the policy itself is carried in standard terms, so
        # a consumer that ignores the profile still gets provenance, custodian
        # and schema -- not just a name and a file glob.
        bare = strip(self.docs["trimmed-reads"])
        self.assertEqual(bare["creator"]["name"], "nf-core")
        self.assertEqual(bare["isBasedOn"], "raw-reads@1.2.0")
        self.assertEqual(bare["measurementTechnique"], "SEQTK_TRIM")
        self.assertTrue(bare["variableMeasured"])

    def test_context_does_not_redefine_a_croissant_term(self):
        for name, doc in self.docs.items():
            with self.subTest(dataset=name):
                ctx = doc["@context"]
                added = {k for k in ctx if k not in CROISSANT_CONTEXT}
                self.assertEqual(added, {"cpol", "cpol:expected"})
                for term, definition in CROISSANT_CONTEXT.items():
                    self.assertEqual(ctx[term], definition)

    def test_retention_is_carried_and_not_enforced(self):
        # SPEC 5.1 lists cpol:retentionDays as informative in 0.1.0. A test
        # that it is *not* acted on is worth more than the sentence saying so.
        doc = self.docs["raw-reads"]
        self.assertEqual(doc["cpol:policy"]["cpol:retentionDays"], 730)
        conditions = [
            c["cpol:conditionName"]
            for a in doc["cpol:policy"]["cpol:permissibleAction"]
            for c in a.get("cpol:condition", [])
        ]
        self.assertNotIn("retentionDays", conditions)


if __name__ == "__main__":
    unittest.main()


class NoHostPathsEscape(unittest.TestCase):
    """A document is meant to be handed out, so it must not describe this host.

    Written after an absolute path reached both the public repository's examples
    and the copy staged for an external standards submission. The file's name and
    its SHA-256 identify it; its location on one machine identifies nothing a
    reader can use.
    """

    def test_a_decision_record_node_carries_a_name_not_a_path(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / "decisions.jsonl"
            record.write_text('{"verdict": "PERMIT"}\n')
            doc = emit.emit(corpus()["raw-reads"], decision_record=str(record))
            node = [d for d in doc["distribution"] if d["@type"] == "cr:FileObject"][0]
            self.assertEqual(node["contentUrl"], "decisions.jsonl")
            self.assertEqual(node["@id"], "decisions.jsonl")
            self.assertTrue(node["sha256"])
            self.assertNotIn(tmp, json.dumps(doc))

    def test_no_emitted_document_contains_an_absolute_path(self):
        for name, native in corpus().items():
            with self.subTest(dataset=name):
                text = json.dumps(emit.emit(native))
                for probe in ("/run/media", "/home/", "/tmp/", "/Users/"):
                    self.assertNotIn(probe, text)

    def test_the_committed_examples_are_clean(self):
        # The examples are committed and were the thing that actually leaked.
        from pathlib import Path

        for path in sorted((Path(__file__).resolve().parent.parent / "examples").glob("*.json")):
            with self.subTest(example=path.name):
                text = path.read_text()
                for probe in ("/run/media", "/home/", "/Users/"):
                    self.assertNotIn(probe, text, f"{path.name} carries a host path")
