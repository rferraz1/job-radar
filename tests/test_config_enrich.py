import importlib


def test_config_enrich_defaults(monkeypatch):
    for var in ("LLM_PROVIDER", "GEMINI_API_KEY", "LIMIAR_COMPAT_IMEDIATO", "CV_PATH"):
        monkeypatch.delenv(var, raising=False)
    import config
    importlib.reload(config)
    assert config.LLM_PROVIDER == "gemini"
    assert config.GEMINI_API_KEY == ""
    assert config.LIMIAR_COMPAT_IMEDIATO == 85
    assert config.CV_PATH.endswith(".html")
    assert isinstance(config.GREENHOUSE_BOARDS, list)
    assert config.ENRICH_MAX_FALHAS_LLM >= 1


def test_config_enrich_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LIMIAR_COMPAT_IMEDIATO", "70")
    import config
    importlib.reload(config)
    assert config.LLM_PROVIDER == "anthropic"
    assert config.LIMIAR_COMPAT_IMEDIATO == 70
