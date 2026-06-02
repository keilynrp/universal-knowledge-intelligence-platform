from backend.cache.base import make_key, MISS


def test_make_key_joins_with_none_sentinel():
    assert make_key(("authority", None, "x")) == "authority|\x00|x"


def test_make_key_is_deterministic():
    assert make_key((1, "a")) == make_key((1, "a"))


def test_make_key_distinguishes_none_from_empty_string():
    assert make_key((None,)) != make_key(("",))


def test_miss_is_distinct_singleton():
    assert MISS is MISS
    assert MISS is not None
