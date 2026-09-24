from haila.api import app, health


def test_api_se_identifica_como_haila():
    status = health()
    assert status["service"] == "HAILA"
    assert status["red_flags"] == "deterministic-v3.1"
    assert status["distractor_memory"] is True
    assert status["distractor_rules"] is True


def test_backend_operacional_nao_expoe_parecerista_llm():
    paths = {route.path for route in app.routes}
    assert "/requests/{request_id}/reviews" in paths
    assert "/requests/{request_id}/reviews/llm" not in paths
