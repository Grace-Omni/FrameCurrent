# Contributing to FrameCurrent

Thanks for helping improve 连续影像 / FrameCurrent. This is an experimental, macOS-local creative tool with real-cost API actions, so contributions must keep proof, safety, and paid execution clearly separated.

## Before opening a change

1. Run `./doctor.command`.
2. Keep the existing standard-library Python and vanilla web architecture unless a dependency has a clear product need.
3. Never include real API Keys, prompts, reference images, task manifests, provider receipts, generated videos, or compiled runtime binaries.
4. Do not make any test submit a real fal generation.
5. Preserve the product rule that preset channels hide the creative “节目设置” interface; only the custom channel exposes it.

## Verification

```bash
/usr/bin/python3 -m py_compile app.py
/usr/bin/python3 -m unittest discover -s tests -v
node --check web/app.js
node --check web/player.js
```

Type-check each Swift tool separately:

```bash
for source_file in scripts/*.swift; do
  /usr/bin/swiftc -typecheck "$source_file"
done
```

## Pull requests

Describe the user-visible outcome, privacy or billing impact, tests run, and whether any paid request was made. For UI changes, include a screenshot that contains no Key, private media, session ID, or local absolute path.

If a change alters budget math, provider endpoints, Key handling, persistence, cancellation, idempotency, media validation, or public binding, call it out explicitly for security review.

## Licensing

The project is licensed under [Apache-2.0](LICENSE). Unless you explicitly state
otherwise, intentionally submitted contributions are provided under the same
license as described by Section 5. Do not submit material you do not have the
right to license.

Contribution does not grant rights to use “连续影像”, “FrameCurrent”, or their
logos as the identity of a separate product. See [TRADEMARKS.md](TRADEMARKS.md).
