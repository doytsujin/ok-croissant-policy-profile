"""The profile, described in the vocabulary the Web has for describing profiles.

Until now this repository published everything a consumer needs -- a
specification, a JSON-LD context, a conformance validator, examples -- and
published nothing that says which file plays which role. A reader learned that
from the README. A program could not learn it at all.

The Profiles Vocabulary (PROF, W3C Working Group Note, 2019) is the vocabulary
for exactly this. A `prof:Profile` names what it is a profile *of* and lists
`prof:ResourceDescriptor`s, each pairing an artifact with a role drawn from a
standard role vocabulary. A consumer that holds a document claiming
`conformsTo: https://w3id.org/croissant-policy/0.1.0` can then discover the
validator from the identifier, instead of from a paper.

Two design notes.

**The description is generated, not written.** Every IRI in it comes from
`vocab.py` or from this module's own tables, and `tests/test_description.py`
asserts that the served file matches what this module produces. The served
context is already handled this way; a second hand-maintained copy of the same
IRIs is exactly the drift this repository has spent time undoing before.

**`isProfileOf` names Croissant, and the ODRL carrier is a second profile.**
The `cpol:` form profiles Croissant. The ODRL carrier (`croissant_policy/odrl.py`)
profiles both Croissant and ODRL, and says so, because a consumer that
recognises one identifier and not the other must be able to tell them apart --
ODRL's Information Model requires a processor to stop on a profile identifier it
does not recognise, and that requirement is worth nothing if the identifiers are
not distinguishable.
"""

from __future__ import annotations

import json
from pathlib import Path

from .odrl import ODRL_NS, ODRL_PROFILE_IRI
from .vocab import CROISSANT_IRI, PROFILE_IRI, PROFILE_VERSION

PROF_NS = "http://www.w3.org/ns/dx/prof/"
ROLE_NS = PROF_NS + "role/"

# Where the artifacts are actually served. The profile IRI is a w3id identifier
# and the registration is still open upstream, so a description that pointed
# only at the w3id URLs would describe resources a consumer cannot currently
# fetch. It points at both: the identifier for identity, the served URL for
# retrieval. When the redirect lands, the served URLs keep working.
SERVED_BASE = "https://doytsujin.github.io/ok-croissant-policy-profile/ns"
SERVED = f"{SERVED_BASE}/{PROFILE_VERSION}"

REPO = "https://github.com/doytsujin/ok-croissant-policy-profile"
REPO_RAW = f"{REPO}/blob/main"


def _resource(name: str, role: str, artifact: str, fmt: str, description: str,
              conforms_to: str | None = None) -> dict:
    node = {
        "@id": f"{PROFILE_IRI}#{name}",
        "@type": "prof:ResourceDescriptor",
        "dct:title": name,
        "dct:description": description,
        "prof:hasRole": {"@id": ROLE_NS + role},
        "prof:hasArtifact": {"@id": artifact},
        "dct:format": fmt,
    }
    if conforms_to:
        node["dct:conformsTo"] = {"@id": conforms_to}
    return node


def resources() -> list[dict]:
    """Every artifact a consumer of this profile may need, with its role.

    The roles are PROF's own eight and not invented: `specification` for the
    normative text, `vocabulary` for the term definitions, `validation` for
    things that check a document against the profile, `example` for conforming
    documents, `mapping` for the ODRL carrier -- which is a mapping in PROF's
    exact sense, one representation of a profile's content expressed in another
    standard's terms.
    """
    return [
        _resource(
            "specification", "specification", f"{REPO_RAW}/SPEC.md", "text/markdown",
            "The normative specification: conformance clauses, vocabulary, "
            "evaluation and capability projection.",
        ),
        _resource(
            "profile-document", "guidance", f"{SERVED}/", "text/html",
            "Human-readable profile document served at the namespace IRI.",
        ),
        _resource(
            "context", "vocabulary", f"{SERVED}/context.jsonld", "application/ld+json",
            "The JSON-LD context: Croissant's own context plus the two entries "
            "this profile adds.",
        ),
        _resource(
            "shapes", "validation", f"{SERVED}/shapes.ttl", "text/turtle",
            "SHACL shapes for the static conformance clauses of section 3. "
            "These validate a document; they do not decide a request.",
            conforms_to="http://www.w3.org/ns/shacl#",
        ),
        _resource(
            "validator", "validation", f"{REPO_RAW}/croissant_policy/validate.py",
            "text/x-python",
            "The structural conformance validator, which checks the clauses "
            "SHACL cannot reach without expanding the document.",
        ),
        _resource(
            "examples", "example", f"{REPO_RAW}/examples", "application/ld+json",
            "Conforming documents in both carriers, emitted from the descriptors "
            "of a real nf-core pipeline run.",
        ),
        _resource(
            "odrl-carrier", "mapping", f"{REPO_RAW}/croissant_policy/odrl.py",
            "text/x-python",
            "The mapping onto an ODRL policy carried in sc:usageInfo, which "
            "Croissant 1.1 names as the place for fine-grained use conditions. "
            "Decision-equivalent to the cpol: carrier; see "
            "tests/test_carrier_equivalence.py.",
            conforms_to=ODRL_NS,
        ),
        _resource(
            "capabilities", "mapping", f"{REPO_RAW}/croissant_policy/capabilities.py",
            "text/x-python",
            "The deterministic projection from a policy onto Model Context "
            "Protocol tool schemas.",
        ),
    ]


