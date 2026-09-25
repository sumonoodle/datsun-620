"""Hilux collector tests, Japan and Thailand: Goo-net Exchange, Carsensor,
Yahoo Auctions, Truck2Hand, FLEX, kuruma-ex and everycar.

Fixtures live in fixtures/hilux/ and are trimmed from the real pages the
two 2026-09-24 runner probe rounds fetched, using the exact URLs the
collectors request (year caps, oldest-first sort, Yahoo's /carsearch).
None of those pages held a 3rd-gen Hilux, which is the expected state of
these markets: every real card is a later Hilux, a Surf, a Land Cruiser,
a 1971 1st-gen truck or a part. Each fixture that must show a catch ends
with ONE clearly labelled synthetic golden card copied from a real card
of the same page.

Kaidee has no collector: see the lead's report (the site is now a Vue
single-page app with no server-rendered listings).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from common import fx, hilux
from common.schema import validate
from listings_hilux import (carsensor, everycar, flex, goonet_exchange, kuruma_ex,
                            truck2hand, yahoo_auctions)

FIXTURES = Path(__file__).parent / "fixtures"
HILUX = FIXTURES / "hilux"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _full(rec, day="2026-09-24"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}]}


def _raises(fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError:
        return True
    return False


def test_goonet_exchange():
    html = (HILUX / "goonet_exchange_hilux.html").read_text()
    records = goonet_exchange.parse_page(html, FX_DAY)
    # 12 real HILUX_PICK_UP cards (1990-1997) and 4 real HILUX diesels out;
    # only the synthetic 1980 HILUX PICK UP comes through.
    assert [r["id"] for r in records] == ["goonet_exchange:999000000000000000001"], records
    g = records[0]
    assert g["year"] == 1980 and g["country"] == "JP" and g["drive_side"] == "RHD"
    assert g["url"].endswith("/usedcars/TOYOTA/HILUX_PICK_UP/999000000000000000001/")
    assert g["price"]["amount"] == 1480000 and g["price"]["currency"] == "JPY"
    assert g["variant"]["chassis_code"] is None
    assert g["variant"]["target_match"] is True  # 1600cc in the spec cells
    # The truck photo, not a "trusted dealer" badge.
    assert "picture1.goo-net.com" in g["images"][0], g["images"]
    validate(_full(g), "listing")
    assert _raises(goonet_exchange.parse_page, "<html><body>blocked</body></html>", FX_DAY)
    print("ok test_goonet_exchange")


def test_carsensor():
    html = (HILUX / "carsensor_hilux.html").read_text()
    # The real YMAX=1989 page: the cap held (no card above 1989, so the
    # guard stays quiet), and its 1971 Deluxe, 1987/1989 4th-gen trucks and
    # 1987-89 Surfs are all out. Only the synthetic 1981 Hilux 1.6 is in.
    records = carsensor.parse_page(html, FX_DAY)
    assert [r["id"] for r in records] == ["carsensor:AU0000000001"], records
    g = records[0]
    assert g["year"] == 1981 and g["title"] == "ハイラックス 1.6 スタンダード ロングボディ"
    assert g["price"]["amount"] == 2500000
    assert g["images"][0].startswith("https://ccsrpcma.carsensor.net/")
    validate(_full(g), "listing")
    assert "YMAX=1989" in carsensor.URL
    # A card above the cap means the parameter was ignored: that raises.
    assert _raises(carsensor.parse_page, html.replace(
        'specList__emphasisData">1989<', 'specList__emphasisData">2026<', 1), FX_DAY)
    assert carsensor.parse_page('<html><form id="panelForm"></form></html>', FX_DAY) == []
    assert _raises(carsensor.parse_page, "<html><body>maintenance</body></html>", FX_DAY)
    print("ok test_carsensor")


def test_yahoo_open():
    html = (HILUX / "yahoo_open_hilux.html").read_text()
    records, raw = yahoo_auctions.parse_open(html, FX_DAY)
    # 12 real ハイラックス RN30 cards (weatherstrips, tail lamps, a model kit,
    # a ¥160,000 US step bumper...) out by parts list, floor or classify().
    assert raw == 13
    assert [r["id"] for r in records] == ["yahoo_auctions:x9990000001"], records
    g = records[0]
    assert g["year"] == 1980  # from 昭和55年 in the title
    assert g["variant"] == {"chassis_code": "RN30", "drive": "2WD", "target_match": True,
                            "target_reasons": ["chassis code RN30"]}
    assert g["price"]["amount"] == 480000 and g["status"] == "active"
    validate(_full(g), "listing")
    urls = yahoo_auctions.search_urls()
    assert all("/search/search?p=" in u and "+" not in u for u, _ in urls), urls
    assert [s for _, s in urls] == [False, False, True, True]
    assert all(u.endswith("&auccat=26360") for u, s in urls if s)
    assert not any("closedsearch" in u for u, _ in urls)
    print("ok test_yahoo_open")


def test_yahoo_carsearch():
    # auccat=26360 now redirects to /carsearch (Next.js JSON, no li.Product).
    html = (HILUX / "yahoo_carsearch_hilux.html").read_text()
    records, raw = yahoo_auctions.parse_vehicle_page(html, FX_DAY)
    # Listing items only (featuredListing is promoted stock and not
    # counted): the real 1997 Delica, 2002 Xtracab and 1985 diesel Surf are
    # out on their structured modelDate; the synthetic 1980 RN30 is in.
    assert raw == 4
    assert [r["id"] for r in records] == ["yahoo_auctions:x9990000002"], records
    g = records[0]
    assert g["year"] == 1980 and g["price"]["amount"] == 880000
    validate(_full(g), "listing")
    # A structured modelDate outranks a title year.
    item = {"auctionId": "z1", "title": "昭和55年 ハイラックス RN30", "price": 1,
            "carSpec": {"modelDate": 19960101},
            "categoryPath": [{"name": "中古車・新車"}]}
    page = ('<script id="__NEXT_DATA__" type="application/json">'
            + json.dumps({"props": {"pageProps": {"initialState": {"search": {"items": {
                "listing": {"items": [item]}}}}}}}) + "</script>")
    assert yahoo_auctions.parse_car_search(page, FX_DAY) == ([], 1)
    assert _raises(yahoo_auctions.parse_car_search, "<html></html>", FX_DAY)
    print("ok test_yahoo_carsearch")


def test_yahoo_parts_and_diesel_titles():
    # Unscoped queries carry the Datsun collector's parts list and floor.
    card = ('<li class="Product"><a class="Product__titleLink" data-auction-id="{id}" '
            'data-auction-price="{p}" data-auction-title="{t}"></a></li>')
    html = "<ul>" + "".join(card.format(id=i, p=p, t=t) for i, p, t in [
        ("a1", "8000", "ハイラックス RN30 テールランプ 左右 当時物"),   # part (ランプ)
        ("a2", "450000", "ハイラックス LN30 ディーゼル 昭和56年 実働"),  # 3rd-gen diesel
        ("a3", "2000000", "ハイラックス 2.4 Z ディーゼルターボ 4WD"),    # modern
        ("a4", "30000", "昭和55年 ハイラックス RN30 実働"),             # under the floor
    ]) + "</ul>"
    records, raw = yahoo_auctions.parse_open(html, FX_DAY)
    assert raw == 4 and records == [], records
    print("ok test_yahoo_parts_and_diesel_titles")


def test_truck2hand():
    html = (HILUX / "truck2hand_search_hilux.html").read_text()
    records = truck2hand.parse_page(html, FX_DAY)
    # 101 real items (Revo, Vigo, Tiger, Mighty-X, Hero, LN106, ฿10 parts)
    # all out; the synthetic 1980 RN30 in.
    assert [r["id"] for r in records] == ["truck2hand:SYNTH00001"], records
    g = records[0]
    assert g["year"] == 1980 and g["country"] == "TH" and g["region"] == "นครปฐม"
    assert g["price"]["amount"] == 85000 and g["price"]["currency"] == "THB"
    assert g["variant"]["target_reasons"] == ["chassis code RN30", "12R engine"]
    validate(_full(g), "listing")
    assert truck2hand.total_pages(html) == 4
    assert _raises(truck2hand.parse_page, "<html></html>", FX_DAY)
    # The Thai-spelling search (real, 3 items: a Hero chassis part, a 2007
    # Vigo, a Revo) parses and yields nothing.
    th = (HILUX / "truck2hand_search_th.html").read_text()
    assert truck2hand.parse_page(th, FX_DAY) == [] and truck2hand.total_pages(th) == 1
    assert truck2hand.QUERIES == ["hilux", "ไฮลักซ์"]
    for title, short in [
        ("Toyota hilux hero 2.4 turbo", "TOYOTA Hilux Hero ปี 1990"),
        ("TOYOTA HILUX LN 106", "TOYOTA LN ปี 1997 ปทุมธานี"),
        ("1997 TOYOTA HILUX MIGHTY-X, 2.5 STATIONWAGON โฉม WAGON", "TOYOTA Hilux Mighty-X ปี 1997"),
        ("ขาย TOYOTA HILUX TIGER 2.5 D4D 4WD ปี 2004", "TOYOTA Hilux Tiger ปี 2004"),
        ("ขายรถกระบะ ไฮลักซ์วีโก้ 4WD สี่ประตู เกียร์ออโต้ ปี 2007", "TOYOTA Hilux Vigo ปี 2007"),
    ]:
        assert hilux.classify(title, short) is None, title
    print("ok test_truck2hand")


def test_truck2hand_pickup_category_page():
    html = (HILUX / "truck2hand_pickup.html").read_text()
    assert truck2hand.parse_page(html, FX_DAY) == []
    print("ok test_truck2hand_pickup_category_page")


def test_flex():
    html = (HILUX / "flex_hilux.html").read_text()
    # Real oldest-first page: 1994-1998 Prados, 80s, 100 and Surfs, all out.
    records = flex.parse_page(html, FX_DAY)
    assert [r["id"] for r in records] == ["flex:888000101"], records
    g = records[0]
    assert g["year"] == 1980 and g["variant"]["chassis_code"] == "RN30"
    # 支払総額, not the 諸費用 (fees) listed first on the card.
    assert g["price"]["amount"] == 1980000, g["price"]
    assert g["images"][0].startswith("https://img2.flexnet.co.jp/"), g["images"]
    assert g["url"].startswith("https://www.flexnet.co.jp/detail/")
    validate(_full(g), "listing")
    cards = BeautifulSoup(html, "html.parser").select("div.usdbox")
    years = [flex._YEAR_RE.search(c.select_one(".usd_detailbox").get_text()).group(1) for c in cards[:8]]
    assert years == sorted(years) and years[0] == "1994", years  # sort=4 honoured
    # Real card 1 (1994 Prado): total 399.8万円, not its fees.
    assert flex._price_yen(cards[0], "") == 3998000
    assert "sort=4" in flex.URL
    assert _raises(flex.parse_page, "<html></html>", FX_DAY)
    print("ok test_flex")


def test_kuruma_ex():
    html = (HILUX / "kuruma_ex_hilux.html").read_text()
    # Real capped page: one card, a 1971 ハイラックスデラックス (1st gen, out).
    records = kuruma_ex.parse_page(html, FX_DAY)
    assert [r["id"] for r in records] == ["kuruma_ex:ccZZ9990000001"], records
    g = records[0]
    assert g["year"] == 1980 and g["title"].startswith("トヨタ ハイラックス")
    assert g["price"]["amount"] == 2500000  # from the total-price-js value
    validate(_full(g), "listing")
    assert kuruma_ex.URL.endswith("/maker/TO/shashu/S112/year_max/1989")
    # Real uncapped page: 2023 cards above the cap mean an ignored filter.
    uncapped = (HILUX / "kuruma_ex_s112_uncapped.html").read_text()
    assert _raises(kuruma_ex.parse_page, uncapped, FX_DAY)
    assert kuruma_ex.parse_page(uncapped, FX_DAY, year_cap=None) == []
    # Search form but no cards: an empty market, not a failure.
    real = (HILUX / "kuruma_ex_toyota_maker.html").read_text()
    assert kuruma_ex.parse_page(real, FX_DAY) == []
    assert _raises(kuruma_ex.parse_page, "<html><body>503</body></html>", FX_DAY)
    print("ok test_kuruma_ex")


def test_everycar():
    html = (HILUX / "everycar_hilux.html").read_text()
    slugs = [s for s in everycar.model_slugs(html) if everycar._HILUX_SLUG_RE.search(s)]
    assert slugs == ["hilux"], slugs
    assert not everycar._HILUX_SLUG_RE.search("hilux-surf")
    records = everycar.parse_page(html, FX_DAY)
    # 15 real Hilux cards (1991-2023) out; the synthetic 1980 RN30 in.
    assert [r["id"] for r in records] == ["everycar:7999001"], records
    g = records[0]
    assert g["title"] == "TOYOTA HILUX LONG DECK"  # "Sale" badge stripped
    assert g["year"] == 1980 and g["variant"]["chassis_code"] == "RN30"
    assert g["price"]["amount"] == 7177 and g["price"]["currency"] == "USD"
    assert g["status"] == "active"
    validate(_full(g), "listing")
    cards = BeautifulSoup(html, "html.parser").select("li.listItem")
    # Real sold card (1991 LN107): SALES HISTORY in place of a price. Moved
    # into the window it is still out, on its LN code and diesel fuel.
    sold = [c for c in cards if "S-LN107" in str(c)][0]
    assert everycar._SOLD_MARK in sold.get_text()
    moved = str(sold).replace("/toyota/hilux/1991/", "/toyota/hilux/1980/")
    assert everycar.parse_page(moved, FX_DAY) == []
    for c in cards:
        if "/toyota/hilux/202" in str(c):
            spec = everycar._spec(c)
            desc = f"Model Code {spec['Model Code']} Fuel {spec['Fuel']}"
            if spec["Fuel"] == "Diesel":
                assert hilux.classify("TOYOTA HILUX", desc, require_name=False) is None
    print("ok test_everycar")


def test_modern_titles_rejected():
    # Real titles from the probe pages, with their real structured years.
    for title, year in [
        ("ハイラックス 2.4 Z ディーゼルターボ 4WD", 2019),              # carsensor
        ("ハイラックスサーフ 2.7 SSR-X アメリカンバージョン 4WD", 2004),  # carsensor
        ("ハイラックス デラックス", 1971),                               # carsensor/kuruma
        ("ハイラックス シングルキャブ4WD", 1987),                        # carsensor
        ("ハイラックス SR5 AT サンルーフ 新品タイヤ", 1989),             # carsensor
        ("トヨタ ハイラックスサーフ 2.7 SSR-X 4WD", 1996),               # flex
        ("TOYOTA HILUX PICK UP SINGLECAB SHORT BODY SSR", 1990),        # goonet exchange
        ("【諸費用コミ】返金保証付:【伊勢崎発】 昭和60年 ハイラックスサーフ 2.4 SSRリミテッド ディーゼル 4WD タイミングベ", 1985),
    ]:
        assert hilux.classify(title, None, year=year) is None, title
    print("ok test_modern_titles_rejected")


if __name__ == "__main__":
    test_goonet_exchange()
    test_carsensor()
    test_yahoo_open()
    test_yahoo_carsearch()
    test_yahoo_parts_and_diesel_titles()
    test_truck2hand()
    test_truck2hand_pickup_category_page()
    test_flex()
    test_kuruma_ex()
    test_everycar()
    test_modern_titles_rejected()
