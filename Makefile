# Everything is stdlib. The only external dependency is the reference gate,
# which is imported rather than installed -- see croissant_policy/reference.py.
PY ?= python3
NFGATE ?= ../dk-nfcore-admission-gate
DESCRIPTORS := $(wildcard $(NFGATE)/descriptors/*.json)

.PHONY: all test bench examples validate capabilities clean

all: test examples validate

test:
	$(PY) -m unittest discover -s tests -t tests -v

bench:
	$(PY) bench/profile_overhead.py --iterations 5000

examples:
	$(PY) -m croissant_policy.emit $(DESCRIPTORS) --outdir examples \
	    --url https://github.com/nf-core/test-datasets \
	    --license https://spdx.org/licenses/MIT.html \
	    --decision-record decisions.jsonl

validate:
	$(PY) -m croissant_policy.validate examples/*.croissant.json

capabilities:
	$(PY) -m croissant_policy.capabilities examples/*.croissant.json \
	    --out examples/capabilities.json

clean:
	rm -rf examples/*.croissant.json examples/capabilities.json \
	    results/profile_overhead.json **/__pycache__
