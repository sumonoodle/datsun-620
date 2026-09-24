"""Hilux collector tests, Japan and Thailand: Goo-net Exchange, Carsensor,
Yahoo Auctions, Truck2Hand, FLEX, kuruma-ex and everycar.

Fixtures live in fixtures/hilux/ and are trimmed from the real pages the
2026-09-24 runner probe fetched (data/research/pages-hilux/). None of
those pages held a 3rd-gen Hilux, which is the expected state of these
markets: every real card is a modern diesel, a Surf, a Land Cruiser or a
Datsun, and each fixture ends with ONE clearly labelled synthetic golden
card copied from a real card's markup. Yahoo and kuruma-ex reuse the real
result-card markup of the Datsun fixtures, because the Hilux probe got no
result page from either (HTTP 500 / maker landing page).

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
    # 20 real 2018-2026 Z / GR SPORT diesels out (structured year); only the
    # synthetic 1980 HILUX PICK UP comes through.
    assert [r["id"] for r in records] == ["goonet_exchange:999000000000000000001"], records
    g = records[0]
    assert g["year"] == 1980 and g["country"] == "JP" and g["drive_side"] == "RHD"
    assert g["url"].endswith("/usedcars/TOYOTA/HILUX_PICK_UP/999000000000000000001/")
    assert g["price"]["amount"] == 1480000 and g["price"]["currency"] == "JPY"
    assert g["variant"]["chassis_code"] is None
    # 1600cc in the spec cells is the reference truck's displacement.
    assert g["variant"]["target_match"] is True
    # The truck photo, not the "trusted dealer" badge that leads the div.
    assert "picture1.goo-net.com" in g["images"][0], g["images"]
    validate(_full(g), "listing")
    assert _raises(goonet_exchange.parse_page, "<html><body>blocked</body></html>", FX_DAY)
    print("ok test_goonet_exchange")


def test_carsensor():
    html = (HILUX / "carsensor_hilux.html").read_text()
    # The fixture is the UNCAPPED probe page, so with the default YMAX guard
    # its 2026 cards prove the guard fires when a cap is ignored.
    assert _raises(carsensor.parse_page, html, FX_DAY)
    records = carsensor.parse_page(html, FX_DAY, year_cap=None)
    # Real 2019-2026 diesels, 2004/2007 Hilux Surfs and a 2003 Sports
    # Pickup out; the synthetic 1981 (S56) Hilux 1.6 in.
    assert [r["id"] for r in records] == ["carsensor:AU0000000001"], records
    g = records[0]
    assert g["year"] == 1981 and g["title"] == "ハイラックス 1.6 スタンダード ロングボディ"
    assert g["price"]["amount"] == 1680000
    assert g["region"] == "群馬県 前橋市"
    assert g["variant"]["target_reasons"] == ["1.6 litre engine"]
    assert g["images"][0].startswith("https://ccsrpcma.carsensor.net/")
    validate(_full(g), "listing")
    assert "YMAX=1989" in carsensor.URL
    # An empty capped search is an ordinary day while the form is there...
    assert carsensor.parse_page('<html><form id="panelForm"></form></html>', FX_DAY) == []
    # ...and a failure when it is not.
    assert _raises(carsensor.parse_page, "<html><body>maintenance</body></html>", FX_DAY)
    print("ok test_carsensor")


def test_yahoo_auctions():
    html = (HILUX / "yahoo_open_hilux.html").read_text()
    for scoped in (False, True):
        records, raw = yahoo_auctions.parse_open(html, FX_DAY, vehicle_scoped=scoped)
        # Five real Datsun parts/toy cards out whatever the scope.
        assert raw == 6
        assert [r["id"] for r in records] == ["yahoo_auctions:x9990000001"], records
    g = records[0]
    assert g["year"] == 1980  # from 昭和55年 in the title
    assert g["variant"] == {"chassis_code": "RN30", "drive": "2WD", "target_match": True,
                            "target_reasons": ["chassis code RN30"]}
    assert g["price"]["amount"] == 480000 and g["status"] == "active"
    validate(_full(g), "listing")
    # Built like the Datsun collector: quote() (%20, not +), vehicle
    # category on the scoped queries, and never the robots-disallowed
    # closed search.
    urls = yahoo_auctions.search_urls()
    assert all("/search/search?p=" in u and "+" not in u for u, _ in urls), urls
    assert [s for _, s in urls] == [False, False, True, True]
    assert all(u.endswith("&auccat=26360") for u, s in urls if s)
    assert not any("closedsearch" in u for u, _ in urls)
    print("ok test_yahoo_auctions")


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
    # In the vehicle category the floor is off, so the ¥30,000 truck counts;
    # the diesel and the modern truck stay out there too. (The parts word
    # list is off as well: the category does that work, as for the 620.)
    records, _ = yahoo_auctions.parse_open(html, FX_DAY, vehicle_scoped=True)
    ids = [r["id"] for r in records]
    assert "yahoo_auctions:a4" in ids and not {"yahoo_auctions:a2", "yahoo_auctions:a3"} & set(ids), ids
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
    # Real probe titles with their shortDetails: the old ones must stay out.
    for title, short in [
        ("Toyota hilux hero 2.4 turbo", "TOYOTA Hilux Hero ปี 1990"),
        ("TOYOTA HILUX LN 106", "TOYOTA LN ปี 1997 ปทุมธานี"),
        ("1997 TOYOTA HILUX MIGHTY-X, 2.5 STATIONWAGON โฉม WAGON", "TOYOTA Hilux Mighty-X ปี 1997"),
        ("ขาย TOYOTA HILUX TIGER 2.5 D4D 4WD ปี 2004", "TOYOTA Hilux Tiger ปี 2004"),
    ]:
        assert hilux.classify(title, short) is None, title
    print("ok test_truck2hand")


def test_truck2hand_pickup_category_page():
    # The real 111-item pickup category page (probe) yields nothing either.
    html = (HILUX / "truck2hand_pickup.html").read_text()
    assert truck2hand.parse_page(html, FX_DAY) == []
    print("ok test_truck2hand_pickup_category_page")


def test_flex():
    html = (HILUX / "flex_hilux.html").read_text()
    records = flex.parse_page(html, FX_DAY)
    assert [r["id"] for r in records] == ["flex:888000101"], records
    g = records[0]
    assert g["year"] == 1980 and g["variant"]["chassis_code"] == "RN30"
    # 支払総額 198万円, not the 12.0万円 諸費用 (fees) listed first on the card.
    assert g["price"]["amount"] == 1980000, g["price"]
    assert g["images"][0].startswith("https://img2.flexnet.co.jp/"), g["images"]
    assert g["url"].startswith("https://www.flexnet.co.jp/detail/")
    validate(_full(g), "listing")
    # Same on a real card: the 2021 Hilux's total is 469.2万円, fees 19.4万円.
    cards = BeautifulSoup(html, "html.parser").select("div.usdbox")
    real = [c for c in cards if "623792978" in str(c)][0]
    assert flex._price_yen(real, "") == 4692000
    assert "sort=4" in flex.URL
    assert _raises(flex.parse_page, "<html></html>", FX_DAY)
    print("ok test_flex")


def test_kuruma_ex():
    html = (HILUX / "kuruma_ex_hilux.html").read_text()
    # Real 1987/1988 cards are above year_max=1984: the guard must call it.
    assert _raises(kuruma_ex.parse_page, html, FX_DAY)
    records = kuruma_ex.parse_page(html, FX_DAY, year_cap=None)
    assert [r["id"] for r in records] == ["kuruma_ex:ccZZ9990000001"], records
    g = records[0]
    assert g["year"] == 1980 and g["title"].startswith("トヨタ ハイラックス")
    assert g["price"]["amount"] == 1580000  # from the total-price-js value
    validate(_full(g), "listing")
    assert kuruma_ex.URL.endswith("/maker/TO/shashu/S112?year_max=1984")
    # The real Toyota maker page: search form present, no result cards,
    # so it reads as an empty market rather than a failure.
    real = (HILUX / "kuruma_ex_toyota_maker.html").read_text()
    assert "/maker/TO/shashu/S112" in real
    assert kuruma_ex.parse_page(real, FX_DAY) == []
    assert _raises(kuruma_ex.parse_page, "<html><body>503</body></html>", FX_DAY)
    print("ok test_kuruma_ex")


def test_everycar():
    html = (HILUX / "everycar_hilux.html").read_text()
    slugs = [s for s in everycar.model_slugs(html) if everycar._HILUX_SLUG_RE.search(s)]
    assert slugs == ["hilux"], slugs
    assert not everycar._HILUX_SLUG_RE.search("hilux-surf")
    records = everycar.parse_page(html, FX_DAY)
    # Real Hiace/Dyna are other models; real 2020/2022 GUN125 Hiluxes are out.
    assert [r["id"] for r in records] == ["everycar:7999001"], records
    g = records[0]
    assert g["year"] == 1980 and g["variant"]["chassis_code"] == "RN30"
    assert g["price"]["amount"] == 9800 and g["price"]["currency"] == "USD"
    assert "Model Code RN30" in g["description_snippet"]
    validate(_full(g), "listing")
    # Even without the path-year gate, the real diesels' spec rows reject.
    cards = BeautifulSoup(html, "html.parser").select("li.listItem")
    for c in cards:
        if "/toyota/hilux/202" in str(c):
            spec = everycar._spec(c)
            assert spec["Fuel"] == "Diesel"
            desc = f"Model Code {spec['Model Code']} Fuel {spec['Fuel']}"
            assert hilux.classify("TOYOTA HILUX", desc, year=1980, require_name=False) is None
    print("ok test_everycar")


def test_modern_titles_rejected():
    # Real titles from the probe pages, with their real structured years.
    for title, year in [
        ("ハイラックス 2.4 Z ディーゼルターボ 4WD", 2019),              # carsensor
        ("ハイラックスサーフ 2.7 SSR-X アメリカンバージョン 4WD", 2004),  # carsensor
        ("ハイラックス スポーツピックアップ 2.7 ダブルキャブ ワイドボディ 4WD", 2003),
        ("トヨタ ハイラックスサーフ 2.7 SSR-X 4WD", 1996),               # flex
        ("TOYOTA HILUX Z GR SPORT", 2023),                              # goonet exchange
    ]:
        assert hilux.classify(title, None, year=year) is None, title
    print("ok test_modern_titles_rejected")


if __name__ == "__main__":
    test_goonet_exchange()
    test_carsensor()
    test_yahoo_auctions()
    test_yahoo_parts_and_diesel_titles()
    test_truck2hand()
    test_truck2hand_pickup_category_page()
    test_flex()
    test_kuruma_ex()
    test_everycar()
    test_modern_titles_rejected()
