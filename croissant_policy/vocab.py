"""Profile vocabulary: the JSON-LD context and the closed operator set.

Everything the profile adds to Croissant is named here, so a reader can see the
whole surface of the extension in one file. If a term is not in this module it
is not part of the profile.
"""

from __future__ import annotations

PROFILE_VERSION = "0.1.0"

# Placeholder IRI. Deliberately not a claim on a registered namespace; nothing
# in the profile depends on it dereferencing (SPEC section 4).
PROFILE_IRI = f"https://example.invalid/croissant-policy/{PROFILE_VERSION}"
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
# self-contained and does not depend on a network fetch to be read. See SPEC
# section 9: this has not been checked against MLCommons' reference validator,
# and the profile says so rather than implying it has.
CROISSANT_CONTEXT = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "arrayShape": "cr:arrayShape",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "cr": "http://mlcommons.org/croissant/",
    "data": {"@id": "cr:data", "@type": "@json"},
    "dataBiases": "cr:dataBiases",
    "dataCollection": "cr:dataCollection",
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "dct": "http://purl.org/dc/terms/",
    "examples": {"@id": "cr:examples", "@type": "@json"},
    "extract": "cr:extract",
    "field": "cr:field",
    "fileObject": "cr:fileObject",
    "fileProperty": "cr:fileProperty",
    "fileSet": "cr:fileSet",
    "format": "cr:format",
    "includes": "cr:includes",
    "isArray": "cr:isArray",
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
    "sc": "https://schema.org/",
    "separator": "cr:separator",
    "source": "cr:source",
    "subField": "cr:subField",
    "transform": "cr:transform",
}


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


def is_known_operator(term: str) -> bool:
    return term in OPERATORS
