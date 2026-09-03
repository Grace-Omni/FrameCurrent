# Security policy

## Supported version

Only the latest `main` branch or most recent tagged release is expected to receive security fixes while the project remains experimental.

## Reporting a vulnerability

Do not publish API Keys, private prompts, reference images, provider receipts, or exploitable details in a public Issue. After the GitHub repository is created, enable GitHub Private Vulnerability Reporting and use that channel. Until then, contact the maintainer privately through the project owner’s established channel.

Include the affected version, macOS version, reproduction steps, expected impact, and a redacted proof. Remove all credentials and private media.

## Local threat model

- The server refuses non-loopback binds and listens only on `127.0.0.1`.
- Host, Origin and JSON content-type checks reduce browser-to-localhost request abuse; provider and media requests never follow HTTP redirects.
- There is no login, account boundary or multi-user authorization model. These local guards are not suitable authentication for a public deployment.
- Anyone who can access the local HTTP service may be able to inspect local session metadata and media.
- `runtime/` contains generated work and must not be committed, synced to an untrusted folder, or included in bug-report archives.
- The fal Key should be scoped and rotated according to the provider’s controls; never hard-code it.

## Repository safety

Pull requests must not add `runtime/`, `real-test/`, manifests, provider payloads, generated videos, precompiled Mach-O binaries, `.env` files, or real credentials. CI never receives a fal Key and must never submit a paid generation request.
