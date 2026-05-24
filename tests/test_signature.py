from leadtime_hermes_plugin.signature import sign_leadtime_payload, verify_leadtime_signature


def test_signature_roundtrip():
    body = b'{"agentRunId":"run-1"}'
    timestamp = "2026-05-24T00:00:00Z"
    signature = sign_leadtime_payload(body, "secret", timestamp)

    assert verify_leadtime_signature(body, "secret", signature, timestamp)
    assert verify_leadtime_signature(body, "secret", f"sha256={signature}", timestamp)
    assert verify_leadtime_signature(body, "secret", f"t={timestamp},v1={signature}", timestamp)
    assert not verify_leadtime_signature(body, "other", signature, timestamp)
