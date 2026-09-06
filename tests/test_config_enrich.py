import importlib


def test_config_enrich_defaults(monkeypatch):
    # Neutraliza load_dotenv: config.py o chama no import, e um .env real no
    # repo (produção cria um — ver deploy/README) sobrescreveria os defaults
    # que este teste verifica. `from dotenv import load_dotenv` no reload pega
    # esta versão no-op.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    for var in ("LLM_PROVIDER", "GEMINI_API_KEY", "GEMINI_MODEL",
                "LIMIAR_COMPAT_IMEDIATO", "CV_PATH", "GREENHOUSE_BOARDS"):
        monkeypatch.delenv(var, raising=False)
    import config
    importlib.reload(config)
    try:
        assert config.LLM_PROVIDER == "gemini"
        assert config.GEMINI_API_KEY == ""
        assert config.GEMINI_MODEL == "gemini-flash-latest"
        assert config.LIMIAR_COMPAT_IMEDIATO == 85
        assert config.CV_PATH.endswith(".html")
        assert isinstance(config.GREENHOUSE_BOARDS, list) and config.GREENHOUSE_BOARDS
        assert config.ENRICH_MAX_FALHAS_LLM >= 1
    finally:
        importlib.reload(config)  # restaura o estado real pra não vazar pros outros testes


def test_config_enrich_from_env(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LIMIAR_COMPAT_IMEDIATO", "70")
    import config
    importlib.reload(config)
    try:
        assert config.LLM_PROVIDER == "anthropic"
        assert config.LIMIAR_COMPAT_IMEDIATO == 70
    finally:
        importlib.reload(config)
