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
    countryPair,
    groupRows,
    labCoverage,
    latestTestYear,
    labPairs,
    MARKET_LABEL,
    priceVsLaunchByMarket,
    ratedHelmets,
    rowMedian,
    sortByMedian,
    sortByRecent,
    spearman,
    vtByYear,
    vtImpactPoints,
  } from "../lib/chartData";
  import { convert, marketCurrency, type MarketChoice } from "../lib/finder";
  import { makeLabLabel, money } from "../lib/format";
  import { median } from "../lib/scoring";
  import { app } from "../lib/state.svelte";
  import { orderedStyles, styleColor } from "../lib/styles";
  import StyleLegend from "./charts/StyleLegend.svelte";
  import type { Dataset, Helmet, MarketKey } from "../lib/types";
  import CategoryStrips from "./charts/CategoryStrips.svelte";
  import PriceSafetyExplorer from "./charts/PriceSafetyExplorer.svelte";
  import Scatter from "./charts/Scatter.svelte";

  let { dataset, fx }: { dataset: Dataset; fx: Record<string, number> } = $props();

  const filters = $derived({ ...app.charts, source: app.goals.safetySource });
  const labLabel = $derived(makeLabLabel(dataset));
  const currency = $derived(marketCurrency(filters.market));

  const MARKETS: { key: MarketChoice; label: string }[] = [
    { key: "de", label: "Germany" },
    { key: "at", label: "Austria" },
    { key: "ch", label: "Switzerland" },
    { key: "us", label: "US (launch price)" },
  ];

  // --- What makes a helmet safe
  const rated = $derived(ratedHelmets(dataset, filters));
  const styleRows = $derived(sortByMedian(groupRows(rated, (h) => h.style, orderedStyles(dataset.filters.styles))));
  const unclassified = $derived(styleRows.find((r) => r.key === "Unclassified")?.items.length ?? 0);
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
  const latestYear = $derived(latestTestYear(rated));
  const recentSince = $derived((latestYear ?? 0) - 1);
  /** "2025–26"; null when no rated helmet in view has a test year, which hides the recent comparison. */
  const recentRange = $derived(latestYear ? `${recentSince}–${String(latestYear).slice(2)}` : null);
  let brandsByRecent = $state(false);
  const brandList = $derived(brandRows(rated, 6, recentSince));
  const brands = $derived(brandsByRecent && recentRange ? sortByRecent(brandList) : brandList);
  const byDelta = $derived([...brandList].filter((b) => b.recent?.delta != null).sort((a, b) => b.recent!.delta! - a.recent!.delta!));
  const brandsUp = $derived(byDelta.filter((b) => b.recent!.delta! >= 5).map((b) => b.label));
  const brandsDown = $derived(byDelta.filter((b) => b.recent!.delta! <= -5).map((b) => b.label).reverse());

  // --- Prices
  const launchRows = $derived(priceVsLaunchByMarket(dataset, filters, fx));
  const launchSummary = $derived(
    [...launchRows]
      .map((r) => ({ label: r.label, med: rowMedian(r) }))
      .sort((a, b) => a.med - b.med)
      .map((r) => `${r.label} ${signed(r.med)}`)
      .join(", "),
  );

  // Every helmet dot on this page wears its riding style's color, as in the price/safety explorer.
  const byStyle = (h: Helmet) => styleColor(h.style);
  const styled = <T extends { helmet: Helmet }>(p: T) => ({ ...p, emphasis: "highlight" as const, color: byStyle(p.helmet) });

  const COUNTRIES = Object.entries(MARKET_LABEL) as [MarketKey, string][];
  let pairA = $state<MarketKey>("de");
  let pairB = $state<MarketKey>("ch");
  const pair = $derived(countryPair(dataset, pairA, pairB, fx));
  const pairPremium = $derived(median(pair.map((p) => (p.y / p.x - 1) * 100)));
  const pairMax = $derived(Math.max(100, ...pair.flatMap((p) => [p.x, p.y])) * 1.05);
  /** Each axis runs in its country's own currency over the same euro range, so the diagonal is "same price". */
  const fromEur = (market: MarketKey, eur: number) => convert(eur, "EUR", marketCurrency(market), fx);
  function swapPair() {
    [pairA, pairB] = [pairB, pairA];
  }

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
        <h3 class="mb-1 text-lg font-semibold">Where did prices fall the most since launch?</h3>
        {#if launchRows.length}
          <p class="mb-4 text-sm text-ink-2">
            Today's shop price in each country against the US price when Virginia Tech tested the helmet. Median change: {launchSummary}. Each dot
            is a helmet, the bar the median; left of 0% is cheaper than at launch.
          </p>
          <CategoryStrips
            rows={launchRows}
            domain={[-80, 60]}
            ticks={[-80, -60, -40, -20, 0, 20, 40, 60]}
            format={(v) => signed(v)}
            axisLabel="Price change since launch →"
            ariaLabel="Price change since launch by country"
            dotColor={byStyle}
          />
          <StyleLegend helmets={launchRows.flatMap((r) => r.items.map((i) => i.helmet))} />
        {:else}
          <p class="text-sm text-ink-3">Needs live shop prices. Run the price fetch.</p>
        {/if}
      </figure>

      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Where is a helmet cheaper?</h3>
        <div class="mb-3 flex flex-wrap items-center gap-2 text-sm">
          <select bind:value={pairA} class="rounded-lg border border-line bg-surface px-2 py-1" aria-label="First country">
            {#each COUNTRIES as [key, label] (key)}<option value={key} disabled={key === pairB}>{label}</option>{/each}
          </select>
          <button class="rounded-lg border border-line px-2 py-1 text-ink-2 hover:text-ink" onclick={swapPair} aria-label="Swap countries">⇄</button>
          <select bind:value={pairB} class="rounded-lg border border-line bg-surface px-2 py-1" aria-label="Second country">
            {#each COUNTRIES as [key, label] (key)}<option value={key} disabled={key === pairA}>{label}</option>{/each}
          </select>
        </div>
        {#if pair.length}
          <p class="mb-4 text-sm text-ink-2">
            The same helmet's shop price in {MARKET_LABEL[pairA]} and {MARKET_LABEL[pairB]}, for the {pair.length} helmets with a real shop price in
            both. Compared in euro: above the line it costs more in {MARKET_LABEL[pairB]}; the typical helmet is {signed(pairPremium ?? 0)} there.
            {#if pair.length < 20}Few helmets, so read this as a hint.{/if}
          </p>
          <Scatter
            points={pair.map((p) => styled({ helmet: p.helmet, x: p.a.amount, y: p.b.amount }))}
            xDomain={[0, fromEur(pairA, pairMax)]}
            yDomain={[0, fromEur(pairB, pairMax)]}
            xLabel="{MARKET_LABEL[pairA]}, {marketCurrency(pairA)} →"
            yLabel="{MARKET_LABEL[pairB]}, {marketCurrency(pairB)} ↑"
            details={(p) => {
              const q = pair.find((x) => x.helmet.id === p.helmet.id)!;
              return [
                [MARKET_LABEL[pairA], money(q.a.amount, q.a.currency)],
                [MARKET_LABEL[pairB], money(q.b.amount, q.b.currency)],
                ["Difference", signed((q.y / q.x - 1) * 100)],
              ];
            }}
            diagonal
            ariaLabel="{MARKET_LABEL[pairB]} against {MARKET_LABEL[pairA]} price for {pair.length} helmets"
          />
          <StyleLegend helmets={pair.map((p) => p.helmet)} />
        {:else}
          <p class="text-sm text-ink-3">No helmets with a real shop price in both {MARKET_LABEL[pairA]} and {MARKET_LABEL[pairB]} yet.</p>
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
        <CategoryStrips rows={styleRows} color={styleColor} ariaLabel="Safety score distribution by helmet style" />
        <p class="mt-3 text-xs text-ink-3">
          Styles come from Virginia Tech, a check of each model by hand, or words in the model name.{#if unclassified}{" "}{unclassified}
            {unclassified === 1 ? "helmet gives" : "helmets give"} no clue, so {unclassified === 1 ? "it is" : "they are"} listed as Unclassified
            rather than guessed.{/if}
        </p>
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
        <CategoryStrips rows={protectionRows} dotColor={byStyle} ariaLabel="Safety score distribution by rotational protection system" />
        <StyleLegend helmets={protectionRows.flatMap((r) => r.items.map((i) => i.helmet))} />
      </figure>

      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Are newer helmets safer?</h3>
        <p class="mb-4 text-sm text-ink-2">
          Virginia Tech percentile by the year VT tested the helmet. If later years sit further right, newer designs are scoring better.
        </p>
        <CategoryStrips rows={yearRows} rowHeight={30} dotColor={byStyle} axisLabel="Virginia Tech percentile →" ariaLabel="Virginia Tech percentile by test year" />
        <StyleLegend helmets={yearRows.flatMap((r) => r.items.map((i) => i.helmet))} />
      </figure>

      <figure class="card p-5">
        <h3 class="mb-1 text-lg font-semibold">Which brands are safest?</h3>
        <p class="mb-3 text-sm text-ink-2">
          Brands with at least six rated helmets.{#if recentRange}{" "}A brand's old models can drag its median down, so the diamond shows the
            median of its helmets tested in {recentRange}, and the arrow how far that sits above (▲) or below (▼) its older ones.{/if}
          {#if brandsUp.length}Improving most: {brandsUp.slice(0, 3).join(", ")}.{/if}
          {#if brandsDown.length}Slipping: {brandsDown.slice(0, 3).join(", ")}.{/if}
        </p>
        {#if recentRange}
          <div class="mb-3 inline-flex rounded-xl border border-line p-0.5 text-sm" role="group" aria-label="Rank brands by">
            <button class="rounded-[0.6rem] px-3 py-1 transition {!brandsByRecent ? 'bg-accent-soft font-medium text-ink' : 'text-ink-2 hover:text-ink'}" aria-pressed={!brandsByRecent} onclick={() => (brandsByRecent = false)}>All helmets</button>
            <button class="rounded-[0.6rem] px-3 py-1 transition {brandsByRecent ? 'bg-accent-soft font-medium text-ink' : 'text-ink-2 hover:text-ink'}" aria-pressed={brandsByRecent} onclick={() => (brandsByRecent = true)}>Recent helmets ({recentRange})</button>
          </div>
        {/if}
        <CategoryStrips
          rows={brands}
          rowHeight={26}
          recentLabel="median of {recentRange} helmets"
          ariaLabel="Safety score distribution by brand"
          dotColor={byStyle}
        />
        <StyleLegend helmets={brands.flatMap((r) => r.items.map((i) => i.helmet))} />
        {#if recentRange}
          <p class="mt-2 text-xs text-ink-3">Test year stands in for release year. Brands with fewer than two recent helmets show no diamond{brandsByRecent ? " and are listed last" : ""}.</p>
        {/if}
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
              points={pair.points.map(styled)}
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
      <StyleLegend helmets={pairs.flatMap((p) => p.points.map((q) => q.helmet))} />
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
          points={vtImpacts.map(styled)}
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
        <StyleLegend helmets={vtImpacts.map((p) => p.helmet)} />
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
          dotColor={byStyle}
        />
        <StyleLegend helmets={impactRows.flatMap((r) => r.items.map((i) => i.helmet))} />
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
        points={aero.map(styled)}
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
      <StyleLegend helmets={aero.map((p) => p.helmet)} />
    </figure>
  </div>

  <p class="pb-4 text-xs text-ink-3">
    Safety scores are percentiles: 100 is the safest helmet rated, 50 the middle. Prices in {currency}{filters.market === "us" ? " are US launch prices" : ""}.
  </p>
</section>
