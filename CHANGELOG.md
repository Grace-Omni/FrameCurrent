# Changelog

All notable changes are documented here. Dates use Asia/Shanghai local time.

## 1.6.1 — 2026-09-03

### Security

- Refuse automatic redirects for authenticated fal requests and media downloads so credentials and trusted URLs cannot cross an unvalidated redirect boundary.
- Enforce loopback-only binding plus local Host, same-origin Origin and JSON content-type checks for state-changing requests.
- Release initial reference-image data from server session memory immediately after use, including failure cleanup.

### Changed

- Rename the UI control to “本地预计费用上限,” state clearly that it is not a fal billing guarantee, and enforce a $150 server-side ceiling that still permits the 30-minute 768P maximum.
- Refresh public-release packaging, artifact exclusions and GitHub Actions checkout pin.
- Publish the source, documentation, production logos, repository brand images,
  and current channel artwork under Apache-2.0 while reserving trademark rights
  in “连续影像”, “FrameCurrent”, and the associated production logos.

### Verification

- 71 / 71 offline tests pass without making a paid fal request.

## 1.6.0 — 2026-09-03

### Added

- Per-scene generation timing with an explicit source: GPU core inference first, fal processing second, and local result-ready observation as the final fallback.
- Offline coverage for top-level and nested provider timing payloads, fixed source priority, invalid values, fallback behavior, tenth-second truncation and public clip fields.

### Changed

- Cost and paid confirmation moved out of the persistent creation form into a start-time dialog. Fixed-duration starts use the conservative estimate as their automatic maximum budget; unlimited starts ask for a temporary hard cap in that dialog.
- Confirmed starts still send `paid_confirmed: true` and remain subject to the same server-side budget and paid-confirmation validation.

### Accuracy boundary

- GPU core inference excludes queueing, encoding, download and local media processing. Broader fallback timings are labeled separately; none of these values is presented as a MiniMax or fal official speed promise.

### Verification

- 66 / 66 offline tests pass without making a paid fal request.

## 1.5.0 — 2026-09-02

### Added

- New product identity: 连续影像 / FrameCurrent.
- Original production SVG mark, bilingual lockup, GitHub cover, brand guide and asset register.
- GitHub-ready privacy, security, contribution, verification, architecture and publishing documentation.
- macOS environment checker and offline GitHub Actions workflow.

### Changed

- Preset channels no longer display creative program fields.
- “节目设置” appears only for the custom channel.
- Resolution, continuation rhythm, Key, budget and paid confirmation remain available for every channel.
- Initial reference images are scoped to the custom channel so hidden legacy images cannot influence a preset.
- Player, download filenames, browser title and local launcher now use FrameCurrent branding.

### Verification

- 58 offline tests remained the release baseline for 1.5.0.
- No paid fal generation is part of the branding or repository-packaging work.

## 1.4.0 — 2026-09-02

- AI television channel interface with five presets and one custom channel.
- Fixed 10-second-to-30-minute duration and unlimited mode with a hard budget cap.
- Per-channel sessions, local drafts, continuous preview and idempotent paid-start recovery.
