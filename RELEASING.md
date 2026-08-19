# Releasing

A Zenodo deposit is permanent. A defect in a tagged snapshot cannot be edited
out — it can only be superseded by a later version, and the flawed one stays
published. So the checks below belong *before* the tag, not after it.

This file exists because that order was got wrong once: v0.1.0 was tagged
carrying a placeholder ORCID and a reference to a document that is no longer in
this repository. Nothing was deposited from it, so nothing permanent came of it,
but the discipline stands — the next tag is the one that becomes a record.

## The GitHub integration works -- and that is what went wrong

An earlier version of this file said the integration did not work for this
repository and that five tagged releases produced no record. That was wrong. The
error was in the observation, not in the mechanism.

Querying the Zenodo API with a token on 2026-08-19 found **three published
records across two concept DOIs**:

| Tag | Record | Concept | Route |
|---|---|---|---|
| v0.1.2 | 22005386 | 22005346 | GitHub integration |
| v0.1.4 | 22005347 | 22005346 | GitHub integration |
| v0.1.5 | 22005284 | **22005283** | manual upload form |

`v0.1.0`, `v0.1.1` and `v0.1.3` produced nothing and why was never established;
most likely they predate the webhook being enabled. That is the one part of the
original account that survives.

The integration's records carry filenames shaped
`doytsujin/ok-croissant-policy-profile-vX.Y.Z.zip`. A slash cannot be produced
through the upload form, so the filename alone says which route made a record.

Two things made this look like silence. The records arrived a few minutes
*after* the manual deposit, and they were minted under **a concept DOI of their
own** instead of joining the one the manual upload had just created. Nothing
appeared where it was being looked for, and the conclusion drawn -- "no edit
here can fix it" -- was reasoning from an absence that was not there.

**The cost was a split citation**: two concept DOIs for one piece of software,
one of them resolving to older code. That, together with the retired 122 us
figure the archives published, is why all of them were deleted rather than
superseded -- see [DEPOSIT.md](DEPOSIT.md). Zenodo deletes records on request
within roughly 30 days of publication; after that the only correction left is a
new version standing alongside the flawed one, permanently.

**The webhook is disabled now** and there is no `.zenodo.json`. Leave it that
way -- not because the integration is broken, but because this repository
already has a concept DOI and a second automatic one is precisely the defect
above. Deposit deliberately, into the concept that already exists.

## Before tagging

- [ ] `python3 -m unittest discover -s tests -t tests` — green
- [ ] `CITATION.cff` `version:` matches the tag about to be cut
- [ ] `CITATION.cff` `date-released:` is today
- [ ] `DEPOSIT.md` version and date match the same tag
- [ ] No placeholder identifiers anywhere — an ORCID of all zeros is worse than
      no ORCID, because it reads as a real one
- [ ] No retired measurement anywhere: `git grep -nE "122 ?(us|micro)"` returns
      only the provenance note in `bench/profile_overhead.py`. The 122 us figure
      was the median over the 7 decisions of the single-run study; the
      30-replicate run superseded it with 119 us over 210 decisions, and the
      old number survived in nine places for a week
- [ ] `results/*.json` regenerated from a run in this tree, not carried over
- [ ] `git grep` for references to files that have moved to another repository;
      the paper and the specification proposal are separate publications and
      their filenames must not appear here

## Depositing

The route is the REST API, not the upload form. The form's defaults win over
every field left untouched, and on the first deposit four of them did: licence,
version, publication date (stamped UTC, a day ahead of a late-evening Toronto
deposit) and related identifiers. The API sends a complete metadata object in
one request, so nothing is left to default.

The token lives at `~/.zenodo_token`, mode 600. It needs scopes `deposit:write`
and `deposit:actions`; only the second can publish.

1. Cut and push the tag.
2. Build the archive:
   `git archive --format=tar.gz --prefix=ok-croissant-policy-profile-vX.Y.Z/ vX.Y.Z -o ../ok-croissant-policy-profile-vX.Y.Z.tar.gz`
3. `POST /api/deposit/depositions` with the complete metadata object and
   `prereserve_doi`. Once this record exists, every subsequent release is a new
   version of it -- `POST /api/deposit/depositions/<newest-id>/actions/newversion`
   -- so that the concept DOI keeps resolving forward and no second concept
   ever appears.
4. Upload the archive to the draft's bucket, then `PUT` the complete metadata.
5. Publish. Read the record back through the API and diff it against
   [DEPOSIT.md](DEPOSIT.md) -- do not trust the form view.
6. Put the **concept** DOI in `CITATION.cff`, the README and the paper.

Step 6 is part of the release, not follow-up work: a deposit nothing cites is
an archive, not a publication.

When listing depositions to check what exists, use
`?size=100&all_versions=1`. The default listing omits versions and hid one of
the three records above.

## The record

Deposited by hand on 2026-08-18, which worked first time.

**There is no record.** All of these were deleted on 2026-08-19 and none of
them may be cited:

| DOI | Was | Status |
|---|---|---|
| `10.5281/zenodo.22005283` | concept of the manual deposit | deleted |
| `10.5281/zenodo.22005284` | v0.1.5 | deleted |
| `10.5281/zenodo.22005346` | concept minted by the integration | deleted |
| `10.5281/zenodo.22005347` | v0.1.4, integration | deletion requested |
| `10.5281/zenodo.22005386` | v0.1.2, integration | deleted |

The next deposit is a **new record** from v0.1.6, and it should be the only one
this software ever has.

## Which DOI to cite

Zenodo mints two: a **version DOI** for each release, and a **concept DOI** that
always resolves to the newest. The record page labels the latter *"Cite all
versions"*.

**Cite the concept DOI** in papers and in `CITATION.cff`. A version DOI in a
paper freezes the citation on whatever was current the week it was written.
