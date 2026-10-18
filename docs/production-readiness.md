# Release and operational readiness

For the current software release, use [the release checklist](release-checklist.md). Version 1.0 is a reusable self-hosted application, not a managed public service. A green software release does not certify an arbitrary Internet deployment.

A host operator must choose an exact HTTPS origin, isolated network publication, trusted administrator, storage and backup protection, capacity limits, monitoring and data policy. See [self-hosting](self-hosting.md), [privacy](privacy.md), [SECURITY](../SECURITY.md) and [threat model](threat-model.md).

Tests verify state transitions, identity boundaries, quotas, ciphertext storage, idempotence, migration, backup/restore and scientific payload separation on synthetic data. LLM integrations use simulated transports in automation. A separate authorized real-model study is needed for scientific claims.

Supported operating scope: one trusted application process and SQLite database. No multi-node capacity, commercial SLA, general equation proof or competitive external-model attestation is advertised. These explicit limits do not prevent local research or a deliberately sized self-hosted installation.
