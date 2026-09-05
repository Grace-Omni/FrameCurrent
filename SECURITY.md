# Security policy

## Supported version

Only the latest `main` branch or most recent tagged release is expected to receive security fixes while the project remains experimental.

## Reporting a vulnerability

Do not publish API Keys, private prompts, reference images, provider receipts, or exploitable details in a public Issue. The repository is currently in private review. A public private-reporting channel has not yet been verified; enabling and testing one is a required gate before making the repository public. Do not assume an unlisted email address or a public Issue is a confidential reporting channel.

During private review, invited reviewers should use their established private contact with the owner. Before public release, the maintainer must replace this paragraph with an actual tested private-reporting route (for example GitHub Private Vulnerability Reporting) and verify it from an external account.

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
