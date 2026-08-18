# Release sequence — run only after the provisional is filed

Everything here was ready on 2026-08-18 and deliberately held. Nothing in this
list is new work; it is the order, so that the sequence is not reconstructed
from memory on the day.

**Precondition, and it is the only one: the provisional has an application
number.** Not "submitted", not "with counsel" — filed and numbered. Record the
number and filing date at the bottom of this file before running step 1.

## Order matters

1. **Re-publish the repository.**
   ```bash
   gh repo edit doytsujin/ok-croissant-policy-profile \
       --visibility public --accept-visibility-change-consequences
   ```

2. **Re-enable Pages**, from `main` `/docs`:
   ```bash
   gh api -X POST repos/doytsujin/ok-croissant-policy-profile/pages \
       -f 'source[branch]=main' -f 'source[path]=/docs'
   ```
   Then wait for it to actually serve — the first build takes a couple of
   minutes and the w3id maintainers will test the target:
   ```bash
   until curl -sfo /dev/null https://doytsujin.github.io/ok-croissant-policy-profile/ns/0.1.0/; do sleep 15; done
   curl -s -o /dev/null -w '%{http_code}\n' https://doytsujin.github.io/ok-croissant-policy-profile/ns/0.1.0/context.jsonld
   ```

3. **Only now, submit the w3id PR.** The redirect target must exist before the
   maintainers look at it; a PR whose destination 404s is a PR that gets closed.
   The two files are in `w3id/croissant-policy/` and are already written to the
   perma-id conventions.
   ```bash
   gh repo fork perma-id/w3id.org --clone --remote=false
   mkdir -p w3id.org/croissant-policy
   cp w3id/croissant-policy/.htaccess w3id/croissant-policy/README.md w3id.org/croissant-policy/
   cd w3id.org && git checkout -b croissant-policy
   git add croissant-policy && git commit   # one commit, project name in the subject
   gh pr create --repo perma-id/w3id.org
   ```
   Their README asks for: contact info (present, name + GitHub username), a
   single squashed commit, and a descriptive subject naming the project.

4. **Verify the identifier end to end**, which is the only proof that matters:
   ```bash
   curl -sIL https://w3id.org/croissant-policy/0.1.0 | grep -i '^location\|HTTP/'
   curl -sIL -H 'Accept: application/ld+json' https://w3id.org/croissant-policy/0.1.0 | grep -i '^location'
   ```

5. **Then, and not before, the outward steps**: the arXiv preprint, and the
   MLCommons Data working-group approach.

## Not gated on the filing

These need no disclosure and can proceed at any time:

- Pass real capability records into `get_volume_croissant` in
  `dk-semantic-gateway-v2` — it currently hardcodes an empty vec, mirroring the
  `/manifest` handler, so contract capabilities never reach the document.
- Re-run the `dk-nfcore-admission-gate` replication with `$PWD` instead of
  `$NXF_TASK_WORKDIR`, which is empty in all 285 records.
- Anything in `dk-agentic-datasets-book`.

## Standing constraint

Until step 1 runs, the repository stays private and
`https://w3id.org/croissant-policy/0.1.0` keeps returning 404. Documents emitted
in the meantime carry a `conformsTo` IRI that does not resolve. **That is
accepted, not a defect to fix by republishing early.** The namespace is not
changed to a placeholder either: changing it twice is worse than a 404 inside a
private system.

## Filing record

Fill in before step 1.

| | |
|---|---|
| Application number | |
| Filing date | |
| Filed by | |
| Covers | |

See `EXPOSURE-2026-08-18.md` for the pre-filing public-exposure window — that
belongs in front of whoever drafts the application, not in a drawer.
