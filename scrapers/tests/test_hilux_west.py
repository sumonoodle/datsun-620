"""Hilux collectors, Western sources on the 620's existing sites: Bring a
Trailer, ClassicCars.com, Kijiji, Barn Finds, PistonHeads, Retro Rides,
Trovit and Kleinanzeigen. Fixtures in fixtures/hilux/ are trimmed from
the real pages the GitHub runner fetched on 2026-09-24
(data/research/pages-hilux/). Where the real page held no 3rd-gen Hilux,
one clearly-labelled synthetic golden card was added (see each fixture's
header comment); BaT, ClassicCars, Barn Finds and Trovit US needed none.

KNOWN_MISFIRES are real titles common.hilux.classify() keeps but should
not (reported to the lead with a proposed rule). They are left out of the
id comparisons so these tests hold whichever way that fix lands."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx
from common.schema import validate
from listings_hilux import (barnfinds, bat, classiccars, kijiji, kleinanzeigen, pistonheads,
                            retrorides, trovit)

FIXTURES = Path(__file__).parent / "fixtures"
HILUX = FIXTURES / "hilux"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))

KNOWN_MISFIRES = {
    # "1978 Toyota Hilux/Pickup (N20 1972-1978)": the seller names the 2nd gen.
    "trovit:1e12y8KpK1k",
    # "52k-Mile Survivor: 1990 Toyota Pickup 4x4": year 1980 read from "1980s"
    # in the description although the title says 1990.
    "barnfinds:52k-mile-survivor-1990-toyota-pickup-4x4",
}


def _ids(records):
    return [r["id"] for r in records if r["id"] not in KNOWN_MISFIRES]


def _full(rec, day="2026-09-24"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}]}


def _raises(fn, *args):
    try:
        fn(*args)
    except ValueError:
        return True
    return False


def test_bat_parser():
    page = (HILUX / "bat_toyota_pickup.html").read_text()
    records = bat.parse_page(page, FX_DAY)
    # Real catches, one each way: the LIVE 1981 (server-rendered card, no
    # JSON blob for live auctions on this page) and a COMPLETED 1982.
    # Rejected on the same page: 1984 Pickup SR5 (4th gen in the US), 1990
    # Hilux, 1992 Hilux SSR Diesel (live), 1988/1993 Pickups, T100s, Tacomas.
    assert _ids(records) == ["bringatrailer:1981-toyota-pickup-38",
                             "bringatrailer:1982-toyota-pickup-58"], _ids(records)
    live, sold = records
    assert live["status"] == "active" and live["price"]["amount"] == 33250
    assert live["title"] == "1981 Toyota Pickup SR-5 4×4 5-Speed"
    assert live["variant"]["drive"] == "4WD" and live["country"] == "US"
    assert live["images"][0].startswith("https://bringatrailer.com/wp-content/uploads/")
    # "4&#215;4" in the blob is unescaped before classify() sees it.
    assert sold["status"] == "sold" and sold["title"] == "1982 Toyota Pickup Deluxe 4×4 5-Speed"
    assert sold["variant"]["drive"] == "4WD" and sold["year"] == 1982
    for rec in records:
        validate(_full(rec), "listing")
    # Guards: no blob at all, and live cards promised but unparseable.
    assert _raises(bat.parse_page, "<html>Toyota Pickup</html>", FX_DAY)
    broken = page.replace('data-listing_id="', 'data-moved="')
    assert _raises(bat.parse_page, broken, FX_DAY)
    print("ok test_bat_parser")


def test_classiccars_parser():
    records = classiccars.parse_page((HILUX / "classiccars_pickup.html").read_text(), FX_DAY)
    # Three real 3rd-gen trucks on the year-scoped US-name search; the
    # 1984 (CC-2084123) is 4th gen in the US and rejected.
    assert _ids(records) == ["classiccars:CC-2104765", "classiccars:CC-2104586",
                             "classiccars:CC-1767320"], _ids(records)
    r = records[0]
    assert r["year"] == 1980 and r["region"] == "Kentwood Michigan"
    assert r["price"]["amount"] == 32900 and r["price"]["currency"] == "USD"
    assert r["url"].startswith("https://classiccars.com/listings/view/2104765/")
    for rec in records:
        validate(_full(rec), "listing")
    # The Hilux search held 1986, 1989 and 1997 trucks: all rejected.
    assert classiccars.parse_page((HILUX / "classiccars_hilux.html").read_text(), FX_DAY) == []
    assert _raises(classiccars.parse_page, "<html><title>Access denied</title></html>", FX_DAY)
    print("ok test_classiccars_parser")


def test_kijiji_parser():
    page = (HILUX / "kijiji_hilux.html").read_text()
    records = kijiji.parse_page(page, FX_DAY)
    # Only the synthetic 1981 (an AutosListing). Real rejections: ten trucks
    # (2005 and 1989 diesels, 2004, Hilux Surfs, a Prado), and toys/parts
    # that classify() alone would keep ("1980 Toyota Hilux 'Minitrek' ...
    # Hot Wheels", "Matching pair 1977-1983 Toyota Pickup Tail Light
    # Lenses"), which the /v-cars-trucks/ path gate drops.
    assert _ids(records) == ["kijiji:9990000001"], _ids(records)
    g = records[0]
    assert g["year"] == 1981 and g["variant"]["chassis_code"] == "RN34"
    assert g["price"]["amount"] == 29500.0 and g["price"]["currency"] == "CAD"  # cents
    assert g["country"] == "CA" and g["region"] == "Abbotsford"
    validate(_full(g), "listing")
    # A search that says it is empty is an empty market, not a failure...
    assert kijiji.parse_page((HILUX / "kijiji_pickup_empty.html").read_text(), FX_DAY) == []
    # ...but results promised with none readable is.
    gutted = page.replace('"AutosListing:', '"MovedListing:').replace('"StandardListing:', '"Moved2:')
    assert _raises(kijiji.parse_page, gutted, FX_DAY)
    print("ok test_kijiji_parser")


def test_barnfinds_parser():
    hilux_feed = barnfinds.parse_feed((HILUX / "barnfinds_hilux_feed.xml").read_text(), FX_DAY)
    pickup_feed = barnfinds.parse_feed((HILUX / "barnfinds_pickup_feed.xml").read_text(), FX_DAY)
    toyota_feed = barnfinds.parse_feed((HILUX / "barnfinds_toyota_feed.xml").read_text(), FX_DAY)
    # The real 1979 truck is tagged both toyota-hilux and toyota-pickup.
    # Rejected: 1973/1974 Hi-Lux (2nd gen), 1986 SR5, 1988 and 1990 Pickups,
    # and on the Toyota feed a 1982 Toyota Citation motorhome and a 1986
    # one-ton whose slug says 1978.
    assert _ids(hilux_feed) == ["barnfinds:toy-story-tribute-1979-toyota-pickup"], _ids(hilux_feed)
    assert _ids(pickup_feed) == ["barnfinds:toy-story-tribute-1979-toyota-pickup"], _ids(pickup_feed)
    assert _ids(toyota_feed) == [], _ids(toyota_feed)
    g = hilux_feed[0]
    assert g["title"] == "Toy Story Tribute: 1979 Toyota Pickup" and g["year"] == 1979
    assert g["images"] and g["images"][0].startswith("https://barnfinds.com/wp-content/uploads/")
    validate(_full(g), "listing")
    assert _raises(barnfinds.parse_feed, "<html>blocked</html>", FX_DAY)
    print("ok test_barnfinds_parser")


def test_pistonheads_parser():
    page = (HILUX / "pistonheads_hilux.html").read_text()
    records = pistonheads.parse_page(page, FX_DAY)
    # 16 real adverts, 2013-2023 diesels, all rejected; the synthetic 1980
    # RN30 is kept and matches the owner's reference truck.
    assert _ids(records) == ["pistonheads:99900001"], _ids(records)
    g = records[0]
    assert g["year"] == 1980 and g["variant"]["target_match"] is True
    assert g["price"]["amount"] == 12995 and g["price"]["currency"] == "GBP"
    assert g["country"] == "GB" and g["drive_side"] == "RHD"
    validate(_full(g), "listing")
    # The real page as fetched (no synthetic advert, no 1978-84 facet
    # entry): nothing to keep and nothing hidden.
    data = json.loads(pistonheads._NEXT_RE.search(page).group(1))
    apollo = data["props"]["pageProps"]["__APOLLO_STATE__"]
    del apollo["Advert:99900001"]
    facet_1980 = '{"__typename": "SearchFacetValue", "key": "1980", "value": 1}, '
    real = page.replace(pistonheads._NEXT_RE.search(page).group(1),
                        json.dumps(data, ensure_ascii=False)).replace(facet_1980, "")
    assert facet_1980 not in real and pistonheads.parse_page(real, FX_DAY) == []
    # Facet guard: the facet counts a 1980 Hilux that page 1 does not hold.
    hidden = page.replace(pistonheads._NEXT_RE.search(page).group(1),
                          json.dumps(data, ensure_ascii=False))
    assert _raises(pistonheads.parse_page, hidden, FX_DAY)
    print("ok test_pistonheads_parser")


def test_retrorides_parser():
    records = retrorides.parse_page((HILUX / "retrorides_board57.html").read_text(), FX_DAY)
    # 35 real threads, none a Hilux (the 1978 Datsun 620 and a 1978 Toyota
    # Chaser among them); the synthetic 1980 RN30 is kept.
    assert _ids(records) == ["retrorides:999101"], _ids(records)
    g = records[0]
    assert g["price"]["amount"] == 6500 and g["price"]["currency"] == "GBP"
    assert g["year"] == 1980 and g["status"] == "active"
    assert g["variant"]["chassis_code"] == "RN30" and g["variant"]["target_match"] is True
    validate(_full(g), "listing")
    print("ok test_retrorides_parser")


def test_trovit_parser():
    us = trovit.parse_page((HILUX / "trovit_us_hilux.html").read_text(), FX_DAY, "US", "USD")
    # Six real 3rd-gen trucks (plus the N20 misfire). Rejected on the same
    # page: a 1970 Hilux, 1985-1992 trucks, a 1996 Surf, and the padding
    # (Rams, F-150s, Canyons).
    assert _ids(us) == ["trovit:12y1l1a1P1C1l1r", "trovit:1m1H-D0v1KQ", "trovit:KoQ1j1D1S1Zw",
                        "trovit:1VX1QK1Z1AB1V", "trovit:k1H1z1C19121hk",
                        "trovit:ntA91Hm71p"], _ids(us)
    by_id = {r["id"]: r for r in us}
    miami = by_id["trovit:12y1l1a1P1C1l1r"]
    assert miami["price"]["amount"] == 22141 and miami["region"].startswith("33149, Miami")
    both_names = by_id["trovit:ntA91Hm71p"]
    assert both_names["year"] == 1982 and both_names["variant"]["drive"] == "4WD"
    assert both_names["region"] is None  # empty address element
    for rec in us:
        validate(_full(rec), "listing")
    # UK: current-shape diesels only. DE: padding only.
    assert trovit.parse_page((HILUX / "trovit_uk_hilux.html").read_text(), FX_DAY, "GB", "GBP") == []
    assert trovit.parse_page((HILUX / "trovit_de_hilux.html").read_text(), FX_DAY, "DE", "EUR") == []
    assert _raises(trovit.parse_page, "<html>captcha</html>", FX_DAY)
    print("ok test_trovit_parser")


def test_kleinanzeigen_parser():
    page = (HILUX / "kleinanzeigen_hilux.html").read_text()
    records = kleinanzeigen.parse_page(page, FX_DAY)
    # 25 real ads (EZ 1989-2023, an LN65 diesel, 4Runner parts listing
    # RN/LN codes, five Suche want-ads); the synthetic EZ 05/1980 RN30 is kept.
    assert _ids(records) == ["kleinanzeigen:9990000042"], _ids(records)
    g = records[0]
    assert g["year"] == 1980 and g["title"] == "Toyota Hilux RN30 Pritsche Benziner"
    assert g["variant"]["target_match"] is True
    assert g["price"]["currency"] == "EUR" and g["country"] == "DE"
    assert g["url"].startswith("https://www.kleinanzeigen.de/s-anzeige/")
    validate(_full(g), "listing")
    # A want-ad is skipped even when its EZ is in the window.
    wanted = page.replace("Toyota Hilux RN30 Pritsche Benziner",
                          "Suche Toyota Hilux RN30 Pritsche Benziner")
    assert kleinanzeigen.parse_page(wanted, FX_DAY) == []
    # Heading promises 140 results; no card parsed must raise.
    assert _raises(kleinanzeigen.parse_page, page.replace("data-adid", "data-moved"), FX_DAY)
    print("ok test_kleinanzeigen_parser")


if __name__ == "__main__":
    test_bat_parser()
    test_classiccars_parser()
    test_kijiji_parser()
    test_barnfinds_parser()
    test_pistonheads_parser()
    test_retrorides_parser()
    test_trovit_parser()
    test_kleinanzeigen_parser()
