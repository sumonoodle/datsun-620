// Shared model config and formatting for every tracked truck.
//
// The site covers more than one truck. Each model's pages are the same
// components parameterised by one of these configs: the Datsun 620 lives at
// the site root (its URLs predate the Hilux and must never move), the Hilux
// under /hilux/. Data paths are relative to site/, the build's cwd.
import { readFileSync } from "node:fs";

export type ModelKey = "datsun" | "hilux";

export interface TruckModel {
  key: ModelKey;
  /** Switcher label. */
  short: string;
  /** Header brand, split so the second word takes the accent colour. */
  brandMake: string;
  brandModel: string;
  /** <title> suffix, e.g. "Updates — Datsun 620 Tracker". */
  siteTitle: string;
  /** Directory of listings.json / changes-latest.json / run-log.json / specs.json. */
  dataDir: string;
  /** URL prefix under the site base: "" for the Datsun, "/hilux" for the Hilux. */
  prefix: string;
  /** What the listing's `king_cab` block means for this model. */
  extLabel: string;
  extChip: string;
  /** Extended cabs are not known for this generation: a match is news. */
  extRare: boolean;
  listingYears: number[];
  specYears: number[];
  listingsIntro: string;
  emptyListings: string;
  specsIntro: string;
  emptySpecs: string;
  /** Hilux only: label for listings resembling the owner's reference truck. */
  targetLabel?: string;
}

const range = (a: number, b: number) => Array.from({ length: b - a + 1 }, (_, i) => a + i);

export const MODELS: Record<ModelKey, TruckModel> = {
  datsun: {
    key: "datsun",
    short: "Datsun 620",
    brandMake: "Datsun",
    brandModel: "620",
    siteTitle: "Datsun 620 Tracker",
    dataDir: "../data",
    prefix: "",
    extLabel: "King Cab",
    extChip: "KING CAB",
    extRare: false,
    listingYears: range(1971, 1979),
    specYears: range(1971, 1980),
    listingsIntro: "Datsun 620 listings worldwide, King Cabs highlighted, refreshed daily.",
    emptyListings: "No listings collected yet. The daily sweep populates this page.",
    specsIntro: "Every Datsun 620 variant by market, curated once with citations.",
    emptySpecs: "The specs database has not been generated yet.",
  },
  hilux: {
    key: "hilux",
    short: "Hilux",
    brandMake: "Toyota",
    brandModel: "Hilux",
    siteTitle: "Hilux Tracker",
    // HILUX_DATA_DIR lets a local build point at sample data without
    // touching data/hilux/, which the pipeline owns.
    dataDir: process.env.HILUX_DATA_DIR || "../data/hilux",
    prefix: "/hilux",
    extLabel: "Extended cab",
    extChip: "EXTENDED CAB",
    extRare: true,
    listingYears: range(1978, 1984),
    specYears: range(1978, 1984),
    listingsIntro:
      "Petrol Toyota Hilux, 3rd generation (1978–1983, RN3x/RN4x, 2WD and 4WD) listings worldwide. Trucks like your 1980 RN30 come first. Refreshed daily.",
    emptyListings:
      "No Hilux listings collected yet. The daily sweep will fill this page once the Hilux search starts running.",
    specsIntro: "Every 3rd-generation petrol Hilux variant by market, curated with citations.",
    emptySpecs: "The Hilux specs database has not been generated yet.",
    targetLabel: "Matches your RN30 spec",
  },
};

export const MODEL_LIST: TruckModel[] = [MODELS.datsun, MODELS.hilux];

/** Site base without a trailing slash, so joins are always "<base>/x/". */
export const base = import.meta.env.BASE_URL.replace(/\/$/, "");

/** Which model a request path belongs to. */
export function modelFromPath(path: string): TruckModel {
  const h = `${base}/hilux`;
  return path === h || path.startsWith(`${h}/`) ? MODELS.hilux : MODELS.datsun;
}

/** Link to a page of a model: modelHref(m) is its listings, modelHref(m, "specs") etc. */
export function modelHref(m: TruckModel, page = ""): string {
  return `${base}${m.prefix}/${page ? `${page}/` : ""}`;
}

export function slugOf(id: string): string {
  return id.replaceAll(":", "--");
}

export function vehicleHref(m: TruckModel, id: string): string {
  return `${base}${m.prefix}/vehicle/${slugOf(id)}/`;
}

/** Parsed JSON from the model's data dir, or null when missing/unreadable.
 *  Every Hilux file may be absent until its pipeline first runs. */
