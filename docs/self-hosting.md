# Self-hosting

Zone is software you operate, not a hosted service supplied by this repository. The default deployment is a single process and SQLite database, bound to loopback. Models remain opt-in and user funded. Read [SECURITY](../SECURITY.md) and [data handling](privacy.md).

## Docker on one computer

```sh
git clone https://github.com/zalaso/Zone.git
cd Zone
docker compose up --build
```

Open http://127.0.0.1:8767, create a member account and save its recovery code. The named volume contains private data; containers can be recreated without losing it. `docker compose down` stops Zone and retains the volume. Do not add `--volumes` unless you intend to delete your installation.

For host-owner access, read `/data/admin-key.txt` from the running container in your trusted terminal and use **I have an invite**. Do not post that key in an issue. Administrative keys expire; rotate them or use the documented `identity recover-admin` command inside your own container.

API storage is disabled by default. To enable personal provider keys:

```sh
docker compose -f compose.yaml -f compose.api.yaml up --build
```

The image includes provider SDKs, but no credentials or automatic inference. The API overlay enables an encrypted vault with a persistent master key at `/data/connection.key`, unless `ZONE_CONNECTION_KEY` is supplied independently. Connector-only installations need no server-side provider credentials.

The root Dockerfile also supports `--build-arg ZONE_EXTRAS=workspace` for a smaller offline/connector-only image without API SDKs. The older `serve` command and an offline `backend` image remain supported for research automation.

## HTTPS server

1. Choose a host you control, back it up and provision a domain with valid HTTPS. Do not expose the application port directly.
2. Set `ZONE_ORIGIN` to the exact HTTPS browser origin (no trailing slash) in your deployment environment. The Compose port remains on `127.0.0.1`.
3. Put a trusted reverse proxy in front of that port. `deploy/zone.caddy` is an example using `zone.example.org`; replace the hostname. If the proxy is itself containerized, create an explicit private network instead of opening the port on all interfaces.
4. External self-registration remains disabled unless the operator explicitly adds `--open-registration` to the `workspace` command. Bootstrap the owner account first and review quotas before opening registration.
5. Keep secure cookies, exact-origin and CSRF checks enabled. Forward only to the configured private listener; Zone does not trust arbitrary forwarded headers.

Equivalent native command (after installing/building the release):

```sh
python -m hidden_lab workspace --data /srv/zone-data --origin https://zone.example.org --open-registration
```

The address is an example, not a Zone-operated endpoint. Direct multi-user hosted ChatGPT plan usage requires OpenAI's applicable enrollment; individual users can instead run their own local connector. No LLM requests should be made as a deployment health check.

## Persistence, backup and recovery

Private installation files include `workspace.db`, `admin-key.txt` and, when enabled, `connection.key`. OAuth connector credentials live in their separate protected local store. Never mount the data directory as static web content or commit it.

For a consistent live database backup:

```sh
python -m hidden_lab ops backup --db zone-data/workspace.db --out /private-backups/zone.sqlite3
python -m hidden_lab ops check --db /private-backups/zone.sqlite3
```

Choose a new backup destination. Protect and encrypt backups independently; Zone does not encrypt complete backups. Preserve the connection master key in a separate protected backup, or API credentials in a restored database cannot be read. A database backup does not back up the key or OAuth stores.

Stop the instance before switching to a restored database. Restore to a **new** destination:

```sh
python -m hidden_lab ops restore --backup /private-backups/zone.sqlite3 --out /srv/zone-restored/workspace.db
python -m hidden_lab ops check --db /srv/zone-restored/workspace.db
```

Restore the matching connection key to the new private data directory, then start `workspace --data /srv/zone-restored`. Review revoked credentials, running calls and disclosed test worlds before reopening. Never rerun an interrupted experiment automatically.

## Upgrade and rollback

Read release notes, stop the process and make a verified backup before upgrading. Install the new wheel, retain the existing data path and restart. SQLite migrations are forward checked; existing benchmark files and CLI contracts remain supported where documented. There is no automatic schema downgrade. To roll back, stop the new process and restore the prior database backup into a new directory, with the previous matching application version and encryption key.

`/health/live` checks process availability; `/health/ready` checks schema/readiness. Health responses exclude credentials and private world content. Set up disk/log/backup monitoring appropriate to your server. Example maintenance units under `deploy/` are templates, not automatically installed services.

## Capacity and policy

Do not infer multi-node or high-volume capacity from local tests. SQLite and local IP limiting are intended for one trusted application process. Account quotas persist in SQLite; a common proxy can cause legitimate users to share an IP limit. Validate capacity on your target before inviting a large audience. There is no automatic billing, email service, anti-Sybil identity verification or managed operations team.

The instance operator must state retention, support and account-removal policy before accepting other people's data. See [privacy](privacy.md). These responsibilities belong to each deployment, not to the GitHub repository.
