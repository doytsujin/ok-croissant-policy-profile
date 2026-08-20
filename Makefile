# Everything is stdlib. The only external dependency is the reference gate,
# which is imported rather than installed -- see croissant_policy/reference.py.
PY ?= python3
NFGATE ?= ../ok-nfcore-admission-gate
DESCRIPTORS := $(wildcard $(NFGATE)/descriptors/*.json)

.PHONY: all test bench precedence examples examples-odrl validate capabilities \
        venv mlcroissant shacl shapes description ns conformance clean

all: test examples conformance validate ns

test:
	$(PY) -m unittest discover -s tests -t tests -v

bench:
	$(PY) bench/profile_overhead.py --iterations 5000

precedence:
	$(PY) bench/precedence.py

# mlcroissant pulls in pandas/numpy/scipy/rdflib, so it lives in a venv and is
# never a dependency of the package itself.
venv:
	$(PY) -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q mlcroissant

mlcroissant:
	.venv/bin/python tools/validate_mlcroissant.py examples/*.croissant.json

# SHACL needs pyshacl, which needs rdflib, so it lives in the same venv as
# mlcroissant and for the same reason. --negative is not optional in CI: shapes
# that accept everything pass silently.
shacl:
	.venv/bin/python tools/validate_shacl.py examples/*.croissant.json \
	    --negative --corpus conformance

# The served namespace artifacts are generated, never hand-edited: the closed
# operator set and the resource list each have exactly one definition, in
# croissant_policy/. tests/test_ns.py fails if the served files drift from it.
shapes:
	$(PY) -m croissant_policy.shapes --write

description:
	$(PY) -m croissant_policy.description --write

ns: shapes description

# The specification-coverage corpus: documents generated from the closed
# grammar, so that translation fidelity and carrier equivalence are established
# across the operator and refusal space rather than on three descriptors. It
# carries no timing on purpose -- performance is measured on the deployment
# corpus, where the descriptors are real.
conformance:
	$(PY) -m croissant_policy.conformance --outdir conformance

examples: examples-odrl
	$(PY) -m croissant_policy.emit $(DESCRIPTORS) --outdir examples \
	    --url https://github.com/nf-core/test-datasets \
	    --license https://spdx.org/licenses/MIT.html \
	    --decision-record $(NFGATE)/results/decisions_gated.jsonl

# The cpol documents only. An ODRL-carrier document expresses its policy in
# odrl: terms and is deliberately not a cpol: document; validating it against
# the cpol conformance clauses would be checking it against a profile it does
# not claim.
CPOL_EXAMPLES := $(filter-out %.odrl.croissant.json,$(wildcard examples/*.croissant.json))

validate:
	$(PY) -m croissant_policy.validate $(CPOL_EXAMPLES)

capabilities:
	$(PY) -m croissant_policy.capabilities examples/*.croissant.json \
	    --out examples/capabilities.json

examples-odrl:
	$(PY) -m croissant_policy.odrl $(DESCRIPTORS) --outdir examples \
	    --url https://github.com/nf-core/test-datasets \
	    --license https://spdx.org/licenses/MIT.html \
	    --decision-record $(NFGATE)/results/decisions_gated.jsonl

clean:
	rm -rf conformance examples/*.croissant.json examples/capabilities.json \
	    results/profile_overhead.json **/__pycache__
