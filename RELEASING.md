# Releasing

A Zenodo deposit is permanent. A defect in a tagged snapshot cannot be edited
out — it can only be superseded by a later version, and the flawed one stays
published. So the checks below belong *before* the tag, not after it.

This file exists because that order was got wrong once: v0.1.0 was tagged
carrying a placeholder ORCID and a reference to a document that is no longer in
this repository. Nothing was deposited from it, so nothing permanent came of it,
but the discipline stands — the next tag is the one that becomes a record.

## The deposit is manual

**The GitHub integration does not work for this repository.** Five tagged
releases were cut on 2026-08-18 and not one produced a Zenodo record:

| Tag | Metadata carried | Result |
|---|---|---|
| v0.1.0, v0.1.1 | `.zenodo.json`, `license: "Apache-2.0"`, `upload_type: software` | no record |
| v0.1.2 | `.zenodo.json`, `license: "apache-2.0"`, `publication_date` present | no record |
| v0.1.3 | `.zenodo.json`, `license: {"id": "Apache-2.0"}`, no `upload_type` | no record |
| v0.1.4 | no `.zenodo.json` at all — `CITATION.cff` only | no record |

The last row is what settles it. With `.zenodo.json` gone, Zenodo falls back to
`CITATION.cff`, which is a validated standard format that parses and carries
title, authors, version, date, licence, abstract, keywords and repository. It
failed identically. **The fault is therefore not in what this repository
carries, and no edit here can fix it.** The licence shape was the earlier
suspect and it is not the discriminator either: nipype deposits successfully
with `"Apache-2.0"` and `upload_type: software`, which is exactly the shape that
failed here.

So the route is Zenodo's own upload form, by hand. [DEPOSIT.md](DEPOSIT.md)
holds the field values to paste. This costs one form per release and depends on
no webhook. Do not reintroduce `.zenodo.json` to try again — if a
Zenodo-specific field is ever genuinely needed, add it on the record through
Zenodo's edit form.

## Before tagging

- [ ] `python3 -m unittest discover -s tests -t tests` — green
- [ ] `CITATION.cff` `version:` matches the tag about to be cut
- [ ] `CITATION.cff` `date-released:` is today
- [ ] `DEPOSIT.md` version and date match the same tag
- [ ] No placeholder identifiers anywhere — an ORCID of all zeros is worse than
      no ORCID, because it reads as a real one
- [ ] `git grep` for references to files that have moved to another repository;
      the paper and the specification proposal are separate publications and
      their filenames must not appear here

## Depositing

1. Cut and push the tag.
2. Build the archive:
   `git archive --format=tar.gz --prefix=ok-croissant-policy-profile-vX.Y.Z/ vX.Y.Z -o ../ok-croissant-policy-profile-vX.Y.Z.tar.gz`
3. New upload at zenodo.org, attach the archive, and fill the form from
   [DEPOSIT.md](DEPOSIT.md).
4. Publish. Zenodo mints the two DOIs.
5. **Re-read the published record against `DEPOSIT.md`.** The form's defaults
   win over every field left untouched, and on the first deposit four of them
   did. Metadata is editable after publication; the files are not.
6. Put the **concept** DOI in `CITATION.cff` `identifiers`, in the README, and
   in the paper's Availability section.

Step 6 is part of the release, not follow-up work: a deposit nothing cites is
an archive, not a publication.

## The record

Deposited by hand on 2026-08-18, which worked first time.

| DOI | What it points at |
|---|---|
| `10.5281/zenodo.22005283` | concept — the newest version, whatever that is |
| `10.5281/zenodo.22005284` | v0.1.5 specifically |

## Which DOI to cite

Zenodo mints two: a **version DOI** for each release, and a **concept DOI** that
always resolves to the newest. The record page labels the latter *"Cite all
versions"*.

**Cite the concept DOI** in papers and in `CITATION.cff`. A version DOI in a
paper freezes the citation on whatever was current the week it was written.
