# Getting started

Zone is a self-hosted research application, not an account on a central service. Start without an AI; the default numerical baseline is explicitly identified as **not an LLM**. The interface and its in-app guide are currently in Italian.

## Install a release (Python 3.11+; Node is not required)

Download the wheel from [releases](https://github.com/zalaso/Zone/releases) and verify its SHA-256 against `SHA256SUMS`. Install it in a virtual environment.

PowerShell, from a folder where you want to keep your installation:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install "hidden-physics-lab[workspace] @ https://github.com/zalaso/Zone/releases/download/v1.0.0/hidden_physics_lab-1.0.0-py3-none-any.whl"
.\.venv\Scripts\python.exe -m hidden_lab workspace --data ./zone-data
```

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'hidden-physics-lab[workspace] @ https://github.com/zalaso/Zone/releases/download/v1.0.0/hidden_physics_lab-1.0.0-py3-none-any.whl'
.venv/bin/python -m hidden_lab workspace --data ./zone-data
```

Open **http://127.0.0.1:8767**. Keep the terminal running; Ctrl+C stops the server without deleting data. Start the same command again to resume the same installation. The installed `zone` command is an alias for `python -m hidden_lab`.

## Install from source

Requires Python 3.11+, Node 22 and pnpm 10.28.0. The frontend must be built once; the release wheel already includes it.

```sh
git clone https://github.com/zalaso/Zone.git
cd Zone
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[workspace]'
cd frontend
pnpm install --frozen-lockfile
pnpm run build
cd ..
.venv/bin/python -m hidden_lab workspace --data ./zone-data
```

On Windows substitute `.\.venv\Scripts\python.exe` for `.venv/bin/python` and `python` for `python3`. Installing dependencies uses the package registries; running the default lab does not contact a model provider.

## First investigation

1. Click **Crea account**, choose a username and a password of at least 12 characters, and save the one-time recovery code. Then click **Ho conservato il codice**. Creating an account does not connect or charge an AI.
2. Click **Inizia senza AI** or choose **Scientist**, select a world and click **Crea sessione**. A level-1 world and a diagnostic Arena challenge are generated on first startup.
3. Write the purpose of your experiment. Set position and velocity on x/y, duration and measurement interval. Send the request, approve it and choose **Esplorazione**. Finally click **Esegui esperimento**: approval alone does not launch anything.
4. Play back the public measurements, enter an hypothesis or switch to **Verifica con previsione** for a subsequent experiment. Verification requires predicted positions at all approved times before the launch.
5. Conclude with evidence, limits and alternatives, including insufficient information when appropriate. The final probes ask for accelerations on new states. Results remain separate by dimension and interpolation/extrapolation category.

Use **Guida a Zone** for every mode, glossary and technical explanations. Sessions are stored automatically and can be reopened from **Le mie sessioni**. Plain-language explanations and numeric tables accompany the visualizations.

## Host-owner access

The first startup creates an administrative invite in `zone-data/admin-key.txt`, readable only by trusted local users. Sign in using **Ho un invito** and that key. The first self-registered account is a member, never automatically an administrator. The key is not printed in server logs, sent to a provider or served by the website.

The administrative key expires after 30 days; rotate it in the admin console. For trusted-host recovery:

```sh
python -m hidden_lab identity recover-admin --db zone-data/workspace.db --handle zone_admin
```

This explicitly prints a replacement key in your trusted terminal. Store it securely; an older `admin-key.txt` becomes invalid after rotation. The administrator manages invitations, quotas and Arena challenges. Keep all files in `zone-data` private and out of Git.

## Bring your own AI

See [AI connections](ai-connections.md). API keys are optional. ChatGPT and Ollama use a connector on your computer; no inbound local port is exposed. Model IDs are explicit, no model is downloaded automatically, and changing a connection applies to new sessions. A real inference starts only when you request an agent step.

## Troubleshooting

| Problem | Action |
| --- | --- |
| `Interfaccia non compilata` | Use the release wheel, or run the frontend build when installing from source. |
| Port already in use | Stop your previous Zone terminal, or use `--port 8768`; open the new URL. |
| Login/CSRF error | Use the exact printed origin (`127.0.0.1`, not `localhost`), refresh and sign in again. |
| `Limite di richieste raggiunto` | Wait at least 60 seconds, then refresh the state. Do not resubmit a launch automatically. |
| Lost password | Use your recovery code on the access page; this revokes earlier sessions and AI connections. No email recovery is provided. |
| Connector offline | Keep the connector terminal open and use the exact model and origin configured in the site. |
| Provider error after a launch | The experiment stays recorded. Refresh the session; do not rerun it to repair a model response. |
| Encryption key lost | Existing API credentials cannot be decrypted. Restore the original key or disconnect and add fresh credentials. |

For an external server follow [self-hosting](self-hosting.md); do not publish a raw HTTP development port.
