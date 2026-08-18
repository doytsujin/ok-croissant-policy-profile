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


def is_known_operator(term: str) -> bool:
    return term in OPERATORS
