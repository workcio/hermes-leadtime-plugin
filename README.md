# Leadtime Hermes Plugin

Connect Leadtime self-hosted agent sessions to a customer-owned Hermes Agent.

This repository has two pieces:

- A Hermes plugin that registers Leadtime tools inside Hermes.
- A connector listener owned by the Hermes gateway lifecycle. It receives signed Leadtime session webhooks on its own port, starts Hermes API Server runs, streams run events back into Leadtime, and marks sessions done or failed.

## Install

```bash
hermes plugins install workcio/hermes-leadtime-plugin --enable
pipx inject hermes-agent 'leadtime-hermes-plugin @ git+https://github.com/workcio/hermes-leadtime-plugin.git'
```

## Update

Update both the Hermes directory plugin and its Python installation, then restart the gateway:

```bash
hermes plugins update leadtime
pipx runpip hermes-agent install --upgrade 'leadtime-hermes-plugin @ git+https://github.com/workcio/hermes-leadtime-plugin.git'
```

The existing Leadtime configuration and credentials are preserved; no new setup code is required.

For local development from this checkout:

```bash
pip install -e .
mkdir -p ~/.hermes/plugins/leadtime
cp plugin.yaml ~/.hermes/plugins/leadtime/plugin.yaml
cat > ~/.hermes/plugins/leadtime/__init__.py <<'PY'
from leadtime_hermes_plugin import register
PY
hermes plugins enable leadtime
```

## Configure With Leadtime Setup Code

Generate a setup code in Leadtime from a bot settings page, then run on the Hermes machine:

```bash
leadtime-hermes-setup \
  --leadtime-base-url https://leadtime.app/api \
  --claim lt_conn_... \
  --connector-public-url https://your-hermes-connector.example.com \
  --agent-id default \
  --mode basic
```

The setup command claims the one-time code, enables Leadtime task sessions for the bot, creates a bot PAT, writes `~/.hermes/leadtime/config.json`, and updates Hermes config so the `leadtime` plugin is enabled.

Restart Hermes Gateway:

```bash
API_SERVER_ENABLED=true API_SERVER_KEY=local-dev hermes gateway
```

Leadtime should send webhooks to:

```text
https://your-hermes-connector.example.com/leadtime/webhook
```

Expose only the Leadtime connector port publicly. The connector starts and stops with Hermes Gateway, while the Hermes API server stays private on the machine or private network. If the connector URL is localhost, LAN, or Tailscale-only while using Leadtime Cloud, setup stops before claiming the code and prints options such as Tailscale Funnel, a named Cloudflare Tunnel, or an HTTPS reverse proxy.

## Modes

- `basic`: Hermes gets narrow task tools: read task, add comment, list statuses, update status.
- `full`: Hermes also gets generic public API actions discovered from Leadtime OpenAPI.
- `full` with raw API credential exposure: the run prompt includes the bot bearer token and OpenAPI URL for trusted scripting.

## Local Docker Harness

From the Leadtime repo:

```bash
npm run hermes-plugin-docker
npm run provision-hermes-plugin -- --bot-name "Hermes Local Bot" --mode basic
```

Run the printed setup command against the Docker harness. Use `http://host.docker.internal:9221/api` as the Leadtime base URL from inside Docker.

## Security

- The connector verifies Leadtime HMAC-SHA256 webhook signatures before accepting a session.
- One Leadtime bot maps to one bot PAT and one webhook signing secret.
- Only the wrapper/connector updates session status and activity.
- Hermes tools call Leadtime with the configured bot PAT, so normal Leadtime audit and permissions still apply.
- Do not expose raw bot credentials to the agent unless the Hermes instance is trusted.
