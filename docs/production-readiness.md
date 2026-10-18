# Release and operational readiness

For the current software release, use [the release checklist](release-checklist.md). Version 1.0 is a reusable self-hosted application, not a managed public service. A green software release does not certify an arbitrary Internet deployment.

A host operator must choose an exact HTTPS origin, isolated network publication, trusted administrator, storage and backup protection, capacity limits, monitoring and data policy. See [self-hosting](self-hosting.md), [privacy](privacy.md), [SECURITY](../SECURITY.md) and [threat model](threat-model.md).

Tests verify state transitions, identity boundaries, quotas, ciphertext storage, idempotence, migration, backup/restore and scientific payload separation on synthetic data. LLM integrations use simulated transports in automation. A separate authorized real-model study is needed for scientific claims.

Supported operating scope: one trusted application process and SQLite database. No multi-node capacity, commercial SLA, general equation proof or competitive external-model attestation is advertised. These explicit limits do not prevent local research or a deliberately sized self-hosted installation.

## Public distribution audit — 2026-10-18

Production audit: **88/100, strong for the supported self-hosted software scope**, with no outstanding release blocker in the checked evidence. This is a prioritization judgment, not a mathematical security score or certification of an Internet deployment.

- **Blockers:** none in the validated release scope. All six offline CI jobs pass; the release includes the UI and both installation formats.
- **High-value future work:** independent real-model studies, capacity measurements on an intended host and external accessibility/security review. These are not features required to start the shipped local laboratory.
- **Evidence checked:** 298 local Python tests, 35 UI tests, two frontend guard tests, Linux/Windows Python 3.11/3.12 CI, clean wheel installation, Docker restart/live restore, real local browser scenarios including daily-world persistence, public/private payload tests, documentation links, archive allowlists, reachable Git blob scans, dependency advisories and GitHub private security reporting.
- **Evidence missing:** real provider trials for this release, macOS CI, hostile multi-node operation and independent penetration/accessibility certification. A historical small model pilot is kept separate from current simulated-transport evidence.
- **Operational boundary:** the repository distributes an application; it does not operate every installation or attest external agents. HTTPS, backups, capacity and data policies belong to each host operator. GitHub branch-governance settings remain the repository owner's choice and are not represented as an implemented application control.
- **Next action:** install the tagged wheel or build the documented Compose deployment; use the offline path first. A real provider test is optional and user initiated, with the user's own model and allowance.
