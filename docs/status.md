# Project status

Zone 1.0 finishes the public, reusable software project: standalone launcher, packaged web UI, all six modes, personal model connections, research CLI, tests and operational documentation. See [the README](../README.md), [release verification](release-checklist.md) and [limitations](limitations.md).

This is a self-hosted application. It is not an account-registration invitation to a centrally operated service. Earlier beta hosts and operator-specific configuration are not public endpoints or required infrastructure.

The default flow is offline, with no provider account or credential. API models, eligible ChatGPT-plan models and existing local Ollama models are opt-in, with explicit model IDs and human-authorized experiment execution. Provider transports are tested with simulations; that is separate from validating scientific performance on real models.

Benchmark v0.3, Forge v1, Arena v1, Integrity v1 and additive SQLite migrations remain supported. Exact software verification and release artifacts are recorded in the [checklist](release-checklist.md); do not use historical phase counts as current evidence.
