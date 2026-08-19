# Zenodo deposit sheet — v0.1.6

**Not yet deposited, and this is the first record.** Every earlier deposit was
deleted on 2026-08-19 — see [RELEASING.md](RELEASING.md) for what they were and
why they went. So v0.1.6 goes in as a **new record**, and it should be the only
one this software ever has. Whatever concept DOI Zenodo mints for it is the one
that gets cited everywhere, permanently, so deposit once and deposit deliberately.

Deposit through the REST API, not the upload form. The token is at
`~/.zenodo_token`. The form's defaults overwrite every field left untouched and
did so four times on the v0.1.5 deposit; a complete metadata object sent in one
request has nothing left to default.

**File to attach:** `ok-croissant-policy-profile-v0.1.6.tar.gz`, built by
`git archive` from the tag — not a working-tree zip, which would carry whatever
happened to be uncommitted.

| Field | Value |
|---|---|
| Resource type | Software |
| Title | A Policy Profile for Croissant: Refusal as a Property of the Dataset |
| Creator | Chernov, Alexander |
| ORCID | 0009-0007-3198-2712 |
| Publication date | 2026-08-19 |
| Version | 0.1.6 |
| Licence | Apache License 2.0 |
| Language | English |

**Description** (paste as written):

> An additive policy profile for Croissant dataset descriptors. A dataset
> declares the operations it admits and the conditions under which it admits
> them, so a gate in front of the data can permit or refuse a request from the
> descriptor alone and leave a record of what was checked. Includes a reference
> implementation, a conformance validator, an MCP capability projection, a
> measured overhead study, a caller-side/data-side precedence experiment, and a
> tool for re-deciding a stored decision archive against a later policy.

**Keywords:** croissant, dataset descriptors, admission control, data
governance, provenance, agent governance

**Related identifiers:**

| Identifier | Relation |
|---|---|
| `https://github.com/doytsujin/ok-croissant-policy-profile/tree/v0.1.6` | is supplement to |
| `https://w3id.org/croissant-policy/0.1.0` | is documented by |

The first relation is the one Zenodo's own GitHub integration sets, so a
deliberate deposit reads the same way as an automated one. Leave communities and
grants empty — neither is in use.

## Why the earlier records were deleted

The v0.1.5 record's **metadata** was repairable and was repaired in place —
version, keywords, related identifiers, and a publication date the form had
stamped UTC a day ahead of the tag.

Its **files** were not repairable, and that is what disqualified it:

| Defect | Where | Why it disqualifies the archive |
|---|---|---|
| The retired **122 µs** figure | `README.md` ×2, `bench/profile_overhead.py` ×4, `croissant_policy/__init__.py`, `reference.py`, and as data in `results/profile_overhead.json` | 122 µs was the median over the **7** decisions of the single-run study. The 30-replicate run superseded it with **119 µs over 210 decisions**. The archive published a measurement its own authors had withdrawn, and the C3 projection was computed from it |
| Absolute host path | 3 × `examples/*.croissant.json`, `results/profile_overhead.json` | `/run/media/<user>/...` identifies the machine that emitted the file. A file's name and SHA-256 identify it; its path does not |

Files on a published record are frozen. Zenodo does, however, delete records on
request within roughly 30 days of publication, and all three were a day old, so
deletion was available where editing was not. Records 22005284 and 22005386 are
gone (410); 22005347 was requested and is still live at the time of writing.

**That window is the thing to remember.** After ~30 days the only remaining
correction is a new version alongside the flawed one, forever. Deposit late
enough to be right, early enough to still have the option.

## What changed for v0.1.6

- 122 µs retired in all nine locations, replaced by 119 µs with its provenance
  recorded in `bench/profile_overhead.py` next to the constant
- `results/profile_overhead.json` regenerated in-tree, not edited — the
  projection moves to **130.7 µs**
- README's overhead table re-read from the fresh run (+11.7 µs cold, was +11.9)
- The claim that the gate stays "below the resolution of Nextflow's own trace"
  removed. The replication measured a per-task delta of **+25.7 ms, 95% CI
  [3.3, 48.2] ms**, an interval excluding zero. The cost is the per-task
  subprocess, not the decision, and the README now says so
- The namespace section no longer claims the w3id IRI resolves. It does not —
  the registration PR is unsubmitted and the IRI returns 404
- The P2 summary no longer reads `deny-overrides` **admits 0**, which is false;
  it admits 12. It makes 0 admissions that some authority refused
- `RELEASING.md`'s account of the GitHub integration corrected — it works, and
  the split concept DOI is the consequence

## After publishing

Read the record back **through the API**, not the record page, and diff it
against this sheet:

```
curl -sL https://zenodo.org/api/records/<new-version-id> \
  | python3 -c "import json,sys; m=json.load(sys.stdin)['metadata']; \
      print({k: m.get(k) for k in ('version','publication_date','keywords','related_identifiers')})"
```

Then put the newly minted **concept** DOI — not the version DOI — in
`CITATION.cff` `identifiers`, the README's opening line, and the paper's
Availability section. The concept resolves forward to whatever the newest
version is, which is why it is the one to cite. All three files currently carry
no DOI at all, deliberately: a tag shipping a dead DOI is worse than one
shipping none.

## Keep this in step

The version, date and description here are duplicated from `CITATION.cff` on
purpose: the deposit is filled from this file, and a sheet that drifts from the
tag deposits the wrong metadata permanently. Both are on the pre-tag checklist
in [RELEASING.md](RELEASING.md).
