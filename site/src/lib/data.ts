// Build-time data loading. JSON data files live at the repo root (../data),
// outside the Astro project, so we read them with Node fs during the static
// build. `astro build` runs with the site/ dir as cwd, so data is at ../data.
import fs from "node:fs";
import path from "node:path";

function readJson<T>(filename: string, fallback: T): T {
  const full = path.resolve(process.cwd(), "..", "data", filename);
  try {
    return JSON.parse(fs.readFileSync(full, "utf-8")) as T;
  } catch {
    return fallback;
  }
}

// ---- Listings (placeholder until M4) ----
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
  status: string;
}
export const getListings = () => readJson<Listing[]>("listings.json", []);

// ---- Specs ----
export interface Citation {
  value: unknown;
  source_url: string;
  source_name: string;
}
export interface SpecGroup {
  value: Record<string, unknown>;
  citations: Citation[];
}
export interface SpecVariant {
  id: string;
  market: string;
  years: string;
  body_style: string;
  bed_length: string | null;
  engine?: SpecGroup;
  dimensions?: SpecGroup;
  weights?: SpecGroup;
  [group: string]: unknown;
}
export interface Conflict {
  variant_id: string;
  field: string;
  candidates: { value: unknown; source: string }[];
  status: string;
}
export interface SourceStatus {
  source: string;
  ok: boolean;
  note: string;
  facts: number;
}
export interface SpecsReport {
  generated_at?: string;
  variant_count: number;
  markets: string[];
  conflict_count: number;
  sources: SourceStatus[];
}

export const getSpecs = () => readJson<SpecVariant[]>("specs.json", []);
export const getConflicts = () => readJson<Conflict[]>("specs-conflicts.json", []);
export const getSpecsReport = () =>
  readJson<SpecsReport>("specs-report.json", { variant_count: 0, markets: [], conflict_count: 0, sources: [] });

// Read a leaf like "dimensions.length_mm" from a variant. Returns undefined if absent (a gap).
export function leaf(v: SpecVariant, group: string, key: string): unknown {
  const g = v[group] as SpecGroup | undefined;
  return g?.value?.[key];
}

// Field display config used by the comparison table and detail pages.
export interface FieldDef {
  group: string;
  key: string;
  label: string;
  unit?: string;
  decimals?: number;
}
export const FIELDS: FieldDef[] = [
  { group: "engine", key: "code", label: "Engine" },
  { group: "engine", key: "displacement_cc", label: "Displacement", unit: "cc", decimals: 0 },
  { group: "engine", key: "power_hp", label: "Power", unit: "hp", decimals: 0 },
  { group: "engine", key: "torque_nm", label: "Torque", unit: "Nm", decimals: 0 },
  { group: "dimensions", key: "length_mm", label: "Length", unit: "mm", decimals: 0 },
  { group: "dimensions", key: "width_mm", label: "Width", unit: "mm", decimals: 0 },
  { group: "dimensions", key: "height_mm", label: "Height", unit: "mm", decimals: 0 },
  { group: "dimensions", key: "wheelbase_mm", label: "Wheelbase", unit: "mm", decimals: 0 },
  { group: "dimensions", key: "ground_clearance_mm", label: "Ground clearance", unit: "mm", decimals: 0 },
  { group: "weights", key: "kerb_kg", label: "Kerb weight", unit: "kg", decimals: 0 },
  { group: "weights", key: "payload_kg", label: "Payload", unit: "kg", decimals: 0 },
];

export function fmt(value: unknown, f: FieldDef): string {
  if (value === undefined || value === null) return "";
  if (typeof value === "number") {
    const n = f.decimals === 0 ? Math.round(value) : value;
    return f.unit ? `${n} ${f.unit}` : `${n}`;
  }
  return String(value);
}