def description() -> dict:
    """The `prof:Profile` description of this profile, as JSON-LD."""
    return {
        "@context": {
            "prof": PROF_NS,
            "dct": "http://purl.org/dc/terms/",
            "role": ROLE_NS,
            "sh": "http://www.w3.org/ns/shacl#",
            "odrl": ODRL_NS,
        },
        "@graph": [
            {
                "@id": PROFILE_IRI,
                "@type": "prof:Profile",
                "dct:title": "Croissant Policy Profile",
                "dct:description": (
                    "An additive policy layer for Croissant dataset descriptors. A "
                    "dataset declares the operations it admits and the conditions "
                    "under which it admits them, from a closed set of five "
                    "operators, so that a gate can decide a request from the "
                    "descriptor alone and leave a record of what it checked."
                ),
                "dct:hasVersion": PROFILE_VERSION,
                "dct:publisher": "Alexander Chernov",
                "dct:license": {"@id": "https://spdx.org/licenses/Apache-2.0.html"},
                # Croissant is what this profiles. Naming it here is what makes
                # the additivity claim of conformance clause 1 a machine-readable
                # statement rather than a sentence in a README.
                "prof:isProfileOf": {"@id": CROISSANT_IRI},
                "prof:hasToken": "cpol",
                "prof:hasResource": [{"@id": r["@id"]} for r in resources()],
            },
            {
                # The ODRL carrier is a profile in its own right, of two things.
                # A consumer that recognises Croissant but not this identifier
                # must stop -- ODRL Information Model 3.2 -- and it can only do
                # that if the identifier is distinct from the cpol: one.
                "@id": ODRL_PROFILE_IRI,
                "@type": "prof:Profile",
                "dct:title": "Croissant Policy Profile — ODRL carrier",
                "dct:description": (
                    "The same policy expressed as an ODRL Set in sc:usageInfo, the "
                    "carrier Croissant 1.1 recommends for fine-grained use "
                    "conditions. Four of the five operators are ODRL core "
                    "operators; only the presence test is minted, because ODRL "
                    "defines no existence operator. Decisions are identical to the "
                    "cpol: carrier, record for record."
                ),
                "dct:hasVersion": PROFILE_VERSION,
                "prof:isProfileOf": [{"@id": CROISSANT_IRI}, {"@id": ODRL_NS}],
                "prof:isTransitiveProfileOf": {"@id": PROFILE_IRI},
                "prof:hasToken": "cpolodrl",
            },
            *resources(),
        ],
    }


def served_path() -> Path:
    return (Path(__file__).resolve().parent.parent
            / "docs" / "ns" / PROFILE_VERSION / "profile.jsonld")


def main(argv: list[str] | None = None) -> int:
    """Write the served description. Regenerate rather than hand-edit."""
    import argparse

    ap = argparse.ArgumentParser(
        prog="croissant_policy.description",
        description="Generate the PROF description of this profile",
    )
    ap.add_argument("--write", action="store_true",
                    help="write docs/ns/<version>/profile.jsonld instead of stdout")
    args = ap.parse_args(argv)

    text = json.dumps(description(), indent=2) + "\n"
    if args.write:
        path = served_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"description: -> {path}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
