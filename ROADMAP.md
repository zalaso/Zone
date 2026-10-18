# Zone roadmap

## Version 1.0 — complete open-source application

On 18 October 2026 the project changed direction from a centrally hosted beta to a reusable public GitHub release. The delivery includes the application, research tools, documentation, tests and installable artifacts. A managed public SaaS is not a release prerequisite.

| Capability | Release scope |
| --- | --- |
| Simulator and protocol | Bounded RK4 worlds, explicit human decisions, immutable predictions and public/private history separation |
| Benchmark | v0.3 with four conditions, sequential passive control, category metrics and strict pairing |
| World Forge | Versioned seeded generation, safe AST, levels 1–5 and validation pipeline |
| Scientific identification | Numeric probes, optional law AST and uncertainty; separate empirical metrics |
| Web application | Six modes, onboarding, glossary, public-measurement replay, LaTeX/MathML and reduced motion |
| Personal agents | API providers, official local ChatGPT OAuth and outbound local-model connectors |
| Accounts | Password/recovery, invited roles, ownership, CSRF, quotas, revocation and administration |
| Arena and Integrity | Idempotent trials, challenge lifecycle, embargo, contamination flags and multidimensional results |
| Operations | SQLite migration checks, health, backup/restore, release wheel, source archive and Docker |
| Public project | MIT, third-party notices, contribution and security channels, CI, release notes and checksum verification |

The earlier phases 0–13 produced the existing research and application capabilities. Hosted-beta experiments are engineering history, not a requirement to run this release or a claim of hosted-service availability. See [scope and limitations](docs/limitations.md) and [release verification](docs/release-checklist.md).

## Optional future research

Future work may add carefully validated world levels, new scientific studies, stronger external-model attestation, additional languages or deployment architectures. These require their own designs and evidence. There are no unimplemented modes advertised as usable in version 1.0. Levels beyond 5 remain explicitly unsupported, rather than silently falling back.

Bug fixes and security maintenance apply to the current release. Proposed extensions belong in issues; no implementation date, hosted SLA or research result is promised.
