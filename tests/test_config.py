from leadtime_hermes_plugin.config import MIN_RUNNER_TIMEOUT_SECONDS, parse_config


def test_parse_config_normalizes_values():
    config = parse_config(
        {
            "leadtimeBaseUrl": "http://localhost:9221/api/",
            "webhookPath": "leadtime/webhook/",
            "hermesApiBaseUrl": "http://127.0.0.1:8642/",
            "bots": [
                {
                    "name": "Hermes",
                    "botUserId": "bot-1",
                    "botPat": "pat",
                    "webhookSecret": "secret",
                    "agentId": "default",
                    "mode": "full",
                    "exposeRawApiCredentialToAgent": True,
                }
            ],
        }
    )

    assert config.leadtime_base_url == "http://localhost:9221/api"
    assert config.webhook_path == "/leadtime/webhook"
    assert config.public_base_url == "http://localhost:9221/api/public"
    assert config.bots[0].mode == "full"
    assert config.bots[0].expose_raw_api_credential_to_agent is True
    assert config.runner_timeout_seconds == MIN_RUNNER_TIMEOUT_SECONDS


def test_parse_config_upgrades_legacy_short_runner_timeout():
    config = parse_config(
        {
            "leadtimeBaseUrl": "https://leadtime.app/api",
            "runner": {"timeoutSeconds": 900},
            "bots": [
                {
                    "botUserId": "bot-1",
                    "botPat": "pat",
                    "webhookSecret": "secret",
                }
            ],
        }
    )

    assert config.runner_timeout_seconds == MIN_RUNNER_TIMEOUT_SECONDS
