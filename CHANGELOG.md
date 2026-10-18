# Changelog

## 1.1.0 — 2026-10-18

- English interface throughout onboarding, six modes, AI connections, account, guide and staff controls. User-authored notes and real model replies keep their original language.
- Readable experiment/hypothesis/state references instead of opaque IDs; identifiers remain available in explicit technical details and unchanged API records. Human-readable states and reviewed error messages.
- English number formatting, bounded displayed decimals and scientific notation for very small/large values. Measurements and machine-readable records retain their precision.
- Offline baseline explanations no longer dump coefficient arrays. Its numerical fitting and prediction algorithm is unchanged.
- Fresh English application screenshot and a 42-second silent introduction with captions and actual product captures; no real model calls, generated evidence or music.
- Installation guide and selectors updated; regression coverage for readable references, finite numbers, stop reasons and safe English errors. Database schema 4 and scientific/benchmark protocols are unchanged.


## 1.0.0 — 2026-10-18

First complete public, self-hosted application release, licensed MIT.

- Supported `zone workspace` / `python -m hidden_lab workspace` launcher: persistent private data, generated starter world, diagnostic Arena challenge, member registration and separate host-owner administration.
- Compiled web UI included in wheel and source release; Node is only needed when developing/building from source. SHA256SUMS and strict archive/publication checks accompany release artifacts.
- All six modes, scientific protocol and separate human approvals retained. Guided interface, glossary, profile quotas, public-measurement playback, preregistered prediction overlay, LaTeX/MathML and reduced motion.
- Personal API vault, outbound ChatGPT/Ollama/API connectors, per-session model pinning and revocation. No startup inference, implicit experiment or billing fallback.
- Benchmark v0.3 with four conditions, interpolation/extrapolation metrics and strict pairing; seeded Forge v1 levels 1–5, bounded AST identification, Arena and Integrity v1 preserved.
- SQLite schema 4, account ownership, CSRF, quotas, idempotent receipts, audit, migration checks, health and verified backup/restore.
- Generic Docker/HTTPS setup, English and Italian entry guides, operator/developer documentation, data policy responsibilities, security and support channels, dependency notices and research citation.
- CI verifies Linux/Windows Python, frontend, installed distribution, offline browser workflows and Docker without provider credentials or inference.

### Compatibility notes

Existing CLI, benchmark files and `serve` flows remain supported. Database migrations are forward checked; make a verified backup before upgrade. Rollback requires the prior version and its matching backup, not an automatic schema downgrade.

For safety, advanced `chatgpt transfer-vps` now requires explicit `--ssh-host` and `--container` in addition to the consent flag. Pending transfers are bound to the chosen destination; changing it requires reconciliation. This is not used by the normal local connector and performs no inference.

The default Compose application is now a complete account workspace, rather than an empty token-only server. Existing explicit `serve` deployments remain unchanged until their operator upgrades. Initial administrator keys expire and can be rotated or recovered on the trusted host.

## Development history (0.1–0.11)

The preceding local versions introduced the simulator/protocol, multi-provider operator loop, benchmark controls, Forge, identification, SQLite web backend, six modes, BYOA Arena, Integrity and operational tooling. Later local work added identity, per-user AI connections and the guided interface. A small real-model pilot demonstrated the protocol; it did not establish benchmark/model superiority. These development notes are engineering history rather than additional required release phases.

Public research limits are in [limitations](docs/limitations.md). Reproducible release evidence is in [release verification](docs/release-checklist.md).
