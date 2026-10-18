"""procbot/content.py: tagging proclamations, and which ones each server's filters allow."""

import re

import pytest

from procbot import content, proclamations
from procbot.content import FULL, MILD, OFF


@pytest.mark.parametrize("text, expected", [
    ("A Proclamation for the better confining of Popish Recusants.", {"religion": FULL}),
    ("A Proclamation for the banishing of Iesuites and Seminarie Priests.", {"religion": MILD}),
    ("Quakers and other Fanaticks assembling in Conventicles.", {"religion": FULL}),
    ("forbidding the disorderly trading with the saluages in New England", {"peoples": FULL}),
    ("Rogues, Vagabonds calling themselves Egyptians", {"peoples": FULL}),
    ("the late damnable Plot of the Turks", {"peoples": MILD}),
    ("any person who shall bring in the Person of James Duke of Monmouth Alive or Dead", {"violence": FULL}),
    ("upon pain of death", {"violence": MILD}),
    ("the detestable and abominable Vice of Buggery, committed with Man or Beast; All Rape and Carnal Ravishments",
     {"lgbt": FULL, "sex": FULL}),
    ("designing to Ravish, and against her Will to Marry Mary Wharton", {"sex": FULL}),
    ("for preventing the spreading of the Plague", {"plague": FULL}),
    ("to avoid the danger of the Infection", {"plague": MILD}),
    # Not what they look like
    ("any part of Our Army shall happen to be Quartered upon their March", {}),  # Billeting
    ("Free-quartering, or other illegal payments", {}),
    ("each Parish, Hamlet, Ward, Hundred, Lath, Rape, Wapentake, or any other Division", {}),  # Sussex
    ("to the bailife or high constable of euery hundred rape, lath, or wapentake", {}),
    ("A Proclamation against the excesse of Apparell, and the vse of Starch.", {}),
    ("A Proclamation concerning Tobacco.", {}),
])
def test_tags(text, expected):
    assert content.tag(text) == expected


def test_allowed():
    assert content.allowed({}, content.every(OFF))
    assert content.allowed({"violence": MILD}, content.every(MILD))
    assert not content.allowed({"violence": FULL}, content.every(MILD))
    assert not content.allowed({"violence": MILD, "lgbt": MILD}, content.every(FULL, lgbt=OFF))


def test_presets():
    assert [p.key for p in content.PRESETS] == ["tame", "default", "grim", "unabridged"]
    for preset in content.PRESETS:
        assert set(preset.limits) == set(content.BY_KEY)
        assert content.preset_for(dict(preset.limits)) is preset
    assert content.preset_for(content.every(FULL, violence=OFF)) is None
    # The default keeps contempt for other peoples, sex and LGBTQ+ people out; grim keeps the bigotry out.
    for key in ("peoples", "sex", "lgbt"):
        assert content.DEFAULT.limits[key] == OFF
    for key in ("peoples", "lgbt"):
        assert content.PRESETS_BY_KEY["grim"].limits[key] == OFF


def test_categories_fit_discord():
    for category in content.CATEGORIES:
        assert re.fullmatch(r"[a-z]{1,32}", category.key)
        assert len(f"How much {category.name.lower()} to allow in this channel") <= 100
        assert len(category.about) < 900


# A tame server must see none of this.
GRIM = re.compile(r"\bpapist|\bpopish|\bpopery|\bdead or a[lv]i[uv]e|\ba[lv]i[uv]e or dead|\bquartered alive|"
                  r"\bdrawn and quartered|\bmassacre|\bplague|\bpestilence|\bbugger|\bsodom|\bravish|\bsa[uv]age|"
                  r"\bsaluage|\bnegro|\bblack-?a-?moor|\b[ij]ewes?\b|\bpain(e)? of death|\bhanged\b", re.I)


def test_a_tame_server_sees_nothing_grim():
    tame = content.PRESETS_BY_KEY["tame"].limits
    leaks = [p.id for p in proclamations.PROCLAMATIONS if content.allowed(p.tags, tame) and GRIM.search(p.text)]
    assert leaks == []


def test_every_preset_leaves_plenty():
    for preset in content.PRESETS:
        assert len(proclamations.matching(preset.limits)) >= 1000, preset.key
