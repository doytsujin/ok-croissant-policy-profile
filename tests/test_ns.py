"""The served namespace artifacts say what the code says.

`docs/ns/<version>/` is what a consumer gets when it dereferences the profile
IRI. Three of the four files there are generated -- the context, the SHACL
shapes, and the PROF description -- and a generated file that has been edited in
place is worse than one that was never generated, because the disagreement is
invisible until someone acts on the wrong copy.

This repository has paid for that lesson once already: a hand-transcribed
`@context` carried four terms that did not belong and was missing two, and the
error survived until MLCommons' own validator was pointed at it. These tests
make the same class of drift a build failure instead of a discovery.

`make ns` regenerates everything checked here.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from croissant_policy import description, shapes
from croissant_policy.odrl import ODRL_NS, ODRL_PROFILE_IRI
from croissant_policy.vocab import CROISSANT_IRI, OPERATORS, PROFILE_IRI

REPO = Path(__file__).resolve().parent.parent


class ServedArtifactsDoNotDrift(unittest.TestCase):
    def test_the_served_shapes_match_the_generator(self):
        self.assertEqual(
            shapes.served_path().read_text(),
            shapes.shapes(),
            "docs/ns/<version>/shapes.ttl is stale; run `make shapes`",
        )

    def test_the_served_description_matches_the_generator(self):
        self.assertEqual(
            json.loads(description.served_path().read_text()),
            description.description(),
            "docs/ns/<version>/profile.jsonld is stale; run `make description`",
        )


class ShapesCoverTheClosedSet(unittest.TestCase):
    def test_every_operator_appears_in_the_shapes(self):
        """The shapes and the evaluator must agree on what the set contains.

        Generated from `vocab.OPERATORS`, so this cannot fail by editing one
        and not the other -- but it can fail if the generator's regex is wrong,
        which is a mistake the generated file would carry silently.
        """
        text = shapes.shapes()
        for term in OPERATORS:
            self.assertIn(term.split(":", 1)[1], text, f"{term} missing from the shapes")

    def test_the_operator_pattern_accepts_exactly_the_closed_set(self):
        import re

        pattern = re.compile(shapes._operator_pattern().replace("\\\\", "\\"))
        for term in OPERATORS:
            self.assertTrue(pattern.match(term), f"{term} rejected by its own shape")
        for term in ("cpol:regex", "cpol:matches", "min", "cpol:", "cpol:minimum"):
            self.assertFalse(pattern.match(term), f"{term} wrongly accepted")


class ProfileDescriptionIsUsable(unittest.TestCase):
    """A description nobody can act on is documentation with extra steps."""

    def setUp(self):
        self.graph = description.description()["@graph"]
        self.by_id = {n["@id"]: n for n in self.graph}

    def test_it_describes_both_profiles(self):
        self.assertIn(PROFILE_IRI, self.by_id)
        self.assertIn(ODRL_PROFILE_IRI, self.by_id)

    def test_the_cpol_profile_is_a_profile_of_croissant(self):
        self.assertEqual(
            self.by_id[PROFILE_IRI]["prof:isProfileOf"], {"@id": CROISSANT_IRI}
        )

    def test_the_odrl_carrier_profiles_both_croissant_and_odrl(self):
        node = self.by_id[ODRL_PROFILE_IRI]
        self.assertEqual(
            node["prof:isProfileOf"], [{"@id": CROISSANT_IRI}, {"@id": ODRL_NS}]
        )
        # ODRL Information Model 3.2 requires a processor to stop on a profile
        # identifier it does not recognise. That is worth nothing if the two
        # identifiers are the same string.
        self.assertNotEqual(ODRL_PROFILE_IRI, PROFILE_IRI)

    def test_every_named_resource_is_described(self):
        named = {r["@id"] for r in self.by_id[PROFILE_IRI]["prof:hasResource"]}
        described = {r["@id"] for r in description.resources()}
        self.assertEqual(named, described)

    def test_the_roles_are_prof_roles_and_not_invented(self):
        known = {
            "constraints", "example", "guidance", "mapping",
            "schema", "specification", "validation", "vocabulary",
        }
        for resource in description.resources():
            role = resource["prof:hasRole"]["@id"]
            self.assertTrue(role.startswith(description.ROLE_NS), role)
            self.assertIn(role[len(description.ROLE_NS):], known, role)

    def test_the_shapes_and_the_specification_are_both_reachable(self):
        roles = {r["prof:hasRole"]["@id"].rsplit("/", 1)[1] for r in description.resources()}
        self.assertIn("specification", roles)
        self.assertIn("validation", roles)

    def test_repository_artifacts_are_named_by_a_path_that_exists(self):
        """A resource descriptor pointing at a file nobody has is a broken promise."""
        prefix = description.REPO_RAW + "/"
        for resource in description.resources():
            artifact = resource["prof:hasArtifact"]["@id"]
            if not artifact.startswith(prefix):
                continue
            relative = artifact[len(prefix):]
            self.assertTrue(
                (REPO / relative).exists(),
                f"{resource['@id']} points at {relative}, which is not in the repository",
            )


if __name__ == "__main__":
    unittest.main()
