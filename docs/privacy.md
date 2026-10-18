# Data handling for self-hosted installations

Zone does not send analytics to a central Zone service. You control the installation. The following describes application behavior; it does not replace the policy an operator must supply when hosting other users.

| Data | Storage and access |
| --- | --- |
| Account username, password hash, recovery hash | Private SQLite database; password and recovery code are never sent to models. Recovery code is shown once. |
| Browser session | Opaque HttpOnly cookie, hashed on the server; expiry, idle limit and revocation checks. |
| Scientific messages, decisions, observations and predictions | Persisted event history; visible to the owner, authorized staff and that session's model as public scientific context. |
| World law, seed, truth and scoring grids | Private simulator/database material; omitted from provider payloads. |
| API credentials in server vault | AES-GCM ciphertext bound to owner, connection, provider and model. Master key is outside the database. |
| API/ChatGPT credentials in a connector | Remain on the user's computer; connector key is scoped and stored hashed by the server. |
| Provider settings and returned usage | Private technical audit without credentials. Monetary cost may be unavailable. |

The default offline baseline makes no provider requests. When you request a real model step, the selected provider receives public instructions, schema and scientific history. That provider's data policy, plan limits and charges apply. A local model receives the same public messages through your local runtime. No model is given filesystem, terminal or Session-object access.

Avoid personal information in free-text scientific messages: the application cannot prevent a person from intentionally copying it into the public context. Operator theory suggestions are recorded and can influence scientific results.

Password recovery revokes existing login sessions and personal AI connections. Disconnecting a connection removes its stored secret and cancels queued work, without changing a session to a different provider. Historical scientific records remain; deleting access is not erasing research data.

There is no email recovery, automatic retention/purge or self-service permanent account deletion in this release. A host operator controls removal/export and backup retention on their installation, must coordinate changes with active trials and immutable audit needs, and must tell users their policy. The GitHub maintainer cannot inspect or delete data from independently run instances. On a single-user computer, stopping Zone and removing your chosen private data directory and associated backups removes that installation; this is destructive and must be done by its owner deliberately.

Database backups are not encrypted automatically. Keep data, encryption keys and OAuth stores out of Git, CI artifacts, images, public static directories and issue attachments. For recovery and operational responsibilities see [self-hosting](self-hosting.md).
