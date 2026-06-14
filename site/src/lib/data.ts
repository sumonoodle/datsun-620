// Build-time data loading. The JSON data files live at the repo root (../data),
// outside the Astro project, so we read them with Node fs during the static build.
// `astro build` runs with the site/ directory as the working directory, so the
// data lives at ../data relative to cwd.
import fs from "node:fs";
import path from "node:path";

function readJson<T>(filename: string): T {
  const full = path.resolve(process.cwd(), "..", "data", filename);
  return JSON.parse(fs.readFileSync(full, "utf-8")) as T;
}

export interface Listing {
  id: string;
  source: string;
  source_url: string;
  title: string;
  price_original: number | null;
  currency: string | null;
  price_gbp: number | null;
  country: string | null;
  region: string | null;
  drive_side: "LHD" | "RHD" | "unknown";
  year: number | null;
  king_cab_score: number;
  king_cab_signals?: string[];
  status: string;
}

export interface SpecVariant {
  id: string;
  market: string;
  years: string;
  body_style: string;
  bed_length: string | null;
  engine?: { value: { code?: string; displacement_cc?: number | null } };
}

export const getListings = () => readJson<Listing[]>("listings.json");
export const getSpecs = () => readJson<SpecVariant[]>("specs.json");
