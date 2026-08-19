# Releasing

A Zenodo deposit is permanent. A defect in a tagged snapshot cannot be edited
out — it can only be superseded by a later version, and the flawed one stays
published. So the checks below belong *before* the tag, not after it.

This file exists because that order was got wrong once: v0.1.0 was tagged and
deposited carrying a placeholder ORCID and a reference to a document that is no
longer in this repository. Both were cosmetic and both are fixed in v0.1.1, but
neither can be removed from the v0.1.0 record.

## Before tagging

- [ ] `python3 -m unittest discover -s tests -t tests` — green
- [ ] `CITATION.cff` `version:` matches the tag about to be cut
- [ ] `CITATION.cff` `date-released:` is today
- [ ] No placeholder identifiers anywhere — an ORCID of all zeros is worse than
      no ORCID, because it reads as a real one
- [ ] `git grep` for references to files that have moved to another repository;
      the paper and the specification proposal are separate publications and
      their filenames must not appear here
- [ ] `python3 -c "import json;json.load(open('.zenodo.json'))"` — valid
- [ ] `.zenodo.json` `version` matches the tag

### There is no `.zenodo.json`, deliberately

Four deposits failed with it. Three different shapes were tried, each taken from
documentation or from a real project whose deposits succeed, and every one
failed:

| Attempt | `license` | `upload_type` | `publication_date` | Result |
|---|---|---|---|---|
| v0.1.0, v0.1.1 | `"Apache-2.0"` | `software` | absent | failed |
| v0.1.2 | `"apache-2.0"` | `software` | present | failed |
| v0.1.3 | `{"id": "Apache-2.0"}` | absent | absent | failed |

The evidence contradicts itself, which is why chasing it further was not worth
the releases it was costing. `developers.zenodo.org` documents a lowercase
controlled vocabulary and a live query confirms it, but that endpoint is the
legacy REST API and not the GitHub integration. Zenodo's own help page shows a
bare lowercase string. The Citation File Format project deposits successfully
with an object and no `upload_type`. **nipype deposits successfully with
`"Apache-2.0"` and `upload_type: software` — which is exactly the shape that
failed here.** So the licence form is not the discriminator and the real fault
was never identified.

**The file is removed.** Zenodo's precedence is `.zenodo.json`, then
`CITATION.cff`, then `LICENSE`; with the first gone, `CITATION.cff` drives the
deposit. That is a validated standard format, it parses, and it carries title,
authors, version, date, licence, abstract, keywords and repository — everything
in the deleted file except `communities`, `grants` and `related_identifiers`,
none of which were in use.

If a Zenodo-specific field is ever genuinely needed, add it on the record
through Zenodo's own edit form rather than reintroducing this file.

## Which DOI to cite

Zenodo mints two: a **version DOI** for each release, and a **concept DOI** that
always resolves to the newest. The record page labels the latter *"Cite all
versions"*.

**Cite the concept DOI** in papers and in `CITATION.cff`. A version DOI in a
paper freezes the citation on whatever was current the week it was written.

## Metadata precedence

Both `.zenodo.json` and `CITATION.cff` are present. Zenodo reads
`.zenodo.json` in preference, so that file governs the deposit record;
`CITATION.cff` drives GitHub's "Cite this repository" widget and other tools
that read it directly. Keeping the two consistent is manual.
