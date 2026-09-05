# Architecture

FrameCurrent is intentionally small: a standard-library Python server, a vanilla HTML/CSS/JavaScript client, and three Swift/AVFoundation media helpers.

```mermaid
flowchart LR
  UI[Local browser UI] -->|Key check / confirmed start| API[Python HTTP server]
  API -->|Queue requests| FAL[fal API]
  FAL -->|Temporary clip URLs| API
  API --> MEDIA[Swift + AVFoundation tools]
  MEDIA --> STORE[runtime/sessions]
  STORE -->|Preview clips / final MP4| UI
```

## Paid generation path

1. The browser validates the persistent creation fields; cost and paid-confirmation controls are not kept in the main form.
2. Clicking start opens one confirmation dialog. Fixed-duration mode uses the local cost estimate; unlimited mode asks for a temporary local estimated-cost cap inside the dialog.
3. Canceling closes the dialog without starting. Confirming sends `paid_confirmed: true`, the selected maximum budget and a client-generated UUID for idempotency.
4. The server independently validates paid confirmation, duration, aspect ratio, provider URLs and budget exactly as before.
5. The worker first compiles and probes local media helpers and checks writable storage. Only after preflight succeeds does the first clip use text-to-video, or image-to-video for a custom-channel reference image.
6. Each subsequent clip uses the previous validated final frame and continuity constraints.
7. Clips are downloaded, inspected, trimmed to planned duration and appended to the manifest.
8. The finalizer re-encodes a unified H.264 MP4 and AAC track, then records size and SHA-256.

## Trust boundaries

- Browser storage is local but not secret storage.
- The Python process temporarily holds the provider Key.
- fal processes prompts, references, end frames, and generated media.
- `runtime/` is durable local content and may contain sensitive creative work.
- The HTTP service enforces loopback binding plus Host, Origin and JSON request checks, but it has no public authentication and is safe only on loopback.
- Authenticated provider requests and media downloads reject redirects instead of forwarding credentials or crossing trust boundaries.
- The estimated-cost cap is a local submission guard based on built-in reference rates, not a provider billing guarantee.

## Local lifecycle and recovery

`launcher.py` validates the actual toolchain and only reopens an existing service if its product, checkout fingerprint and version match. The fingerprint does not disclose the absolute source path. A conflicting process is never killed automatically.

The health endpoint describes the local service and the single active channel; it does not certify fal availability. The client discovers active sessions independently of browser history. A lost start response is reconciled using `POST /api/session/recover`, which only looks up the exact existing request ID and cannot create a task. The pending ID is retired only after a matching session is proven. This preserves idempotent recovery while allowing a subsequent new programme to use a new request ID.

During shutdown, registration and shutdown state share a lock. New starts are rejected, workers stop extending the programme, and the existing atomic stop/cancellation mechanism is given a bounded grace period. Already-submitted remote work may still run or incur a charge. Relaunch never automatically resumes paid generation.

GET and HEAD share local authority checks and the public route allowlist; HEAD omits the body. Partial completed clips remain accessible through scoped media links even when no complete MP4 is available.

## Product evidence levels

FrameCurrent keeps these claims separate:

- **Configured**: a channel and budget were selected.
- **Submitted**: the provider accepted a job.
- **Generated**: a clip was returned.
- **Validated**: the local media structure passed checks.
- **Merged**: a final file was created and hashed.
- **Accepted**: a person watched the complete relevant video and approved motion/story continuity.
