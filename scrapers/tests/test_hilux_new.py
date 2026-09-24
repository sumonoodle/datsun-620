"""New-source Hilux collectors: Gumtree UK, Gumtree ZA, Classic Trader, TCV,
CAR FROM JAPAN, Goo-net (domestic), Marktplaats and Hagerty. Parse
contracts against fixtures trimmed from the real 2026-09-24 runner fetches
(data/research/pages-hilux/, rounds 1 and 3). Marktplaats holds a REAL
1981 petrol Hilux; elsewhere no real page held a 1978-83 truck, so those
fixtures carry ONE clearly-labelled synthetic golden card cloned from a
real card's markup, and every real card must be rejected."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx
from common.schema import validate
from listings_hilux import (carfromjapan, classic_trader, goonet, gumtree_uk, gumtree_za, hagerty,
                            marktplaats, tcv)

FIXTURES = Path(__file__).parent / "fixtures"
HILUX = FIXTURES / "hilux"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _full(rec, day="2026-09-24"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}]}


def _raises(fn, *args):
    try:
        fn(*args)
    except ValueError:
        return True
    return False


def test_gumtree_uk_parser():
    html = (HILUX / "gumtree_uk_page.html").read_text()
    records = gumtree_uk.parse_page(html, FX_DAY)
    ids = [r["id"] for r in records]
    # 26 real cards all out: 2002-2025 diesels, the 2006 petrol V6 Raider
    # (1803099683, structured year 2006), the Ford Ranger and Mitsubishi L200
    # whose titles mention the Hilux (other make).
    assert ids == ["gumtree_uk:1809999001"], ids
    g = records[0]
    assert g["year"] == 1981 and g["country"] == "GB" and g["drive_side"] == "RHD"
    assert g["price"]["amount"] == 7950.0 and g["price"]["currency"] == "GBP"
    assert g["variant"]["chassis_code"] == "RN30" and g["variant"]["target_match"] is True
    assert g["url"].startswith("https://www.gumtree.com/p/vans/")
    assert g["region"] == "Salisbury, Wiltshire"
    validate(_full(g), "listing")
    print("ok test_gumtree_uk_parser")


def test_gumtree_uk_guard():
    # Layout change / block page: no clientData at all.
    assert _raises(gumtree_uk.parse_page, "<html><title>Gumtree</title></html>", FX_DAY)
    import urllib.parse

    def page(ads, total):
        blob = {"resultsPage": {"searchAds": ads,
                                "adsTitle": {"totalNumberOfAdsFound": str(total)}}}
        return f'<script>window.clientData = "{urllib.parse.quote(json.dumps(blob))}";</script>'
    # Results promised, none parsed: raise, never "no trucks".
    assert _raises(gumtree_uk.parse_page, page([], 12), FX_DAY)
    # Zero results is an empty market.
    assert gumtree_uk.parse_page(page([], 0), FX_DAY) == []
    # robots.txt disallows /search (round-3 probe refused both /search
    # URLs): only the path-style /srpsearch+ form may be polled.
    assert gumtree_uk.URLS[0] == "https://www.gumtree.com/cars-vans-motorbikes/uk/srpsearch+toyota+hilux"
    assert all("/search?" not in u and "/srpsearch+" in u for u in gumtree_uk.URLS)
    print("ok test_gumtree_uk_guard")


def test_gumtree_za_parser():
    html = (HILUX / "gumtree_za_page.html").read_text()
    # Round-3 petrol facet page: 73 results, 20 real petrol cards of 1999-2020.
    assert gumtree_za.result_count(html) == 73
    records = gumtree_za.parse_page(html, FX_DAY)
    ids = [r["id"] for r in records]
    assert ids == ["gumtree_za:10019999999991019999999909"], ids
    g = records[0]
    assert g["year"] == 1981 and g["country"] == "ZA" and g["drive_side"] == "RHD"
    assert g["price"]["amount"] == 45000.0 and g["price"]["currency"] == "ZAR"
    assert g["variant"]["chassis_code"] == "RN30"
    # CarBodyType "Single Cab" is an explicit non-extended cab.
    assert g["king_cab"]["matched"] is False and g["king_cab"]["body_style_check"] == "fail"
    assert g["url"].startswith("https://www.gumtree.co.za/a-cars-bakkies/")
    validate(_full(g), "listing")
    print("ok test_gumtree_za_parser")


def test_gumtree_za_guard_and_urls():
    html = (HILUX / "gumtree_za_page.html").read_text()
    # Cards gone but "(264 results)" still promised: raise.
    stripped = re.sub(r'<span class="related-item\b[^>]*>', "<span>", html)
    assert _raises(gumtree_za.parse_page, stripped, FX_DAY)
    # No results block at all and no count: raise (block page).
    assert _raises(gumtree_za.parse_page, "<html>blocked</html>", FX_DAY)
    assert gumtree_za.page_url(1).endswith("/toyota~hilux~petrol/v1c9077a3mamofup1")
    assert gumtree_za.page_url(3).endswith("/toyota~hilux~petrol/page-3/v1c9077a3mamofup3")
    print("ok test_gumtree_za_guard_and_urls")


def test_classic_trader_parser():
    # The real page: "Toyota Hilux (0 offers)" and 14 expired/sold reference
    # islands (incl. a 1983 SR5 4WD and a 1977 RN28). None is for sale, so
    # nothing is a record.
    real = (HILUX / "classic_trader_page.html").read_text()
    assert classic_trader.parse_page(real, FX_DAY) == []
    golden_page = (HILUX / "classic_trader_golden.html").read_text()
    records = classic_trader.parse_page(golden_page, FX_DAY)
    ids = [r["id"] for r in records]
    assert ids == ["classic_trader:999000001"], ids
    g = records[0]
    assert g["title"] == "Toyota Hilux RN30 1.6 petrol pick-up, UK registered"
    assert g["year"] == 1981 and g["country"] == "GB"
    assert g["price"]["amount"] == 8950.0 and g["price"]["currency"] == "GBP"
    assert g["url"] == "https://www.classic-trader.com/uk/cars/listing/toyota/hilux/hilux/1981/999000001"
    # Round-3 Toyota make page: 41 offers, 15 live ads in state "published"
    # (each also in a BookmarkAd island), none a Hilux: the model-slug gate
    # keeps the 1978/1981 Land Cruisers out and nothing raises.
    toyota = (HILUX / "classic_trader_toyota.html").read_text()
    live = {str(p["vehicleAd"]["id"]) for p in classic_trader._islands(toyota)
            if p.get("vehicleAd") and p["vehicleAd"].get("state") == "published"}
    assert len(live) == 15, len(live)
    assert classic_trader.parse_page(toyota, FX_DAY) == []
    assert g["images"][0].startswith("https://cdn.classic-trader.com/")
    validate(_full(g), "listing")
    print("ok test_classic_trader_parser")


def test_classic_trader_guard():
    golden_page = (HILUX / "classic_trader_golden.html").read_text()
    # Count says 1 offer but the live island is gone: raise.
    no_live = golden_page.replace("&quot;published&quot;", "&quot;expired&quot;")
    assert _raises(classic_trader.parse_page, no_live, FX_DAY)
    # No search dialog (count unknown): raise.
    assert _raises(classic_trader.parse_page, "<astro-island props=\"{}\"></astro-island>", FX_DAY)
    assert classic_trader._astro({"a": [0, 1], "b": [1, [[0, "x"]]], "c": [0]}) == \
        {"a": 1, "b": ["x"], "c": None}
    print("ok test_classic_trader_guard")


def test_tcv_parser():
    html = (HILUX / "tcv_page.html").read_text()
    records = tcv.parse_page(html, FX_DAY)
    ids = [r["id"] for r in records]
    # 25 real cards out: GUN125/GUN226 2018-2026 diesels, a 2014 MR0 (Thai),
    # the 2001 RZN147 and the 1994 YN107 petrols (registration year).
    assert ids == ["tcv:99990001"], ids
    g = records[0]
    assert g["year"] == 1981 and g["country"] == "JP" and g["drive_side"] == "RHD"
    assert g["price"]["amount"] == 9800.0 and g["price"]["currency"] == "USD"
    assert g["variant"]["chassis_code"] == "RN30"
    assert g["url"] == "https://www.tc-v.com/used_car/toyota/hilux/99990001/"
    validate(_full(g), "listing")
    assert "fid=1978" in tcv.URL and "jid=1984" in tcv.URL
    print("ok test_tcv_parser")


def test_tcv_years_page():
    # Round 3: ?fid=1978&jid=1984 is applied server-side (title echo) and
    # TCV held no 1978-84 Hilux: an empty id list, an empty market.
    html = (HILUX / "tcv_years.html").read_text()
    assert tcv._FILTER_ECHO_RE.search(html)
    assert tcv.parse_page(html, FX_DAY) == []
    print("ok test_tcv_years_page")


def test_tcv_guard():
    assert _raises(tcv.parse_page, "<html>blocked</html>", FX_DAY)
    assert _raises(tcv.parse_page, '<article data-search-car-ids-value="[1, 2]"></article>', FX_DAY)
    assert tcv.parse_page('<article data-search-car-ids-value="[]"></article>', FX_DAY) == []
    print("ok test_tcv_guard")


def test_carfromjapan_parser():
    html = (HILUX / "carfromjapan_page.html").read_text()
    records = carfromjapan.parse_page(html, FX_DAY)
    ids = [r["id"] for r in records]
    # The 25 real cars (1989-2026) are out on registrationYear.
    assert ids == ["carfromjapan:6ffff0000000000000000a81"], ids
    g = records[0]
    assert g["year"] == 1981 and g["drive_side"] == "RHD" and g["country"] == "JP"
    assert g["price"]["amount"] == 9800.0 and g["price"]["currency"] == "USD"
    assert g["variant"]["chassis_code"] == "RN30" and g["variant"]["target_match"] is True
    assert g["url"].startswith("https://carfromjapan.com/cheap-used-toyota-hilux-1981-for-sale-")
    validate(_full(g), "listing")
    assert carfromjapan.URL.endswith("?maxYear=1985")
    # Round 3: the real maxYear page echoes the filter and returns no cars.
    real = (HILUX / "carfromjapan_maxyear.html").read_text()
    assert carfromjapan.parse_page(real, FX_DAY) == []
    print("ok test_carfromjapan_parser")


def test_carfromjapan_guard():
    def page(flight):
        return f"<script>self.__next_f.push({json.dumps([1, flight])})</script>"
    assert _raises(carfromjapan.parse_page, page('{"nothing":1}'), FX_DAY)
    assert _raises(carfromjapan.parse_page, page('{"cars":[]}, "totalCount":538'), FX_DAY)
    assert carfromjapan.parse_page(page('{"cars":[]}, "totalCount":0'), FX_DAY) == []
    # Empty, no count, no year-filter echo: not trusted as an empty market.
    assert _raises(carfromjapan.parse_page, page('{"cars":[]}'), FX_DAY)
    print("ok test_carfromjapan_guard")


def test_goonet_parser():
    html = (HILUX / "goonet_page.html").read_text(encoding="utf-8")
    records = goonet.parse_page(html, FX_DAY)
    ids = [r["id"] for r in records]
    # Round-3 その他 facet: 7 real cards (2023-24 120-series, 2003, 2000,
    # 1996 and a 1970 1st-gen 初代) are all out on 年式.
    assert ids == ["goonet:999999999900000000001"], ids
    g = records[0]
    assert g["year"] == 1980 and g["country"] == "JP"
    # Cloned from the real 1970 card, whose price is "ASK": no amount.
    assert g["price"]["amount"] is None and g["price"]["currency"] == "JPY"
    # Full-width ＲＮ３０ / １２Ｒ in the title are read after NFKC folding.
    assert g["variant"]["chassis_code"] == "RN30"
    assert "12R engine" in g["variant"]["target_reasons"]
    assert g["url"].startswith("https://www.goo-net.com/usedcar/spread/goo/")
    validate(_full(g), "listing")
    print("ok test_goonet_parser")


def test_goonet_guard():
    assert goonet.parse_page('<script>{"offerCount":"0"}</script>', FX_DAY) == []
    assert _raises(goonet.parse_page, '<script>{"offerCount":"38"}</script>', FX_DAY)
    assert _raises(goonet.parse_page, "<html>blocked</html>", FX_DAY)
    assert goonet._year("1980年") == 1980 and goonet._year("昭和55年") == 1980
    print("ok test_goonet_guard")


def test_marktplaats_real_catch():
    html = (HILUX / "marktplaats_page.html").read_text()
    records = marktplaats.parse_page(html, FX_DAY)
    ids = [r["id"] for r in records]
    # REAL: "Toyota 1981", a US-import petrol Hilux in Amsterdam; only the
    # description says Hilux, the structured year says 1981. The other 29
    # (2000-2026 trucks, a 1994, a 1992 VW Taro/RN106, a want-ad) are out.
    assert ids == ["marktplaats:m2438531579"], ids
    g = records[0]
    assert g["year"] == 1981 and g["country"] == "NL" and g["region"] == "Amsterdam"
    assert g["price"]["amount"] is None and g["price"]["currency"] == "EUR"  # bid-only ad
    assert g["url"] == "https://www.marktplaats.nl/v/auto-s/bestelauto-s/m2438531579-toyota-1981"
    validate(_full(g), "listing")
    assert marktplaats.total_count(html) == 72 and marktplaats.page_offset(html) == 0
    assert marktplaats.page_url(2) == "https://www.marktplaats.nl/l/auto-s/q/toyota+hilux/p/2/"
    print("ok test_marktplaats_real_catch")


def test_marktplaats_guard():
    def page(listings, total):
        blob = {"props": {"pageProps": {"searchRequestAndResponse": {
            "listings": listings, "totalResultCount": total}}}}
        return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(blob)}</script>'
    assert _raises(marktplaats.parse_page, "<html>blocked</html>", FX_DAY)
    assert _raises(marktplaats.parse_page, page([], 72), FX_DAY)
    assert marktplaats.parse_page(page([], 0), FX_DAY) == []
    print("ok test_marktplaats_guard")


def test_hagerty_parser():
    # Real round-3 make=Toyota page: the search runs server-side, 14 Toyotas
    # (Land Cruisers, 4Runner, Crowns, Supra, 1998 Hilux, 1997 Hilux Surf),
    # none of the generation.
    assert hagerty.parse_page((HILUX / "hagerty_page.html").read_text(), FX_DAY) == []
    records = hagerty.parse_page((HILUX / "hagerty_golden.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    assert ids == ["hagerty:99999999-0000-4000-8000-000000001981"], ids
    g = records[0]
    # model "Pickup" + make Toyota is the US name for the Hilux.
    assert g["title"] == "1981 Toyota Pickup" and g["year"] == 1981
    assert g["price"]["amount"] == 14500.0 and g["price"]["currency"] == "USD"  # cents
    assert g["region"] == "Sacramento, CA" and g["drive_side"] == "LHD"
    assert g["url"] == ("https://www.hagerty.com/marketplace/classified/1981-Toyota-Pickup/"
                        "99999999-0000-4000-8000-000000001981")
    validate(_full(g), "listing")
    assert _raises(hagerty.parse_page, "<html>blocked</html>", FX_DAY)
    print("ok test_hagerty_parser")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
