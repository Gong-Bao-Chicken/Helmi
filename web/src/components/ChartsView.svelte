<script lang="ts">
  import { findHelmets, RIDES, safetyFor } from "../lib/finder";
  import { median } from "../lib/scoring";
  import { app } from "../lib/state.svelte";
  import type { Dataset, Helmet } from "../lib/types";
  import CategoryStrips from "./charts/CategoryStrips.svelte";
  import PositionChart from "./charts/PositionChart.svelte";

  let { dataset, fx }: { dataset: Dataset; fx: Record<string, number> } = $props();

  // The price chart follows the chosen riding style; the category charts compare across all styles.
  const ride = $derived(RIDES.find((r) => r.key === app.goals.ride));
  const result = $derived(findHelmets(dataset, { ...app.goals, ride: app.goals.ride ?? "any" }, fx));

  const rated = $derived(
    dataset.helmets
      .filter((h) => !app.goals.euOnly || app.goals.market === "us" || h.european_market)
      .map((h) => ({ helmet: h, value: (safetyFor(h, app.goals.safetySource) ?? NaN) * 100 }))
      .filter((i) => !Number.isNaN(i.value)),
  );

  function rowsBy(keyOf: (h: Helmet) => string | null | undefined, order: { key: string; label: string; hint?: string }[]) {
    return order
      .map((o) => ({ ...o, items: rated.filter((i) => keyOf(i.helmet) === o.key) }))
      .filter((r) => r.items.length > 0);
  }
  const byMedian = <T extends { items: { value: number }[] }>(rows: T[]) =>
    [...rows].sort((a, b) => (median(b.items.map((i) => i.value)) ?? 0) - (median(a.items.map((i) => i.value)) ?? 0));

  const styleRows = $derived(byMedian(rowsBy((h) => h.style, dataset.filters.styles.map((s) => ({ key: s, label: s })))));
  const protectionRows = $derived(
    rowsBy(
      (h) => h.protection_group ?? "none",
      dataset.filters.protection_groups.map((g) => ({ key: g.key, label: g.label, hint: g.hint })),
    ),
  );
  const aeroRows = $derived(
    rowsBy((h) => h.aero?.tier, dataset.filters.aero_tiers.map((t) => ({ key: t.key, label: t.label }))),
  );

  function medianOf(rows: { key: string; items: { value: number }[] }[], key: string) {
    const r = rows.find((x) => x.key === key);
    return r ? Math.round(median(r.items.map((i) => i.value)) ?? 0) : null;
  }
  const rotMedian = $derived(medianOf(protectionRows, "rotational"));
  const noneMedian = $derived(medianOf(protectionRows, "none"));
</script>

<section class="mx-auto mt-6 max-w-6xl space-y-6" aria-labelledby="charts-title">
  <div>
    <h1 id="charts-title" class="text-2xl font-semibold tracking-tight">Charts</h1>
    <p class="mt-1 text-sm text-ink-2">Browse the whole catalogue visually. Hover a dot for the helmet, click it for full details.</p>
  </div>

  <figure class="card p-5">
    <div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
      <h2 class="text-lg font-semibold">Does paying more buy more safety?</h2>
      <span class="text-sm text-ink-3">{ride ? ride.label : "All styles"} · {result.ranked.length} helmets</span>
    </div>
    <PositionChart {result} size="full" showBand />
    <figcaption class="mt-2 text-sm text-ink-2">
      Up and to the left is better. The shaded band is the typical safety at each price; helmets above it beat their price. The stepped
      line connects helmets nothing else beats on both safety and price. Pick a riding style in <button class="underline" onclick={() => (app.view = "find")}>Find a helmet</button> to narrow this chart.
    </figcaption>
  </figure>

  <div class="grid gap-6 lg:grid-cols-2">
    <figure class="card p-5">
      <h2 class="mb-1 text-lg font-semibold">Which riding style is safest?</h2>
      <p class="mb-4 text-sm text-ink-2">Safety score of every tested helmet, by style, sorted by median.</p>
      <CategoryStrips rows={styleRows} ariaLabel="Safety score distribution by helmet style" />
    </figure>

    <figure class="card p-5">
      <h2 class="mb-1 text-lg font-semibold">Does rotational protection help?</h2>
      <p class="mb-4 text-sm text-ink-2">
        {#if rotMedian != null && noneMedian != null}
          Median safety with a slip-plane system is {rotMedian}, without any system {noneMedian}.
        {:else}
          Safety score by rotational-protection system.
        {/if}
      </p>
      <CategoryStrips rows={protectionRows} ariaLabel="Safety score distribution by rotational protection system" />
    </figure>

    <figure class="card p-5 lg:col-span-2">
      <h2 class="mb-1 text-lg font-semibold">Are aero helmets less safe?</h2>
      <p class="mb-4 text-sm text-ink-2">
        Safety of the {aeroRows.reduce((n, r) => n + r.items.length, 0)} wind-tunnel-tested helmets, grouped by aero result.
      </p>
      <CategoryStrips rows={aeroRows} ariaLabel="Safety score distribution by aero tier" />
    </figure>
  </div>
</section>
