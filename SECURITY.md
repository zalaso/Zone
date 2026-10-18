# Security

Report vulnerabilities privately through [GitHub Private Vulnerability Reporting](https://github.com/zalaso/Zone/security/advisories/new). Do not put credentials, private worlds, databases or exploit details in public issues. If that channel is unavailable, contact [the maintainer](https://github.com/zalaso) to arrange a private channel before sharing sensitive material.

## Supported scope

Security fixes target the current 1.x release. Earlier development releases should be upgraded. There is no guaranteed response time or paid support agreement. This repository is software you run yourself; it does not provide a centrally operated public laboratory.

Reproduce reports on your own local installation with synthetic data. Include the release, affected route or component, prerequisites, impact and minimal reproduction. Testing systems you do not own is not authorized.

## Trust boundaries

- The host operator controls the simulator, database, process environment and backups. This is not a sandbox against a malicious host administrator.
- Models receive explicitly constructed public messages, never the private world, repository, README, credentials, filesystem or terminal tools.
- A model step cannot authorize a launch. Approval, exploration/verification and execution remain separate human actions; silence is never approval.
- Account cookies are HttpOnly and SameSite Strict, with CSRF and exact-origin checks. HTTPS is required for external origins. Do not disable these checks behind a proxy.
- Provider credentials are either kept on the user's computer by an outbound connector or encrypted with a separately managed server key. No inference or provider fallback runs at startup.
- SQLite, logs, `admin-key.txt`, `connection.key`, OAuth stores, private suites, commitments and backups must stay outside Git, static directories, release assets and CI artifacts. Local data directories must only be readable by trusted users.

## Self-hosting

The default listener and Docker publication are loopback only. An Internet deployment requires an exact HTTPS origin, reverse proxy, independent backups, resource limits, retention policy and an operator. Registration outside loopback is opt-in. See [self-hosting](docs/self-hosting.md), [data handling](docs/privacy.md) and the [threat model](docs/threat-model.md).

Backups are not encrypted by Zone. Protect them independently and retain the connection encryption key separately; without the original key, stored provider credentials cannot be decrypted. On compromise stop the instance, preserve controlled evidence, revoke sessions and provider access, rotate credentials and retire exposed test worlds before reopening.
