from src.shared.config.config import Settings, get_config

def test_settings_load():
    settings = Settings()
    assert settings.config_path.exists()

def test_config_loads():
    settings = Settings()
    config = get_config(settings.config_path)

    assert "pipeline" in config