"""Profile vocabulary: the JSON-LD context and the closed operator set.

Everything the profile adds to Croissant is named here, so a reader can see the
whole surface of the extension in one file. If a term is not in this module it
is not part of the profile.
"""

from __future__ import annotations

PROFILE_VERSION = "0.1.0"

# The namespace IRI. A w3id.org identifier redirecting to the hosted profile
# document, which is the usual pattern for a vocabulary namespace: the
# identifier outlives any decision about where the document is served from.
#
# This is permanent. Every emitted document embeds it, so changing it is not a
# refactor -- it invalidates every document already in circulation. A version
# bump gets a new path; it never gets a new host.
PROFILE_IRI = f"https://w3id.org/croissant-policy/{PROFILE_VERSION}"
CPOL_NS = PROFILE_IRI + "/"

CROISSANT_IRI = "http://mlcommons.org/croissant/1.0"

# The closed operator set, mapped to the key the reference evaluator already
# understands. This mapping is the whole enforcement story: the profile does
# not evaluate anything itself, it rewrites a policy into the native condition
# form and hands it to the gate. An operator absent from this table therefore
# cannot be "not implemented" -- it maps to UNSUPPORTED_KEY, which the native
# evaluator already refuses on. Fail-closed is a property of the translation,
# not a check somebody has to remember to write.
OPERATORS = {
    "cpol:min": "min",
    "cpol:max": "max",
    "cpol:in": "in",
    "cpol:equals": "equals",
    "cpol:present": "present",
}

UNSUPPORTED_KEY = "unsupportedOperator"

REFUSAL_UNDECLARED = "UNDECLARED_ACTION"
REFUSAL_STATE = "STATE_PRECONDITION"
REFUSAL_CONDITION = "CONDITION_VIOLATED"

# Croissant 1.0's own context, reproduced so that an emitted document is
# self-contained and does not depend on a network fetch to be read.
#
# Copied from MLCommons' own generator (`mlcroissant._src.core.rdf.make_context`
# at CroissantVersion.V_1_0) rather than transcribed from the spec prose. The
# first hand-written version of this table carried four terms it should not have
# -- `arrayShape` and `isArray`, which are Croissant 1.1, and `dataBiases` and
# `dataCollection`, which are not Croissant terms at any version -- and was
# missing `equivalentProperty` and `samplingRate`. mlcroissant reported it as a
# non-standard context. Regenerate with tools/validate_mlcroissant.py rather
# than editing by hand.
CROISSANT_CONTEXT = {
        "@language": "en",
        "@vocab": "https://schema.org/",
        "citeAs": "cr:citeAs",
        "column": "cr:column",
        "conformsTo": "dct:conformsTo",
        "cr": "http://mlcommons.org/croissant/",
        "data": {
            "@id": "cr:data",
            "@type": "@json"
        },
        "dataType": {
            "@id": "cr:dataType",
            "@type": "@vocab"
        },
        "dct": "http://purl.org/dc/terms/",
        "equivalentProperty": "cr:equivalentProperty",
        "examples": {
            "@id": "cr:examples",
            "@type": "@json"
        },
        "extract": "cr:extract",
        "field": "cr:field",
        "fileObject": "cr:fileObject",
        "fileProperty": "cr:fileProperty",
        "fileSet": "cr:fileSet",
        "format": "cr:format",
        "includes": "cr:includes",
        "isLiveDataset": "cr:isLiveDataset",
        "jsonPath": "cr:jsonPath",
        "key": "cr:key",
        "md5": "cr:md5",
        "parentField": "cr:parentField",
        "path": "cr:path",
        "rai": "http://mlcommons.org/croissant/RAI/",
        "recordSet": "cr:recordSet",
        "references": "cr:references",
        "regex": "cr:regex",
        "repeated": "cr:repeated",
        "replace": "cr:replace",
        "samplingRate": "cr:samplingRate",
        "sc": "https://schema.org/",
        "separator": "cr:separator",
        "source": "cr:source",
        "subField": "cr:subField",
        "transform": "cr:transform"
    }

# RAI terms are reached through the `rai` prefix, which the official context
# binds. There is no bare `dataCollection` alias in Croissant; writing one would
# resolve against @vocab to a schema.org term that does not exist.
RAI_DATA_COLLECTION = "rai:dataCollection"


def context() -> dict:
    """The `@context` of a conforming document.

    Croissant's context verbatim, plus exactly two entries. The profile adds a
    prefix and one typed term, and every policy key in the document is written
    prefixed (`cpol:policy`, not `policy`). Aliasing policy terms to bare names
    would be more pleasant to read and would risk shadowing a Croissant or
    schema.org term, which conformance clause 1 forbids -- so the profile pays
    the prefix everywhere and keeps the guarantee.

    `cpol:expected` is typed `@json` because a condition operand is arbitrary
    JSON: a number, a string, a boolean, or an array. Without the typing a
    JSON-LD processor would try to interpret an array as a set of nodes.
    """
    ctx = dict(CROISSANT_CONTEXT)
    ctx["cpol"] = CPOL_NS
    ctx["cpol:expected"] = {"@id": "cpol:expected", "@type": "@json"}
    return ctx


