"""Hilux collectors (3rd-generation petrol Toyota Hilux, 1978-1983).

Each module exposes collect(fx_day) -> [listing records], exactly like
listings/, and uses common.hilux for identity so every source applies the
same rules. SOURCES is the registry run_daily.py --model hilux iterates.
Source names match the 620 side where the site is the same (the site and
digest share display names), so "ebay" here is eBay whichever truck.
"""

from . import ebay

SOURCES: list[tuple] = [
    ("ebay", ebay.collect),
]
