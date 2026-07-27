---
name: release
description: Cut a release on the correct one of this repo's two version lines - `pypi-v<version>` for the PyPI package, `v1.x` for the GitHub Action - and verify the publish workflow actually fired.
disable-model-invocation: true
---

# Releasing crucible

This repo ships two artifacts on two version lines. Picking the wrong tag prefix
fails **silently**: no error, no upload, a GitHub Release that looks fine.

| Artifact | Tag | Publishes to |
| --- | --- | --- |
| PyPI package `crucible-harden` | `pypi-v<version>` | pypi.org |
| GitHub Action | `v1.x.y` + moving `v1` | Marketplace / `uses:` |

Mechanics that decide everything below, from `.github/workflows/publish.yml`:

- The trigger is `on: release: [published]` — **a published GitHub Release, not a
  pushed tag**. `git push --tags` alone never publishes anything.
- The build job is gated `if: startsWith(github.event.release.tag_name, 'pypi-v')`.
  A release tagged anything else skips the job and uploads nothing.
- The build job then asserts the tag equals `pypi-v$VERSION` read from
  `pyproject.toml`, and fails loudly on a mismatch.

The gate is the fix for a bug that already happened: `v0.1.0` predates it and did
publish 0.1.0 to PyPI. A PyPI version can never be reused, so verification is not
optional.

## PyPI package release

1. Confirm `version` in `pyproject.toml` is bumped and merged to `main`. Record it:
   `python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"`
2. Packaging guard first — it rejects the metadata PyPI refuses at upload and
   `twine check` does not catch: `python -m pytest -q tests/test_packaging.py`
3. Full suite: `python -m pytest -q`
4. Lint: `ruff check src tests`
5. Build locally: `python -m build`
6. Publish a GitHub **Release** tagged `pypi-v<version>` (tag must equal the
   pyproject version exactly):
   `gh release create pypi-v<version> --title "crucible-harden <version>" --notes "..."`
7. **Verify the live effect.** Creating the release is not evidence it published:
   - `gh run list --workflow=publish.yml --limit 3` — a run must exist for this
     tag and reach `success`. No run, or a run whose build job was skipped, means
     the tag prefix was wrong. Fix by deleting the release and tag, then redo
     step 6 with the correct `pypi-v` prefix.
   - `gh run watch <run-id>` to follow it.
   - Confirm the version is live: https://pypi.org/project/crucible-harden/
   - `pip index versions crucible-harden` (or install it in a scratch venv).

If the run failed on the tag-match assertion, the tag and the pyproject version
disagree. Do not retag around it — fix whichever is wrong and re-release.

## GitHub Action release

The Action is versioned independently. `README.md` pins `Jott2121/crucible@v1`, so
the floating major tag must be moved or consumers never receive the release.

1. Confirm `action.yml` is correct on `main`.
2. Check the existing convention before tagging: `git tag -l` (currently `v1`,
   `v1.0.0`).
3. Publish a GitHub Release tagged `v1.x.y`:
   `gh release create v1.x.y --title "..." --notes "..."`
4. Move the floating major tag to the same commit:
   ```
   git tag -f v1 v1.x.y
   git push origin -f refs/tags/v1
   ```
5. **Verify no PyPI publish happened.** An Action release still fires the
   `release: published` event, so a `publish.yml` run may appear — what must be
   true is that its build job was **skipped** by the `pypi-v` gate and nothing
   reached PyPI:
   - `gh run list --workflow=publish.yml --limit 3` — any run for the `v1.x.y`
     tag must be skipped, never `success` with an upload.
   - Confirm PyPI shows no new version: https://pypi.org/project/crucible-harden/
6. Confirm the Action resolves: `git ls-remote --tags origin v1` points at the new
   commit.

Never tag an Action release `pypi-v*`, and never tag a package release `v*`.
