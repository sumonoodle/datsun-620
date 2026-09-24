"""Hilux collectors (3rd-generation petrol Toyota Hilux, 1978-1983).

Each module exposes collect(fx_day) -> [listing records], exactly like
listings/, and uses common.hilux for identity so every source applies the
same rules. SOURCES is the registry run_daily.py --model hilux iterates.
Source names match the 620 side where the site is the same (the site and
digest share display names), so "ebay" here is eBay whichever truck.
"""

from . import (barnfinds, bat, carsensor, classiccars, ebay, everycar, flex,
               goonet_exchange, kijiji, kleinanzeigen, kuruma_ex, pistonheads,
               retrorides, trovit, truck2hand, yahoo_auctions)

SOURCES: list[tuple] = [
    ("ebay", ebay.collect),
    ("bringatrailer", bat.collect),
    ("classiccars", classiccars.collect),
    ("kijiji", kijiji.collect),
    ("barnfinds", barnfinds.collect),
    ("pistonheads", pistonheads.collect),
    ("retrorides", retrorides.collect),
    ("trovit", trovit.collect),
    ("kleinanzeigen", kleinanzeigen.collect),
    ("goonet_exchange", goonet_exchange.collect),
    ("carsensor", carsensor.collect),
    ("yahoo_auctions", yahoo_auctions.collect),
    ("truck2hand", truck2hand.collect),
    ("flex", flex.collect),
    ("kuruma_ex", kuruma_ex.collect),
    ("everycar", everycar.collect),
]
