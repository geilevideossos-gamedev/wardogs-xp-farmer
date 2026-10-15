from heli_farmer.config import load_config


def test_local_config_overrides_nested_values(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "game_region:\n  left: 0\n  width: 1920\nkeys:\n  stop: f2\n", encoding="utf-8"
    )
    (tmp_path / "config.local.yaml").write_text("game_region:\n  left: 100\n", encoding="utf-8")

    config = load_config(tmp_path / "config.yaml")

    assert config["game_region"] == {"left": 100, "width": 1920}
    assert config["keys"]["stop"] == "f2"


def test_without_local_config(tmp_path):
    (tmp_path / "config.yaml").write_text("keys:\n  stop: f2\n", encoding="utf-8")

    assert load_config(tmp_path / "config.yaml") == {"keys": {"stop": "f2"}}


def test_repo_config_has_required_sections():
    config = load_config("config.yaml")

    assert config["keys"]["stop"] == "f2"
    assert {config["keys"][k] for k in ("shop", "drop", "up", "down")} == {
        "b",
        "g",
        "shift",
        "ctrl",
    }
    assert config["timeouts"]["max_hold_s"] > 0
    assert {"bakurani", "ozeti", "zestafona"} <= config["maps"].keys()
    assert config["game_region"]["width"] == 1920
    assert config["game_region"]["height"] == 1080
    assert config["timeouts"]["unknown_state_s"] > 0
