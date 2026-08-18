# Release sequence

> **Decision, 2026-08-18: no patent will be filed.** This file was written as
> *ON-FILING.md*, gated on a provisional that will not now exist. The gate is
> removed; the sequence below is unblocked and can run immediately.
>
> The strategy is **defensive publication**. Publishing establishes the work as
> prior art against anyone else's filing, which is the protection actually
> wanted here, and it costs nothing beyond doing what was going to be done
> anyway. The assessment that led here is in
> [`dk-croissant-policy-patent`](../../dk-croissant-policy-patent) — nine of
> twelve candidate claims closed on prior art before the decision was taken, so
> little was given up.

**There is no precondition. Step 1 can run now.**

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

## Order still matters

Nothing gates step 1 any more, but steps 2-4 remain ordered for a practical
reason rather than a legal one: the w3id maintainers test the redirect target,
and a pull request whose destination 404s is a pull request that gets closed.
Republish, confirm Pages actually serves, then submit.

## On the exposure record

`EXPOSURE-2026-08-18.md` documented a ~35 minute public window for counsel.
With no application to draft, it is no longer evidence for anything and is
retained only as an accurate record of what happened on the day. It should not
be read as an open question.
