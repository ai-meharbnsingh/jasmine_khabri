"""Geographic tier classifier and filter."""

TIER_1_CITIES: frozenset[str] = frozenset()
TIER_2_CITIES: frozenset[str] = frozenset()
GOV_SOURCES: frozenset[str] = frozenset()


def classify_geo_tier(article):
    raise NotImplementedError


def filter_by_geo_tier(articles):
    raise NotImplementedError
