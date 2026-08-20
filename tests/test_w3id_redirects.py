"""The w3id rewrite rules resolve where the documentation says they do.

`w3id/croissant-policy/.htaccess` is the file submitted to `perma-id/w3id.org`,
and it is the one artifact in this repository that nobody here runs. It executes
on someone else's Apache, after a pull request, against a namespace that is
permanent once granted. A defect in it is discovered by a reader whose
dereference fails, which is the worst place to discover anything.

So the rules are parsed out of the file and applied to a table of paths. This is
a simulation and not Apache -- it models `RewriteRule` ordering, the `[L]` flag,
the `SetEnvIf` base variable, and the one `RewriteCond` on `HTTP_ACCEPT`, which
is everything the file uses. What it cannot catch is a directive Apache rejects
outright; what it does catch is a rule that matches the wrong path or is
shadowed by an earlier one, which is the mistake that ordering invites.

The expectations below are the table in `w3id/croissant-policy/README.md`. If
the two disagree, one of them is wrong and this test says which.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

HTACCESS = (Path(__file__).resolve().parent.parent
            / "w3id" / "croissant-policy" / ".htaccess")


def _rules() -> tuple[str, list[tuple[bool, str, str]]]:
    """Parse the base URL and the ordered (needs_ld_accept, pattern, target)."""
    base = None
    rules: list[tuple[bool, str, str]] = []
    pending_accept = False
    for line in HTACCESS.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        env = re.match(r"SetEnvIf\s+Request_URI\s+\S+\s+PROFILE_URL=(\S+)", line)
        if env:
            base = env.group(1)
            continue
        if line.startswith("RewriteCond"):
            # The only condition in the file is on HTTP_ACCEPT, and it guards
            # the JSON-LD branch. Two of them are OR'd; either arms the branch.
            if "HTTP_ACCEPT" in line:
                pending_accept = True
            continue
        rule = re.match(r"RewriteRule\s+(\S+)\s+(\S+)\s+\[", line)
        if rule:
            rules.append((pending_accept, rule.group(1), rule.group(2)))
            pending_accept = False
    assert base, "no PROFILE_URL in the .htaccess"
    return base, rules


def resolve(path: str, accept_ld: bool = False) -> str | None:
    """Where Apache would send this path. None if nothing matches."""
    base, rules = _rules()
    for needs_ld, pattern, target in rules:
        if needs_ld and not accept_ld:
            continue
        if re.match(pattern, path):
            expanded = target.replace("%{ENV:PROFILE_URL}", base)
            # Apache writes backreferences as $1; Python wants \1.
            return re.sub(pattern, re.sub(r"\$(\d)", r"\\\1", expanded), path)
    return None


class RedirectsResolveAsDocumented(unittest.TestCase):
    def setUp(self):
        self.base, _ = _rules()

    def _assert(self, path, expected_suffix, accept_ld=False):
        self.assertEqual(
            resolve(path, accept_ld), self.base + expected_suffix,
            f"/croissant-policy/{path}"
            + (" with Accept: application/ld+json" if accept_ld else ""),
        )

    def test_the_bare_namespace_is_the_version_index(self):
        self._assert("", "/")

    def test_a_version_is_the_profile_document(self):
        self._assert("0.1.0", "/0.1.0/")
        self._assert("0.1.0/", "/0.1.0/")

    def test_a_version_under_content_negotiation_is_the_context(self):
        """The one branch that exists to make the namespace machine-readable."""
        self._assert("0.1.0", "/0.1.0/context.jsonld", accept_ld=True)

    def test_each_named_artifact_resolves_to_itself(self):
        for name in ("context.jsonld", "shapes.ttl", "shapes-odrl.ttl",
                     "profile.jsonld"):
            with self.subTest(artifact=name):
                self._assert(f"0.1.0/{name}", f"/0.1.0/{name}")

    def test_the_odrl_carrier_identifier_resolves(self):
        """A distinct identifier, and it has to dereference like one."""
        self._assert("0.1.0/odrl", "/0.1.0/")
        self._assert("0.1.0/odrl/", "/0.1.0/")

    def test_a_term_resolves_to_the_document_defining_it(self):
        for term in ("policy", "Policy", "Condition", "failClosed", "min"):
            with self.subTest(term=term):
                self._assert(f"0.1.0/{term}", "/0.1.0/")

    def test_a_future_version_routes_to_its_own_path(self):
        """It will 404 until that version is published, which is correct.

        Sending an unminted version to the index would tell a consumer the
        version exists and looks like this one.
        """
        self._assert("0.2.0", "/0.2.0/")

    def test_anything_else_falls_back_to_the_index(self):
        self._assert("nonsense", "/")
        self._assert("0.1", "/")


class TheRulesAreOrderedCorrectly(unittest.TestCase):
    """Ordering is the whole risk in a rewrite file: `[L]` means first wins."""

    def test_named_artifacts_are_not_shadowed_by_the_term_rule(self):
        _, rules = _rules()
        patterns = [p for _, p, _ in rules]
        term_rule = next(i for i, p in enumerate(patterns) if p.endswith(r"/(.+)$"))
        for artifact in (r"profile\.jsonld", r"shapes\.ttl", r"shapes-odrl\.ttl",
                         r"context\.jsonld"):
            index = next(i for i, p in enumerate(patterns) if artifact in p)
            self.assertLess(index, term_rule,
                            f"{artifact} is shadowed by the generic term rule")

    def test_the_catch_all_is_last(self):
        _, rules = _rules()
        self.assertEqual(rules[-1][1], "^(.*)$",
                         "the catch-all must come last or it swallows everything")

    def test_every_rule_is_a_303(self):
        """303 rather than 302: the namespace is not an information resource."""
        for line in HTACCESS.read_text().splitlines():
            if line.strip().startswith("RewriteRule"):
                self.assertIn("[R=303,L]", line, line.strip())


class TheSubmissionIsComplete(unittest.TestCase):
    """w3id.org requires both files, and contact information in one of them."""

    def test_both_required_files_exist(self):
        self.assertTrue(HTACCESS.is_file())
        self.assertTrue((HTACCESS.parent / "README.md").is_file())

    def test_contact_information_is_present(self):
        text = HTACCESS.read_text() + (HTACCESS.parent / "README.md").read_text()
        self.assertIn("Contacts", text)
        self.assertIn("doytsujin", text)


if __name__ == "__main__":
    unittest.main()
