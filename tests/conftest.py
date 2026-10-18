import os

os.environ["PROCBOT_NO_DOTENV"] = "1"  # Never read a real .env (or token) in the tests.

import pytest  # noqa: E402

from procbot import db, proclamations  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    db.init(":memory:")
    proclamations.recent.clear()
    yield
    db.conn.close()
