"""/decree's made-up proclamations (procbot/decree.py)."""

import random
from datetime import date

import pytest

from procbot import decree, spelling


@pytest.mark.parametrize("n, words", [(1, "first"), (5, "fift"), (18, "eighteenth"), (20, "twentieth"),
                                      (22, "two and twentieth"), (30, "thirtieth"), (31, "one and thirtieth")])
def test_ordinals_as_the_datelines_have_them(n, words):
    assert decree.ordinal(n) == words


@pytest.mark.parametrize("kind", [decree.AGAINST, decree.FOR, decree.CONCERNING])
@pytest.mark.parametrize("voice", ["king", "queen"])
def test_make(kind, voice):
    made = decree.make("pineapple on pizza", kind, voice, date(2026, 10, 18), random.Random(1))
    assert made.render(made.title) == f"A Proclamation {kind} pineapple on pizza."
    assert made.heading == ("By the King." if voice == "king" else "By the Queene.")
    body = made.render(" ".join(made.paragraphs))
    assert body.startswith("WHereas") and body.count("pineapple on pizza") == 2
    assert ("Her " if voice == "queen" else "His ") in body and ("His " not in body if voice == "queen" else True)
    assert "the eighteenth day of October" in made.dateline


def test_tidying_leaves_the_thing_as_typed():
    made = decree.make("iou vouchers", decree.AGAINST, on=date(2026, 1, 1), rng=random.Random(2))
    tidied = made.render(" ".join(made.paragraphs), spelling.modern)
    assert "iou vouchers" in tidied and "Majestie" in tidied and "vnderstand" not in tidied


def test_every_template_fills():
    for templates in list(decree.OPENINGS.values()) + list(decree.COMMANDS.values()):
        for template in templates:
            text = template.format(thing=decree.THING, majesty="His Maiestie", pronoun="His")
            assert decree.THING in text and "{" not in text.replace(decree.THING, "")
