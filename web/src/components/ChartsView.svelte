<script lang="ts">
  /**
   * The nerdy corner: every chart reads the whole catalogue through this page's own filters,
   * never the finder's goals, so a chart means the same thing whatever you picked elsewhere.
   */
  import type { ScaleLinear } from "d3-scale";
  import {
    aeroSafetyPoints,
    brandRows,
    certimoovImpactRows,
    groupRows,
    histogram,
    labCoverage,
    labPairs,
    priceVsLaunch,
    ratedHelmets,
    rowMedian,
    sortByMedian,
    spearman,
    swissVsGerman,
    vtByYear,
    vtImpactPoints,
  } from "../lib/chartData";
  import { marketCurrency, type MarketChoice, type SafetySource } from "../lib/finder";
  import { makeLabLabel, money } from "../lib/format";
  import { median } from "../lib/scoring";
  import { app } from "../lib/state.svelte";
  import type { Dataset } from "../lib/types";
  import CategoryStrips from "./charts/CategoryStrips.svelte";
  import Histogram from "./charts/Histogram.svelte";
  import PriceSafetyExplorer from "./charts/PriceSafetyExplorer.svelte";
  import Scatter from "./charts/Scatter.svelte";

  let { dataset, fx }: { dataset: Dataset; fx: Record<string, number> } = $props();

  const filters = $derived(app.charts);
  const labLabel = $derived(makeLabLabel(dataset));
  const currency = $derived(marketCurrency(filters.market));

  const MARKETS: { key: MarketChoice; label: string }[] = [
    { key: "de", label: "Germany" },
    { key: "at", label: "Austria" },
    { key: "ch", label: "Switzerland" },
    { key: "us", label: "US (launch price)" },
  ];
  const SOURCES: { key: SafetySource; label: string }[] = [
    { key: "fused", label: "All labs combined" },
    { key: "virginia_tech", label: "Virginia Tech" },
    { key: "certimoov", label: "CERTIMOOV" },
    { key: "nsw_helmet_star", label: "NSW Helmet STAR" },
    { key: "folksam", label: "Folksam" },
  ];

  // --- What makes a helmet safe
  const rated = $derived(ratedHelmets(dataset, filters));
  const styleRows = $derived(sortByMedian(groupRows(rated, (h) => h.style, dataset.filters.styles.map((s) => ({ key: s, label: s })))));
  const protectionRows = $derived(
    groupRows(
      rated,
      (h) => h.protection_group ?? "none",
      dataset.filters.protection_groups.map((g) => ({ key: g.key, label: g.label, hint: g.hint })),
    ),
  );
  const medianOf = (key: string) => {
    const r = protectionRows.find((x) => x.key === key);
    return r ? Math.round(rowMedian(r)) : null;
  };
  const yearRows = $derived(vtByYear(dataset, filters));
  const brands = $derived(brandRows(rated));

  // --- Prices
  const launch = $derived(priceVsLaunch(dataset, filters, fx));
  const launchMedian = $derived(median(launch.map((l) => l.value)));
  const swiss = $derived(swissVsGerman(dataset, fx));
  const swissPremium = $derived(median(swiss.map((p) => (p.y / p.x - 1) * 100)));
  const swissMax = $derived(Math.max(100, ...swiss.flatMap((p) => [p.x, p.y])) * 1.05);

  // --- Labs
  const pairs = $derived(labPairs(dataset, filters));
  const coverage = $derived(labCoverage(dataset, filters));
  const coverageMax = $derived(Math.max(1, ...coverage.counts.map((c) => c.count)));
  const vtImpacts = $derived(vtImpactPoints(dataset, filters));
  const vtImpactRho = $derived(spearman(vtImpacts));
  const vtLowDomain = $derived([Math.max(...vtImpacts.map((p) => p.x), 1) * 1.05, 0] as [number, number]);
  const vtHighDomain = $derived([Math.max(...vtImpacts.map((p) => p.y), 1) * 1.05, 0] as [number, number]);
  const impactRows = $derived(certimoovImpactRows(dataset, filters));

  // --- Aero
  const aero = $derived(aeroSafetyPoints(dataset, filters));
  const aeroRho = $derived(spearman(aero));
  const aeroLabels = $derived(
    [...aero]
      .sort((a, b) => Math.min(b.x, b.y) - Math.min(a.x, a.y))
      .slice(0, 3)
      .map((p) => ({ id: p.helmet.id, text: p.helmet.model })),
  );

  /** For two measures of the same thing (labs, impact speeds). */
  function agreement(rho: number | null) {
    if (rho == null) return "";
    if (rho >= 0.7) return `agree closely (rank correlation ${rho.toFixed(2)})`;
    if (rho >= 0.4) return `partly agree (rank correlation ${rho.toFixed(2)})`;
    return `hardly agree (rank correlation ${rho.toFixed(2)})`;
  }
  /** For two different properties (aero vs safety). */
  function relation(rho: number | null) {
    if (rho == null) return "";
    const a = Math.abs(rho);
    const word = a >= 0.4 ? (rho > 0 ? "go together" : "trade off against each other") : a >= 0.2 ? (rho > 0 ? "go together a little" : "trade off a little") : "are unrelated";
    return `${word} (rank correlation ${rho.toFixed(2)})`;
  }
  const signed = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(Math.round(v))}%`;
</script>

{#snippet aeroQuadrants(xs: ScaleLinear<number, number>, ys: ScaleLinear<number, number>)}
  <line x1={xs(50)} x2={xs(50)} y1={ys(0)} y2={ys(100)} stroke="var(--axis)" />
  <line x1={xs(0)} x2={xs(100)} y1={ys(50)} y2={ys(50)} stroke="var(--axis)" />
  <text x={xs(100) - 4} y={ys(100) + 12} text-anchor="end" class="fill-ink-3 text-[11px] font-medium">Fast and safe</text>
  <text x={xs(0) + 4} y={ys(0) - 6} class="fill-ink-3 text-[11px] font-medium">Slow and less safe</text>
{/snippet}

<section class="mx-auto mt-6 max-w-6xl space-y-10" aria-labelledby="charts-title">
  <div>
    <h1 id="charts-title" class="text-2xl font-semibold tracking-tight">Charts</h1>
    <p class="mt-1 max-w-3xl text-sm text-ink-2">
      Everything the data can tell you about helmets. These charts look at the whole catalogue, not your shortlist. Hover a dot to see the
      helmet (it lights up in every chart), click it for full details.
    </p>
  </div>

  <!-- One filter row scopes every chart on the page. -->
  <div class="card sticky top-16 z-10 flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 text-sm" role="group" aria-label="Chart filters">
    <label class="flex items-center gap-2">
      <span class="label">Prices in</span>
      <select bind:value={app.charts.market} class="rounded-lg border border-line bg-surface px-2 py-1">
        {#each MARKETS as m (m.key)}<option value={m.key}>{m.label}</option>{/each}
      </select>
    </label>
    <label class="flex items-center gap-2">
      <span class="label">Safety from</span>
      <select bind:value={app.charts.source} class="rounded-lg border border-line bg-surface px-2 py-1">
        {#each SOURCES as s (s.key)}<option value={s.key}>{s.label}</option>{/each}
      </select>
    </label>
    <label class="flex items-center gap-2 text-ink-2">
      <input type="checkbox" bind:checked={app.charts.euOnly} class="accent-(--accent)" disabled={app.charts.market === "us"} />
      Sold in Europe only
    </label>
    <span class="ml-auto text-xs text-ink-3 num">{rated.length} rated helmets</span>
  </div>

  <!-- PRICE & VALUE -->
  <div class="space-y-6">
    <h2 class="text-xl font-semibold tracking-tight">Price and value</h2>
    <figure class="card p-5">
      <h3 class="mb-1 text-lg font-semibold">Does paying more buy more safety?</h3>
      <p class="mb-4 text-sm text-ink-2">
        Up and to the left is better. The stepped line links the helmets nothing else beats on both safety and price; past its sweet spot,
        extra money buys little extra safety.
      </p>
      <PriceSafetyExplorer {dataset} {fx} {filters} />
    </figure>

    <div class="grid gap-6 lg:grid-cols-2">
      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Are helmets cheaper now than at launch?</h3>
        {#if launch.length}
          <p class="mb-4 text-sm text-ink-2">
            Today's shop price against the US price when Virginia Tech tested the helmet, for {launch.length} helmets. The typical helmet costs
            {signed(launchMedian ?? 0)} compared with launch.
          </p>
          <Histogram
            bins={histogram(
              launch.map((l) => l.value),
              10,
              [-80, 60],
            )}
            format={(v) => signed(v)}
            axisLabel="Price change since launch →"
            reference={{ at: 0, label: "launch price" }}
            median={launchMedian}
            ariaLabel="Distribution of price change since launch"
          />
        {:else}
          <p class="text-sm text-ink-3">Needs live shop prices in this market. Pick Germany, Austria or Switzerland, or run the price fetch.</p>
        {/if}
      </figure>

      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Is Switzerland more expensive?</h3>
        {#if swiss.length}
          <p class="mb-4 text-sm text-ink-2">
            The same helmet's Swiss price (converted to euro) against its German price, for {swiss.length} helmets sold in both. Above the line
            costs more in Switzerland; the typical helmet is {signed(swissPremium ?? 0)}.
          </p>
          <Scatter
            points={swiss.map((p) => ({ ...p, emphasis: "highlight" as const }))}
            xDomain={[0, swissMax]}
            yDomain={[0, swissMax]}
            xLabel="Germany →"
            yLabel="Switzerland, in € ↑"
            xFormat={(v) => money(v, "EUR")}
            yFormat={(v) => money(v, "EUR")}
            diagonal
            ariaLabel="Swiss against German price for {swiss.length} helmets"
          />
        {:else}
          <p class="text-sm text-ink-3">No helmets with both a German and a Swiss shop price yet.</p>
        {/if}
      </figure>
    </div>
  </div>

  <!-- WHAT MAKES A HELMET SAFE -->
  <div class="space-y-6">
    <h2 class="text-xl font-semibold tracking-tight">What makes a helmet safe?</h2>
    <div class="grid gap-6 lg:grid-cols-2">
      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Which riding style is safest?</h3>
        <p class="mb-4 text-sm text-ink-2">Safety score of every rated helmet by style, safest median first. Each dot is a helmet, the bar the median.</p>
        <CategoryStrips rows={styleRows} ariaLabel="Safety score distribution by helmet style" />
      </figure>

      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Does rotational protection help?</h3>
        <p class="mb-4 text-sm text-ink-2">
          {#if medianOf("rotational") != null && medianOf("none") != null}
            Median safety with a slip-plane system (MIPS and similar) is {medianOf("rotational")}, without any system {medianOf("none")}. Newer and
            pricier helmets have it more often, so not all of the gap is down to the system.
          {:else}
            Safety score by rotational-protection system.
          {/if}
        </p>
        <CategoryStrips rows={protectionRows} ariaLabel="Safety score distribution by rotational protection system" />
      </figure>

      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Are newer helmets safer?</h3>
        <p class="mb-4 text-sm text-ink-2">
          Virginia Tech percentile by the year VT tested the helmet. If later years sit further right, newer designs are scoring better.
        </p>
        <CategoryStrips rows={yearRows} rowHeight={30} axisLabel="Virginia Tech percentile →" ariaLabel="Virginia Tech percentile by test year" />
      </figure>

      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Which brands are safest?</h3>
        <p class="mb-4 text-sm text-ink-2">Brands with at least six rated helmets, by median safety. A wide spread means the brand's range is uneven.</p>
        <CategoryStrips rows={brands} rowHeight={26} ariaLabel="Safety score distribution by brand" />
      </figure>
    </div>
  </div>

  <!-- LABS -->
  <div class="space-y-6">
    <h2 class="text-xl font-semibold tracking-tight">Inside the lab tests</h2>

    <figure class="card p-5">
      <h3 class="mb-1 text-lg font-semibold">Do the labs agree?</h3>
      <p class="mb-4 text-sm text-ink-2">
        Helmets tested by two labs, each lab's percentile on one axis. On the diagonal the labs agree; far from it, they rate the helmet very
        differently. The labs hit helmets at different speeds and places, so some disagreement is expected.
      </p>
      <div class="grid gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-3">
        {#each pairs as pair (pair.a + pair.b)}
          <div>
            <div class="mb-1 text-xs font-semibold text-ink">{labLabel(pair.a)} vs {labLabel(pair.b)}</div>
            <div class="mb-2 text-xs text-ink-3">{pair.points.length} helmets · the labs {agreement(pair.rho)}</div>
            <Scatter
              points={pair.points.map((p) => ({ ...p, emphasis: "highlight" as const }))}
              xDomain={[0, 100]}
              yDomain={[0, 100]}
              xLabel="{labLabel(pair.a)} percentile"
              yLabel="{labLabel(pair.b)} percentile"
              diagonal
              compact
              height={220}
              ariaLabel="{labLabel(pair.a)} against {labLabel(pair.b)} percentile for {pair.points.length} helmets"
            />
          </div>
        {/each}
      </div>
    </figure>

    <div class="grid gap-6 lg:grid-cols-2">
      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Slow crashes vs fast crashes</h3>
        <p class="mb-4 text-sm text-ink-2">
          Virginia Tech's concussion-risk score split into its low-speed and high-speed impacts (lower is safer, so the axes run backwards: up
          and right is safer). The two {agreement(vtImpactRho)}{(vtImpactRho ?? 0) >= 0.7
            ? ": a helmet that handles slow crashes well usually handles fast ones well too. The outliers are the interesting ones."
            : ": a helmet good at one is not automatically good at the other."}
        </p>
        <Scatter
          points={vtImpacts.map((p) => ({ ...p, emphasis: "highlight" as const }))}
          xDomain={vtLowDomain}
          yDomain={vtHighDomain}
          xLabel="Low-speed risk score, safer →"
          yLabel="High-speed risk score, safer ↑"
          xFormat={(v) => v.toFixed(0)}
          yFormat={(v) => v.toFixed(0)}
          details={(p) => [
            ["Low-speed score", p.x.toFixed(2)],
            ["High-speed score", p.y.toFixed(2)],
          ]}
          ariaLabel="Virginia Tech low-speed against high-speed impact score for {vtImpacts.length} helmets"
        />
      </figure>

      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Where do helmets protect least?</h3>
        <p class="mb-4 text-sm text-ink-2">
          CERTIMOOV scores every impact location from 0 to 5 (higher is better). Ordered from best-protected to worst.
        </p>
        <CategoryStrips
          rows={impactRows}
          domain={[0, 5]}
          ticks={[0, 1, 2, 3, 4, 5]}
          axisLabel="CERTIMOOV impact score →"
          format={(v) => (Number.isInteger(v) ? String(v) : v.toFixed(1))}
          ariaLabel="CERTIMOOV score by impact location"
        />
      </figure>

      <figure class="card p-5 lg:col-span-2">
        <h3 class="mb-1 text-lg font-semibold">Who tested what?</h3>
        <p class="mb-4 text-sm text-ink-2">
          Helmets in this view rated by each lab. {coverage.multi} of {coverage.any} were tested by more than one lab, which is what the agreement
          charts above are built on.
        </p>
        <div class="space-y-2" role="img" aria-label="Number of helmets rated by each lab">
          {#each coverage.counts as c (c.key)}
            <div class="grid grid-cols-[8rem_1fr_3rem] items-center gap-3 text-sm">
              <span class="truncate text-ink-2">{labLabel(c.key)}</span>
              <div class="h-3"><div class="h-full rounded-r bg-(--highlight)" style="width: {(c.count / coverageMax) * 100}%"></div></div>
              <span class="text-right font-medium num">{c.count}</span>
            </div>
          {/each}
        </div>
      </figure>
    </div>
  </div>

  <!-- AERO -->
  <div class="space-y-6">
    <h2 class="text-xl font-semibold tracking-tight">Aero</h2>
    <figure class="card p-5">
      <h3 class="mb-1 text-lg font-semibold">Do you have to choose between fast and safe?</h3>
      <p class="mb-4 text-sm text-ink-2">
        {aero.length} helmets with both a wind-tunnel result (Cyclingnews tests at 40 km/h) and a safety rating. Aero and safety {relation(aeroRho)}{(aeroRho ?? 0) > -0.2
          ? ", so you don't have to give up safety for speed."
          : "."}
      </p>
      <Scatter
        points={aero.map((p) => ({ ...p, emphasis: "highlight" as const }))}
        xDomain={[0, 100]}
        yDomain={[0, 100]}
        xLabel="Aero percentile, faster →"
        yLabel="Safety score ↑"
        labels={aeroLabels}
        underlay={aeroQuadrants}
        details={(p) => [
          ["Aero percentile", String(Math.round(p.x))],
          ["Safety", String(Math.round(p.y))],
          ["Watts saved", p.helmet.aero?.watts_saved != null ? `${p.helmet.aero.watts_saved.toFixed(1)} W` : "–"],
        ]}
        ariaLabel="Aero percentile against safety for {aero.length} helmets"
      />
    </figure>
  </div>

  <p class="pb-4 text-xs text-ink-3">
    Safety scores are percentiles: 100 is the safest helmet rated, 50 the middle. Prices in {currency}{filters.market === "us" ? " are US launch prices" : ""}.
  </p>
</section>
