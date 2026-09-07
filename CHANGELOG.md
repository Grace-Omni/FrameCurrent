# Changelog

All notable changes are documented here. Dates use Asia/Shanghai local time.

## 1.7.1 — 2026-09-07

- Start every channel on a black player. Make example and restored-video playback opt-in through a preview toggle, with no automatic media download. Closing a preview keeps existing files and any generation task intact.
- Accept harmless event-key variations (underscores, spaces, letter case and Unicode dashes) locally, without another paid planning request. Keep story-novelty checks after normalization.
- Separate format corrections from story revisions. Send validated fields as retry context, never escaped raw model output; retain rejection details only in local diagnostics.
- Show the specific story-planning failure in the player and distinguish saved clips from video that was never submitted or has not yet been saved.

## 1.7.0 — 2026-09-07

- Replace all prewritten and cyclic scene tables with stochastic, frame-grounded improvisation for every duration and channel, including custom channels. The last scene of a fixed-length programme receives a remaining-time constraint for closure.
- Before each video request, use fal's `openrouter/router/vision` with `google/gemini-2.5-flash-lite` to review chronological first/middle/last frame samples and cumulative story memory. Observations remain model reports, not full-video or human verification.
- Require a consequential new goal, dilemma, discovery or reversal. Reject duplicate/near-duplicate plans, reported semantic repeats and low-impact plans; allow one new planning attempt, then stop instead of falling back to an old script.
- Persist scene plans, video prompts and story memory locally. Include planning allowances and returned usage costs in the existing start confirmation and estimated-budget guard. Unknown request outcomes are not resubmitted.
- Replace plot spoilers in channel descriptions with AI-TV channel identities.
- Verified with offline provider substitutes and local media/browser checks; new paid generation is still required to assess narrative quality.

## 1.6.3 — 2026-09-05

### Animation channel

- Rebuild the hand-drawn animation channel around an original healing summer meadow, a naturally proportioned child and one orange-and-white pet cat, with separate built-in 16:9 and 9:16 opening frames.
- Add a duration-aware story scheduler: butterfly pursuit, a windblown hat, the cat's rescue, recovery and reunion are expanded or compressed to the actual clip plan.
- Make each scene advance a visible action, expression or prop state while inheriting the actual previous frame. Planned beats are treated as intent rather than proof, so missing actions receive a causal bridge instead of a teleport or reset.
- Lock the current server-owned preset revision so stale browser drafts cannot mix the former animation concept into the new artwork.

### Verification boundary

- Added offline coverage for both reference-frame orientations, stale-draft replacement, 5/10/15-second scene planning and story-continuation prompts. No fal generation was submitted while preparing this update.

## Repository presentation — 2026-09-05

- Refresh the bilingual product introduction, brand cover and 1280 × 640 social-preview card.
- Present five preset channels and the custom channel together, with concept artwork labeled separately from model output.
- Add an actual fresh-session interface screenshot, a concise download/start path, expandable FAQs and a documentation index.
- Localize issue templates for Chinese and English readers, update the asset register, and prepare the 1.6.2 changes for owner review in the existing private repository.

## 1.6.2 — 2026-09-04

### First-run experience

- Start with a 30-second sample; distinguish output length from wait time and local connectivity from provider access.
- Add a compact in-app guide, Key dashboard link, actionable disabled-start explanations and reconnect guidance.
- Keep preset channels free of program settings. Preserve custom controls, horizontal/vertical output and unlimited mode.
- Show the running channel across channel changes, recover it after refresh, and reconcile lost-start request IDs through an exact, read-only lookup.
- Offer individual saved-clip downloads after partial progress or interruption; retain completed-program telemetry when editing the next duration.
- Increase decision-critical text sizes, expose keyboard focus on radio/file controls, and respect reduced-motion preferences.

### Reliability and safety

- Validate and compile media tools before the first billable request; environment checks no longer pass solely because a compiler stub exists.
- Reopen only a matching local checkout/version; explain port conflicts without killing processes.
- Bound frontend request waits without automatically retrying paid POSTs. Reject an in-flight Key verification if the input changed.
- On process shutdown, reject new starts and attempt cancellation with atomic credential capture and a bounded wait. Remote cancellation is not guaranteed.
- Route HEAD through the same protected routes as GET; distinguish file/media errors from model safety rejections.

### Packaging and verification

- Rewrite onboarding for new users, add an English overview and Chinese troubleshooting guide, and replace the hard-coded passing badge with a CI link.
- Keep Apache-2.0 and reserved trademarks unchanged. Private security reporting remains a public-release gate.
- 85 Python and 16 frontend-controller offline tests pass. Clean-source macOS media compilation and local HTTP startup verified. No paid generation or browser visual acceptance was performed for this update.

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
