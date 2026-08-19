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
- [ ] Working tree clean, and everything pushed

## Tag and release

```sh
git tag -a vX.Y.Z -m "Croissant policy profile X.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "X.Y.Z" --notes "..."
```

The GitHub release is what triggers Zenodo, not the tag.

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
