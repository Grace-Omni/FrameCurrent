# Current verification

Updated: 2026-09-05
Product: 连续影像 / FrameCurrent 1.6.2

## Automated baseline

```bash
/usr/bin/python3 -m unittest discover -s tests -v
node --test tests/frontend.test.cjs
```

Observed locally: **85 / 85 Python tests PASS; 16 / 16 frontend-controller tests PASS**. These tests are offline and replace provider calls with local test doubles; they do not generate or charge for video. The frontend suite executes the real controller against a small DOM substitute, not a browser; it does not validate pixel layout, real media playback or browser compatibility.

New coverage includes environment failure before any billable call, safe duplicate launch, bounded shutdown with atomic cancellation, shutdown/start exclusion, HEAD route parity, exact read-only request recovery, first-run defaults, active-channel recovery, lost-response reconciliation, saved-clip links, Key-edit races, and cancelling paid confirmation.

## Local launch verification

- A separate source-only copy without user media, credentials or compiled binaries passed `doctor.command`, including first-time compilation and execution probes for all three Swift media helpers.
- That clean copy started on an ephemeral loopback port and returned HTTP 200; its test server was then stopped.
- The user's normal `run.command` started version 1.6.2 on `127.0.0.1:4173`; the homepage and health endpoint returned HTTP 200 with no active generation.
- Python compilation, both JavaScript syntax checks, shell syntax checks and `git diff --check` passed.
- The GitHub verification for pushed source is recorded in [Offline verification runs](https://github.com/Grace-Omni/framecurrent/actions/workflows/ci.yml); check the run for the specific commit under review.

## Repository presentation verification · 2026-09-05

- The actual local homepage and player region were visually inspected in a fresh browser session without credentials, generation tasks or user media. `docs/brand/app-overview.png` records that interface, not generated-video evidence.
- The refreshed cover was rendered to 1600 × 800 PNG and a 1280 × 640 social card; typography and layout were visually inspected.
- README navigation, referenced local files and asset sizes are checked before private-repository upload.
- No new paid five-minute sample, complete keyboard walkthrough, 200% zoom check or real playback acceptance is claimed.

## Existing coverage

Coverage includes:

- 10-second-to-30-minute fixed-duration boundaries and exact 5–15-second clip schedules.
- Unlimited mode, local estimated-cost cap, $150 server-side ceiling, stop behavior and active-task rules.
- 9:16 and 16:9 request validation.
- Five preset channels and one custom channel.
- Explicit paid confirmation, conservative budget checks and per-clip budget gates.
- API Key and sensitive-field redaction.
- fal queue/media URL allowlists, redirect refusal and request-store header.
- Loopback-only binding, Host/Origin checks and JSON-only state-changing requests.
- One-use initial reference-image handling and in-memory cleanup.
- POST non-retry behavior, GET bounded retry and idempotent start recovery.
- Generation-timing extraction from top-level and nested payloads, strict source priority, invalid-value fallback, tenth-second truncation and public clip fields.
- Start-time paid-dialog DOM contract and removal of the retired persistent cost, budget and confirmation controls.
- Local session restoration, final-file integrity and download behavior.

## Generation timing boundary

Each completed clip exposes a normalized time and its source. The source order is fixed by meaning, not by whichever number is smallest:

1. `gpu_core`: fal result `timings.inference`, the GPU core inference interval. It excludes queueing, encoding, download and local media processing.
2. `fal_processing`: fal completed-status `metrics.inference_time`, used only when the GPU-core value is missing or invalid.
3. `result_ready`: the local interval from before queue submission until the result response is readable. It includes queueing, network latency, polling cadence, GET retry delays and result retrieval, but still excludes media download and local processing.

Normalized values are truncated downward to one decimal place, so a displayed value is not more precise than that tenth-second bucket. The UI and documentation must show or explain the source; these values are per-request observations, not a MiniMax or fal official speed, benchmark or service-level promise.

The offline suite verifies parsing, priority, invalid-value handling, truncation and public projection only. It cannot measure live provider performance.

## Static UI invariants

- `#customProgramSettings` exists once and is hidden for every preset channel.
- Selecting `custom_channel` reveals that section without removing the hidden input nodes used to build requests.
- Resolution, continuation rhythm and API Key remain visible for every channel; cost, maximum budget and paid confirmation appear only after an enabled start action opens the confirmation dialog.
- The retired `#maxBudget`, `#costEstimate`, `#costDetail` and `#paidConfirmed` nodes are absent. The dialog owns `#paidDialog`, `#paidDialogCost`, `#paidDialogDetail`, `#paidDialogBudgetField`, `#confirmMaxBudget`, `#cancelPaidDialog` and `#confirmPaidStart` exactly once.
- Fixed-duration confirmation automatically uses the local estimate. Unlimited confirmation reveals a temporary local estimated-cost cap instead.
- A confirmed start still sends `paid_confirmed: true`; server-side paid-confirmation, minimum-cost, absolute-cap and per-clip guards remain authoritative inside the app. The cap is not a fal billing guarantee.
- Preset requests force `start_image` to `null`, preventing an invisible legacy reference from affecting generation.

## Historical paid evidence

The local `real-test/` folder contains an earlier 70-second portrait chain used to validate the real provider/media pipeline. It is intentionally excluded from Git because it is large generated media and needs separate rights/provenance handling.

That historical evidence does not prove that the current release generated a new five-minute video, a new landscape clip, or perfect semantic continuity. The 300-second merge path was stress-tested with offline media; full-length paid generation requires separate budget authorization and complete playback review.

See `ACCEPTANCE_REPORT.md` for the dated historical record. Treat its older test count and channel count as snapshot facts, not current product status.
