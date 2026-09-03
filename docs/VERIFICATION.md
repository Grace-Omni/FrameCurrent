# Current verification

Updated: 2026-09-03
Product: 连续影像 / FrameCurrent 1.6.1

## Automated baseline

```bash
/usr/bin/python3 -m unittest discover -s tests -v
```

Expected result: **71 / 71 PASS**. These tests are offline and replace provider calls with local test doubles; they do not generate or charge for video.

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
