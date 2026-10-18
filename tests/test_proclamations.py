"""The proclamations' data, searching and picking, and their embeds (procbot/proclamations.py)."""

import pytest

from procbot import proclamations


def test_data_loads():
    assert len(proclamations.PROCLAMATIONS) > 1500
    assert len(proclamations.BY_ID) == len(proclamations.PROCLAMATIONS)  # Ids are unique
    for realm in proclamations.REALMS:
        assert any(p.realm == realm for p in proclamations.PROCLAMATIONS)
    assert all(p.paragraphs and p.realm in proclamations.REALMS for p in proclamations.PROCLAMATIONS)


@pytest.mark.parametrize("modern", [False, True])
def test_every_embed_fits_discord(modern):
    for proclamation in proclamations.PROCLAMATIONS:
        embed = proclamations.embed(proclamation, modern=modern)
        assert len(embed) <= 6000, proclamation.id
        assert len(embed.title) <= 256 and len(embed.description) <= 4096 and len(embed.author.name) <= 256
        assert all(len(field.value) <= 1024 for field in embed.fields), proclamation.id


def test_search_finds_old_spellings():
    jesuits = proclamations.matching(about="jesuit")
    assert jesuits and any("Iesuit" in p.text for p in jesuits)
    assert all(proclamations.words_in("tobacco")[0].search(p.text) for p in proclamations.matching(about="tobacco"))


def test_filters_by_realm_and_monarch():
    irish = proclamations.matching(realm="ireland")
    assert irish and all(p.realm == "ireland" for p in irish)
    elizabeth = proclamations.matching(monarch="Elizabeth I", about="apparel")
    assert elizabeth and all(p.monarch == "Elizabeth I" for p in elizabeth)


def test_pick_avoids_repeats():
    candidates = proclamations.matching(about="starch")
    shown = {proclamations.pick(1, about="starch").id for _ in candidates}
    assert len(shown) == len(candidates)


def test_pick_nothing():
    assert proclamations.pick(1, about="xylophone") is None


def test_when():
    p = proclamations.PROCLAMATIONS[0]
    for date, when in [("1696-05-23", "23 May 1696"), ("1696-05", "May 1696"), ("1696", "1696")]:
        assert proclamations.Proclamation(p.id, 1, "england", "t", ("x",), date=date).when == when


def test_by():
    make = lambda **kw: proclamations.Proclamation("a1", 1, "ireland", "t", ("x",), **kw)  # noqa: E731
    assert make(issuer="Sovereign", monarch="Charles II").by == "Charles II"
    assert make(issuer="Lord Lieutenant", holder="Ormonde", monarch="Charles II").by == \
        "Lord Lieutenant (Ormonde), under Charles II"
    assert make(issuer="Lord Protector", holder="O. Cromwell", monarch="the Commonwealth").by == \
        "Lord Protector (O. Cromwell)"


def test_excerpt_gives_the_command_too():
    long = "Whereas " + "the King hath been informed of great abuses, " * 40 + \
           "and so on. We do hereby straitly charge and command all Our Subjects to stop it."
    p = proclamations.Proclamation("a1", 1, "england", "t", (long,))
    text = proclamations.excerpt(p)
    assert text.startswith("Whereas") and "We do hereby straitly charge and command" in text
    assert len(text) < proclamations.EXCERPT + proclamations.COMMAND_EXCERPT + 20


def test_links():
    p = proclamations.Proclamation("a39500", 1, "england", "t", ("x",))
    assert p.url == "https://quod.lib.umich.edu/e/eebo/A39500.0001.001"
    assert proclamations.Proclamation("a01236", 2, "england", "t", ("x",)).url.startswith(
        "https://quod.lib.umich.edu/e/eebo2/")
    assert p.source_url == "https://github.com/textcreationpartnership/A39500"


def test_monarchs_in_reign_order():
    assert proclamations.MONARCHS[0] == "Henry VII"
    assert proclamations.MONARCHS.index("Elizabeth I") < proclamations.MONARCHS.index("James I")
