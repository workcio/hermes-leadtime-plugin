from leadtime_hermes_plugin.setup_cli import merge_config, normalize_leadtime_api_base_url


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
            "runner": {"timeoutSeconds": 900},
            "bot": {"botUserId": "bot-1", "name": "New"},
        },
    )

    assert merged["leadtimeBaseUrl"] == "new"
    assert [bot["name"] for bot in merged["bots"]] == ["Keep", "New"]