export function readModelJson(m: TruckModel, file: string): any | null {
  return readJsonPath(`${m.dataDir}/${file}`);
}

export function readJsonPath(path: string): any | null {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

export function loadListings(m: TruckModel): { listings: any[]; generated: string } {
  const data = readModelJson(m, "listings.json");
  return { listings: data?.listings ?? [], generated: data?.generated_at ?? "" };
}

// Display names for sources. New sources need no entry: an unknown id is
// shown as-is rather than breaking a page.
export const SOURCE_NAMES: Record<string, string> = {
  ebay: "eBay",
  bringatrailer: "Bring a Trailer",
  carsandbids: "Cars & Bids",
  hemmings: "Hemmings",
  goonet_exchange: "Goo-net Exchange",
  carsensor: "Carsensor",
  yahoo_auctions: "Yahoo Auctions JP",
  kaidee: "Kaidee",
  truck2hand: "Truck2Hand",
  everycar: "EVERY (JP)",
  classiccars: "ClassicCars.com",
  kijiji: "Kijiji",
  barnfinds: "Barn Finds",
  flex: "FLEX (JP)",
  kuruma_ex: "Kuruma-EX",
  pistonheads: "PistonHeads",
  ratsun: "Ratsun",
  retrorides: "Retro Rides",
  trovit: "Trovit",
  kleinanzeigen: "Kleinanzeigen",
  // Hilux sources
  gumtree_uk: "Gumtree UK",
  classic_trader: "Classic Trader",
  gumtree_za: "Gumtree ZA",
  marktplaats: "Marktplaats",
  goonet: "Goo-net",
  carfromjapan: "CarFromJapan",
  tcv: "TCV",
  hagerty: "Hagerty",
  mecum: "Mecum",
  craigslist: "Craigslist",
  ih8mud: "IH8MUD",
};

export function sourceName(id: string | null | undefined): string {
  if (!id) return "unknown source";
  return SOURCE_NAMES[id] ?? id;
}

export const COUNTRY_NAMES: Record<string, string> = {
  US: "USA", GB: "UK", DE: "Germany", AU: "Australia", JP: "Japan",
  TH: "Thailand", ZA: "South Africa", CA: "Canada", MX: "Mexico",
  NZ: "New Zealand", NL: "Netherlands", XX: "location unknown",
};

export function countryName(c: string): string {
  return COUNTRY_NAMES[c] ?? c;
}

const SYM: Record<string, string> = {
  USD: "$", GBP: "£", EUR: "€", JPY: "¥", AUD: "A$", ZAR: "R", THB: "฿", CAD: "C$", MXN: "MX$",
};

export function money(p: any): string {
  if (!p || p.amount == null) return "no price shown";
  const orig = `${SYM[p.currency] ?? p.currency + " "}${p.amount.toLocaleString("en-GB")}`;
  if (p.currency === "GBP" || p.gbp == null) return orig;
  return `${orig} · £${Math.round(p.gbp).toLocaleString("en-GB")}`;
}

export function gbp(n: number | null | undefined): string {
  return n == null ? "?" : `£${Math.round(n).toLocaleString("en-GB")}`;
}

/** Hilux variant helpers; all tolerate a missing `variant` block. */
export function isTarget(l: any): boolean {
  return Boolean(l?.variant?.target_match);
}
export function driveTrain(l: any): string | null {
  const d = l?.variant?.drive;
  return d === "2WD" || d === "4WD" ? d : null;
}
export function chassisCode(l: any): string | null {
  return l?.variant?.chassis_code ?? null;
}
export function isExtCab(l: any): boolean {
  return Boolean(l?.king_cab?.matched);
}

/** getStaticPaths for a model's vehicle pages; no data means no pages. */
export function vehiclePaths(m: TruckModel) {
  const { listings } = loadListings(m);
  const paths = listings.map((l) => ({
    // ':' is awkward in URLs. Aggregator ids are arbitrary tokens, so two
    // ids COULD collapse to one slug (e.g. "a--b" vs "a:b") — that must
    // fail the build loudly, not silently render one truck over another.
    params: { slug: slugOf(l.id) },
    props: { listing: l, all: listings },
  }));
  const seen = new Map<string, string>();
  for (let i = 0; i < paths.length; i++) {
    const slug = paths[i].params.slug;
    const id = listings[i].id;
    if (seen.has(slug)) throw new Error(`vehicle slug collision: ${seen.get(slug)} vs ${id}`);
    seen.set(slug, id);
  }
  return paths;
}
