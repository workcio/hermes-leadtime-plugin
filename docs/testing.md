# Testing

## Local Docker Harness

From the Leadtime repo, use:

```bash
npm run hermes-plugin-docker
```

The helper starts a clean Hermes gateway with:

- Hermes API Server on `http://localhost:18642`
- Leadtime connector webhook on `http://localhost:19338/leadtime/webhook`
- OpenRouter configured through `OPENROUTER_API_KEY`
- the Leadtime Hermes plugin installed and enabled

Create or reuse a Leadtime bot and setup code:

```bash
npm run provision-hermes-plugin -- --bot-name "Hermes Local Bot" --mode basic
```

Run the printed setup command on the Hermes machine/container. For Docker, Leadtime must be reached as:

```text
http://host.docker.internal:9221/api
```

The setup command claims the code, enables sessions, creates a bot PAT, writes `~/.hermes/leadtime/config.json`, and stores the connector webhook URL in Leadtime.

Then assign the bot to a task. Expected result:

1. Leadtime creates a task session.
2. Leadtime calls the Hermes connector webhook.
3. Hermes runs the configured agent through API Server.
4. Hermes uses the Leadtime plugin tools to add a task comment.
5. The Leadtime session reaches `done`.

## Full Mode

```bash
npm run provision-hermes-plugin -- \
  --bot-name "Hermes Full Local Bot" \
  --mode full \
  --expose-raw-api-credential-to-agent
```

Full mode enables generic OpenAPI action tools. Raw API credential exposure should only be used for trusted Hermes deployments.
