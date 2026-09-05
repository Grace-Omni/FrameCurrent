# GitHub publishing checklist

Use this repository root only. Do not publish its parent workspace.

Local preflight last completed: **2026-09-03**, against the staged 1.6.1 initial
release. Re-run the checks after any source or asset change.

The checked boxes below record the original 1.6.1 publication audit, not blanket approval of later edits. For the local 1.6.2 review, see [current verification](VERIFICATION.md) and [review findings](REVIEW-1.6.2.md). Re-run CI and source/asset checks after committing the update. The repository remains private until the owner approves public visibility.

### Private review update — 2026-09-05

- [x] Local 1.6.2 checks: 85 Python tests, 16 frontend tests, JavaScript/Python/shell syntax, and Swift type checks.
- [x] Re-check all candidate source files for private runtime artifacts, credential patterns, personal paths, oversized files, and broken local documentation links.
- [x] Refresh the bilingual README, brand cover, channel overview, and real clean-session UI screenshot.
- [x] Prepare a matching 1280 × 640 social card. The private repository's current Settings page does not expose a Social preview uploader; upload and verify it when that control is available. Do not change visibility for this step.
- [ ] Before making the repository public, obtain the owner's review approval and complete the remaining public-release gates below.

## 1. Legal and brand

- [x] Apache-2.0 selected and canonical `LICENSE` added.
- [x] Existing production logos, repository brand images, and `channel-art-atlas.png` approved for public Apache-2.0 distribution.
- [x] Trademark rights reserved separately in `NOTICE` and `TRADEMARKS.md`.
- [x] Historical generated videos, reference media, and local concept art remain outside the public repository.
- [ ] Perform formal trademark clearance before commercial launch of “FrameCurrent.”
- [ ] Before switching to public, provide a tested private security-reporting route and replace the private-review placeholder in `SECURITY.md`.

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
- [x] Use the PNG cover in the README for consistent font rendering, retain the editable SVG source, and add the repository description.
- [ ] Do not add a fal secret to CI.
- [ ] Publish large, rights-cleared evidence separately as a Release asset, with SHA-256 and a media license.

## 5. Public-hosting boundary

Publishing source code is not authorization to deploy this local server publicly. A hosted product needs authentication, server-side secret custody, user isolation, quotas, rate limits, abuse controls, storage lifecycle, deletion, HTTPS and billing reconciliation.