def profile_iri() -> str:
    """The IRI a conforming document names in `conformsTo` alongside Croissant."""
    return PROFILE_IRI


def conformance_claim(profile: str = PROFILE_IRI) -> list[str]:
    """The value of `conformsTo`: bare strings, and not by preference.

    The obviously correct RDF is a node reference, `{"@id": "..."}`, so that
    the value expands to an IRI. Written as bare strings the values expand to
    *language-tagged literals*, because Croissant's own context defines
    `conformsTo` as `dct:conformsTo` without `"@type": "@id"` and sets
    `"@language": "en"` globally. A document written the obvious way therefore
    claims conformance to the *text* "https://w3id.org/croissant-policy/0.1.0"
    rather than to the profile that IRI identifies, and RDF-level profile
    discovery from a descriptor does not work.

    We tried the node form and reverted it. MLCommons' `mlcroissant` rejects
    it: the reference implementation string-compares `conformsTo` to determine
    which Croissant version a document claims, so a node reference is not
    recognised as a version at all, and the document then fails validation on
    every downstream expectation that depends on the version it could not
    determine. Croissant validity is conformance clause 1 and is not
    negotiable, so the bare form stays.

    The third option -- adding `"conformsTo": {"@id": "dct:conformsTo",
    "@type": "@id"}` to the profile's `@context` -- is closed by clause 1 too,
    which forbids redefining a Croissant core term.

    So this is a defect in Croissant rather than a choice of this profile, and
    it is recorded as one: SPEC section 9, and the note in
    `croissant_policy/shapes.py` where the profile's own SHACL shapes have to
    match a literal instead of an IRI. It was found by running those shapes
    against these examples. Readers here accept both forms (`claimed_iris`), so
    the day the reference implementation accepts node references, the emitter
    changes and nothing else does.
    """
    return [CROISSANT_IRI, profile]


def claimed_iris(value) -> list[str]:
    """The IRIs a `conformsTo` value names, in either notation.

    Documents emitted before this correction carry bare strings, and they are
    not thereby non-conforming JSON -- they are simply weaker. Readers accept
    both; the emitter writes only the node form.
    """
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    out: list[str] = []
    for item in values:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict) and isinstance(item.get("@id"), str):
            out.append(item["@id"])
    return out


def is_known_operator(term: str) -> bool:
    return term in OPERATORS


# What each operator requires of its *operand* -- the value written in the
# document, not the value observed at request time. The two are different and
# conflating them is how the defects below survived as long as they did.
#
# An observation of the wrong type is a normal refusal: `min: 20` against
# "not-a-number" is a request that fails a well-formed rule, and the evaluator
# reports it as a condition violation. An *operand* of the wrong type is not a
# request problem at all -- it is a defect in the policy, and it has to be
# refused before evaluation rather than handed to a comparison that was never
# defined for it.
#
# Found by asking what Table 1 of the paper actually promises. Two answers were
# wrong. `in` with a scalar number raised TypeError, so a malformed document
# crashed the evaluator instead of being refused by it. Worse, `in` with a
# string operand fell through to Python substring matching, so a policy written
# `{"in": "illumina"}` -- forgetting the array, which is the obvious authoring
# slip -- silently PERMITTED "illu". A rule that admits more than its author
# wrote is the failure this profile exists to prevent, and it was reachable
# from a document that looks conforming.
def operand_defect(operator: str, expected) -> str | None:
    """Why this operand cannot be evaluated by this operator, or None.

    Returns a reason rather than a boolean, because the reason travels into the
    decision record and a refusal that cannot say what was wrong with the
    policy is as unhelpful as one that cannot say what was wrong with the
    request.
    """
    if operator in ("cpol:min", "cpol:max"):
        # bool is a subclass of int in Python and is not a threshold.
        if isinstance(expected, bool) or not isinstance(expected, (int, float)):
            return (f"operator {operator} needs a numeric operand, got "
                    f"{type(expected).__name__}")
    elif operator == "cpol:in":
        if not isinstance(expected, list):
            return (f"operator cpol:in needs a list operand, got "
                    f"{type(expected).__name__}; a scalar is not a one-element set")
    elif operator == "cpol:present":
        if not isinstance(expected, bool):
            return (f"operator cpol:present needs a boolean operand, got "
                    f"{type(expected).__name__}")
    # cpol:equals compares for equality and accepts any JSON value, including
    # arrays and objects. Numeric equality follows JSON: 1 and 1.0 are equal.
    return None
