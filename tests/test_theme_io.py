from zlog.core.theme import LIGHT
from zlog.core.theme_io import is_valid_hex, theme_from_dict, theme_to_dict


def test_is_valid_hex():
    assert is_valid_hex("#fff")
    assert is_valid_hex("#ffFFff")
    assert not is_valid_hex("fff")
    assert not is_valid_hex("#ff")
    assert not is_valid_hex("#gggggg")
    assert not is_valid_hex(123)
    assert not is_valid_hex(None)


def test_round_trip_is_identical():
    data = theme_to_dict(LIGHT)
    rebuilt = theme_from_dict(data, base=LIGHT)
    assert rebuilt == LIGHT


def test_missing_fields_fall_back_to_base():
    data = {"name": "My Theme", "window": "#123456"}  # everything else missing
    theme = theme_from_dict(data, base=LIGHT)
    assert theme.name == "My Theme"
    assert theme.window == "#123456"
    assert theme.text == LIGHT.text
    assert theme.level_colors == LIGHT.level_colors
    assert theme.level_text == LIGHT.level_text


def test_bad_hex_falls_back_per_field():
    data = theme_to_dict(LIGHT)
    data["text"] = "not-a-color"
    data["window"] = "#0000ff"  # valid, kept
    theme = theme_from_dict(data, base=LIGHT)
    assert theme.text == LIGHT.text  # fell back
    assert theme.window == "#0000ff"  # kept


def test_level_dict_falls_back_per_key():
    data = theme_to_dict(LIGHT)
    data["level_colors"] = {"W": "#112233", "E": "garbage"}  # F missing entirely
    theme = theme_from_dict(data, base=LIGHT)
    assert theme.level_colors["W"] == "#112233"
    assert theme.level_colors["E"] == LIGHT.level_colors["E"]
    assert theme.level_colors["F"] == LIGHT.level_colors["F"]


def test_non_dict_input_falls_back_entirely():
    theme = theme_from_dict("not a dict", base=LIGHT)
    assert theme == LIGHT


def test_non_dict_level_field_falls_back_entirely():
    data = theme_to_dict(LIGHT)
    data["level_text"] = "oops"
    theme = theme_from_dict(data, base=LIGHT)
    assert theme.level_text == LIGHT.level_text


def test_blank_name_falls_back_to_base_name():
    data = theme_to_dict(LIGHT)
    data["name"] = "   "
    theme = theme_from_dict(data, base=LIGHT)
    assert theme.name == LIGHT.name
