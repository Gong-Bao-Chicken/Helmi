/** Shape of web/public/data/helmets.json, as produced by the helmet-data pipeline. */

export type RatingSourceKey = "virginia_tech" | "folksam" | "certimoov" | "nsw_helmet_star" | "hiper";
export type MarketKey = "de" | "at" | "ch";
export type ProtectionGroup = "spherical" | "rotational" | "crumple" | "none";
export type AeroTier = "elite" | "strong" | "moderate" | "neutral" | "draggy";

export interface RatingSourceMeta {
  key: RatingSourceKey;
  label: string;
  short: string;
  confidence: number;
  lower_score_is_better: boolean;
}

export interface RatingBlock {
  rank_pct?: number | null;
  score?: number | null;
  stars?: number | null;
  test_year?: string | number | null;
  url?: string | null;
  // Virginia Tech
  /** VT's chart of this helmet's impact results (VT has no page per helmet). */
  result_url?: string | null;
  score_norm?: number | null;
  score_low_impact?: number | null;
  score_high_impact?: number | null;
  // Folksam
  recommended?: boolean | null;
  overall_result_pct?: number | null;
  // CERTIMOOV
  impact_scores?: Record<string, number>;
  // NSW
  category?: string | null;
}

export interface FusedRating {
  rank_pct: number | null;
  sources: RatingSourceKey[];
  weights: Partial<Record<RatingSourceKey, number>>;
}

export interface ShopSource {
  source: string;
  title?: string | null;
  price: number | null;
  currency: string;
  url?: string | null;
  available?: boolean;
}

export interface Listing {
  price: number | null;
  currency: string;
  rating: number | null;
  review_count: number | null;
  url: string | null;
  source: string | null;
  sources?: ShopSource[];
  price_window?: string | null;
  price_sample_days?: number | null;
  fetched_at?: string | null;
}

export interface AeroSourceResult {
  source: string;
  source_url?: string;
  test_year?: string;
  speed_kph?: number;
  rank_pct?: number;
  score?: number;
  baseline_helmet?: string;
  watts_saved?: number;
  drag_watts_40kph?: number;
  match?: { confidence: number; method: string; test_name: string };
}

export interface Aero {
  sources: Record<string, AeroSourceResult>;
  rank_pct: number | null;
  score: number | null;
  tier: AeroTier | null;
  watts_saved?: number | null;
  drag_watts?: number | null;
  source?: string;
  source_keys?: string[];
}

export interface Features {
  mips_standard: boolean;
  mips_spherical: boolean;
  wavecel: boolean;
  spin: boolean;
  sweet_2vi: boolean;
  koroyd: boolean;
  rotational_protection: boolean;
  nta8776: boolean;
  asia_fit: boolean;
  round_fit: boolean;
}

export interface Helmet {
  id: string;
  brand: string;
  brand_key?: string;
  model: string;
  search_text: string;
  score: number | null;
  ratings: Partial<Record<RatingSourceKey, RatingBlock>> & { fused?: FusedRating };
  style: string;
  test_year: string | number | null;
  certifications: string;
  price_at_test_usd: number | null;
  image_url?: string | null;
  features: Features;
  feature_labels: string[];
  european_market: boolean;
  listings: Partial<Record<MarketKey, Listing>>;
  manufacturer?: { website?: string | null; search_url?: string | null };
  source?: { name: string; url: string };
  protection?: { mips_label?: string | null; rotational_label?: string | null };
  protection_tech?: string;
  protection_group?: ProtectionGroup;
  current_price?: { amount: number; currency: string; usd_equiv: number; sources: string[] } | null;
  price_comparison_usd?: number | null;
  aero?: Aero;
  catalog?: "extra_only";
  primary_rating_source?: RatingSourceKey;
}

export interface Dataset {
  meta: {
    generated_at: string;
    helmet_count_total: number;
    market_prices_fetched_at?: string;
    /** Units per USD, refreshed on every price update. */
    exchange_rates?: { base: "USD"; EUR: number; CHF: number; date?: string | null; source?: string };
    [key: string]: unknown;
  };
  filters: {
    rating_sources: RatingSourceMeta[];
    styles: string[];
    protection_groups: { key: ProtectionGroup; label: string; hint: string }[];
    protection_technologies: { key: string; label: string; group: ProtectionGroup; hint: string }[];
    markets: { key: MarketKey; label: string; currency: string }[];
    aero_tiers: { key: AeroTier; label: string }[];
    aero_sources: { key: string; label: string; short: string }[];
  };
  helmets: Helmet[];
}
