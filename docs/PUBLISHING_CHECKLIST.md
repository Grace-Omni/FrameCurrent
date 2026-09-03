# GitHub publishing checklist

Use `outputs/h3-max-continuous-test/` as the repository root. Do not publish the parent workspace.

Local preflight last completed: **2026-09-03**, against the staged 1.6.1 initial
release. Re-run the checks after any source or asset change.

## 1. Legal and brand

- [x] Apache-2.0 selected and canonical `LICENSE` added.
- [x] Existing production logos, repository brand images, and `channel-art-atlas.png` approved for public Apache-2.0 distribution.
- [x] Trademark rights reserved separately in `NOTICE` and `TRADEMARKS.md`.
- [x] Historical generated videos, reference media, and local concept art remain outside the public repository.
- [ ] Perform formal trademark clearance before commercial launch of “FrameCurrent.”

## 2. Clean source boundary

- [x] `git status --ignored` shows `runtime/` and `real-test/` as ignored.
- [x] `git ls-files` contains no `.env`, key files, manifest, MP4, compiled Mach-O binary, or session folder.
- [x] Search for accidental credentials and private absolute paths.
- [x] Reject unexpected files larger than 10 MB.

Suggested checks after Git initialization:

```bash
git ls-files | grep -E '(^|/)(runtime|real-test)/|(^|/)manifest\.json$|\.(mp4|mov|m4v|webm|part|partial)$' && exit 1 || true
git grep -nE '(FAL_KEY|api[_-]?key)[[:space:]]*[:=][[:space:]]*[^"'"'"' ]{12,}' || true
git ls-files -z | while IFS= read -r -d '' file; do
  test "$(stat -f %z "$file")" -le 10485760 || echo "$file"
done
```

Review every match manually; a clean command is not proof that a repository contains no secret.

## 3. Verification

- [x] Run `./doctor.command`.
- [x] Run 71 offline tests.
- [x] Confirm release documentation identifies version 1.6.1.
- [x] Type-check all Swift files separately.
- [x] Check both JavaScript files.
- [x] Start with `--no-open`, request `/api/health`, then stop the server.
- [x] Confirm no paid fal request was made during release QA.
- [x] Confirm every generation-time value is paired with its source and is not described as an official model speed; GPU core timing must state that it excludes queueing, encoding, download and local processing.

## 4. GitHub settings

- [ ] Enable private vulnerability reporting.
- [ ] Protect `main` and require CI.
- [ ] Keep Actions permissions read-only by default.
- [ ] Upload `docs/brand/github-social-preview.png` in **Settings → General → Social preview** and verify the rendered card.
- [ ] Keep the SVG cover in the README and add the repository description.
- [ ] Do not add a fal secret to CI.
- [ ] Publish large, rights-cleared evidence separately as a Release asset, with SHA-256 and a media license.

## 5. Public-hosting boundary

Publishing source code is not authorization to deploy this local server publicly. A hosted product needs authentication, server-side secret custody, user isolation, quotas, rate limits, abuse controls, storage lifecycle, deletion, HTTPS and billing reconciliation.
