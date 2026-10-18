# Bring your own AI

The default lab needs no provider account, credentials, billing setup or downloaded model. Choose **Scientist** for manual work. Without a personal connection, AI modes use an explicitly labelled numerical baseline, not a language model.

All real clients receive only public instructions, message contract and public history. They do not receive the repository, private law, seed, test answers, filesystem or terminal tools. A model call and an experiment consume separate budgets. Zone does not impose a monetary ceiling at the provider; configure one in your provider account.

## Provider API

OpenAI, Anthropic and Gemini are supported. Install the matching extra, or all clients:

```sh
python -m pip install 'hidden-physics-lab[all-llm] @ https://github.com/zalaso/Zone/releases/download/v1.0.0/hidden_physics_lab-1.0.0-py3-none-any.whl'
python -m hidden_lab workspace --data ./zone-data --enable-personal-api
```

Use the same virtual-environment Python as the original installation. For editable source use `python -m pip install -e '.[workspace,all-llm]'`.

In **Connessioni AI**, choose the provider, give a descriptive name, enter an available model ID and save your API key. Keys are encrypted on the server. The master key is read from `ZONE_CONNECTION_KEY` when set; otherwise `--enable-personal-api` creates and reuses `zone-data/connection.key` with restrictive permissions. Keep that key separate from database backups, and preserve it across restarts. Starting without the flag leaves server-side API storage disabled. Saving a connection makes no inference request.

Alternatively select **Sul mio computer, con il connettore**. The provider key stays in `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` in the connector's environment. Do not put the value in a command argument, repository, screenshot or public log.

## ChatGPT plan

Install the `chatgpt` extra. In the site choose **ChatGPT**, enter a model available to your account and prepare the connection. Save the one-time connector key. In another terminal run:

```sh
python -m hidden_lab connector --origin http://127.0.0.1:8767 --local-http --provider chatgpt --model YOUR_MODEL_ID --login --allow-inference --max-jobs 8
```

The connector asks for its key with hidden input. ChatGPT authorization happens in your local browser; OAuth tokens remain in Zone's protected local credential store. The Zone account password is separate. Model eligibility and plan limits are controlled by OpenAI. There is no automatic fallback to billed API access; inspect plan usage and credit settings before real experiments.

This follows the [official open-source/local Sign in with ChatGPT flow](https://developers.openai.com/siwc/token-sharing-open-source), whose [preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations) apply. A remotely hosted multi-user app needs OpenAI's applicable enrollment before offering direct plan usage. This release uses the local connector for individual users of a remote Zone instance; it does not claim a universal hosted subscription integration.

Optional CLI tools: `python -m hidden_lab chatgpt --help` for account selection, available models and logout. OAuth login is user initiated; the release tests never log in or infer with a real account.

## Ollama

Install the `ollama` extra and have Ollama running with a model you already installed. Zone never downloads models. Choose **Ollama locale** in the site and use the same exact model ID:

```sh
python -m hidden_lab connector --origin http://127.0.0.1:8767 --local-http --provider ollama --model YOUR_INSTALLED_MODEL --allow-inference --max-jobs 8
```

Cloud-suffixed models are refused. The connector calls the fixed local Ollama endpoint; do not expose Ollama to the Internet.

## Using a remote Zone instance

Replace the connector origin with your instance's exact HTTPS origin and omit `--local-http`. The connector makes outbound requests; no local inbound port or remote shell access is provided. Leave it open while requesting agent steps. Its key is scoped to one connection, expires in 30 days and can be revoked from the site. Changing the selected connection does not replace a running session's model.

Watch an Agent/Human vs AI allow at most one bounded correction where configured. Personal Arena does not retry invalid responses. Network failure stops the call and never repeats an already executed experiment. Returned provider usage, model and settings are recorded without credentials; costs may be unavailable. LLM replies are not promised to be exactly reproducible.
