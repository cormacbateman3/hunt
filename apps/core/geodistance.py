"""How far away somebody's ground is — the browse line's one number.

County-to-county great-circle miles over the centroids distilled from the
same topology the map draws (``utilities/build_county_centroids.py``).
Honest enough for "38 miles from you" on a card; never pretends to more
precision than a county has.
"""

import json
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

_DATA = Path(__file__).resolve().parent / 'data' / 'county_centroids.json'
_EARTH_MILES = 3958.8


@lru_cache(maxsize=1)
def _centroids():
    with open(_DATA, encoding='utf-8') as fh:
        return json.load(fh)


def county_centroid(fips):
    """``[lon, lat]`` for a 5-digit county FIPS, or None."""
    if not fips:
        return None
    return _centroids().get(str(fips))


def miles_between(fips_a, fips_b):
    """Great-circle miles between two county centroids, or None.

    None whenever either side lacks a shape — a distance we can't state
    honestly is a line the card simply doesn't print.
    """
    a = county_centroid(fips_a)
    b = county_centroid(fips_b)
    if not a or not b:
        return None
    lon1, lat1 = map(radians, a)
    lon2, lat2 = map(radians, b)
    h = (sin((lat2 - lat1) / 2) ** 2
         + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2)
    return round(2 * _EARTH_MILES * asin(sqrt(h)))
