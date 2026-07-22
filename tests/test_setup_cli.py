import pytest

from leadtime_hermes_plugin.setup_cli import merge_config, normalize_leadtime_api_base_url, validate_gateway_public_url


def test_normalize_leadtime_base_url():
    assert normalize_leadtime_api_base_url("https://leadtime.app") == "https://leadtime.app/api"
    assert normalize_leadtime_api_base_url("https://leadtime.app/api/public") == "https://leadtime.app/api"


def test_merge_config_replaces_existing_bot():
    merged = merge_config(
        {
            "leadtimeBaseUrl": "old",
            "bots": [{"botUserId": "bot-1", "name": "Old"}, {"botUserId": "bot-2", "name": "Keep"}],
        },
        {
            "leadtimeBaseUrl": "new",
            "webhookPath": "/leadtime/webhook",
            "hermesApiBaseUrl": "http://127.0.0.1:8642",
            "hermesApiKey": "key",
            "runner": {"timeoutSeconds": 172800},
            "bot": {"botUserId": "bot-1", "name": "New"},
        },
    )

    assert merged["leadtimeBaseUrl"] == "new"
    assert [bot["name"] for bot in merged["bots"]] == ["Keep", "New"]


def test_connector_url_rejects_private_urls_for_leadtime_cloud():
    with pytest.raises(SystemExit) as exc:
        validate_gateway_public_url("http://100.81.173.20:9338", "https://leadtime.app/api")

    assert "Cloudflare Tunnel" in str(exc.value)


def test_connector_url_allows_local_urls_for_local_leadtime():
    validate_gateway_public_url("http://localhost:9338", "http://localhost:9221/api")
