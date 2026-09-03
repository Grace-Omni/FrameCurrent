# Privacy

FrameCurrent is currently a single-user local application. It does not include accounts, analytics, telemetry, or a hosted database, but using video generation still sends content to a third-party provider.

## What stays in the browser

The browser stores channel drafts, custom-channel settings, channel/session mapping, aspect-ratio choices, and idempotency recovery state in `localStorage`. The API Key is not intentionally written to `localStorage`.

To remove browser state, clear site data for `http://127.0.0.1:4173` in the browser.

## What stays on the Mac

Generated clips, extracted frames, final videos, checksums, and sanitized task manifests are stored under `runtime/sessions/`. Compiled Swift helpers are stored under `runtime/bin/`.

To remove local work, stop the server and delete the specific session folder you intend to remove. Review the folder before deletion; there is no cloud recycle bin.

## What is sent to fal

When the user explicitly confirms a paid generation, FrameCurrent sends the selected prompt, channel constraints, requested duration/resolution and—when used in the custom channel—the initial reference image to fal. Later requests also send the previous clip’s final frame so the next clip can continue from it.

The request includes `X-Fal-Store-IO: 0`. This is a request to the provider not to persist request input/output; it is not an absolute guarantee about provider infrastructure, logs, legal retention, or subprocessors. Review the provider’s current privacy and retention terms before using sensitive material.

## API Key handling

The Key is present in the password field and the local Python process memory while needed. After a task starts, the page clears the field; after task completion or failure, the backend releases its in-memory copy. An initial reference image is removed from the server session as soon as its first provider call ends, and continuation-frame data is released when the worker exits. Public session responses and manifests are designed to exclude the Key, reference-image data, complete prompts, local absolute paths, and raw provider receipts.

Never paste a production Key into an Issue, log, screenshot, test fixture, or repository file. If a Key may have leaked, revoke it at the provider and issue a replacement.

## Public deployment

This version has no authentication or multi-user isolation. Do not bind it to a public interface, reverse-proxy it to the internet, or deploy it as a shared service. A hosted edition needs authentication, server-side secret storage, user isolation, quotas, abuse controls, encrypted object storage, retention controls, and deletion workflows.
