<script lang="ts">
  /**
   * Price against safety for the whole catalogue, independent of the finder's goals. Categories
   * are shown by emphasis (one group highlighted, the rest greyed) or as small multiples: a
   * scatter can't carry six hues and stay readable for colour-blind readers.
   */
  import { area, curveMonotoneX, curveStepAfter, line } from "d3-shape";
  import type { ScaleLinear } from "d3-scale";
  import { priceSafetyPoints, type ChartFilters, type PricePoint } from "../../lib/chartData";
  import { marketCurrency } from "../../lib/finder";
  import { money, priceLabel } from "../../lib/format";
  import { fairValueBand, frontier, kneeId, median, type Bin, type Point } from "../../lib/scoring";
  import type { Dataset, Helmet } from "../../lib/types";
  import Scatter, { type ScatterPoint } from "./Scatter.svelte";

  let { dataset, fx, filters }: { dataset: Dataset; fx: Record<string, number>; filters: ChartFilters } = $props();

  type GroupBy = "style" | "protection";
  let groupBy = $state<GroupBy>("style");
  let focus = $state<string | null>(null);
  let split = $state(false);
  let includeEstimates = $state(false);
  let showBand = $state(false);

  const groups = $derived(
    groupBy === "style"
      ? dataset.filters.styles.map((s) => ({ key: s, label: s }))
      : dataset.filters.protection_groups.map((g) => ({ key: g.key as string, label: g.label })),
  );
  const groupOf = (h: Helmet) => (groupBy === "style" ? h.style : (h.protection_group ?? "none"));

  const livePoints = $derived(priceSafetyPoints(dataset, filters, fx, false));
  const withEstimates = $derived(priceSafetyPoints(dataset, filters, fx, true));
  const estimates = $derived(withEstimates.length - livePoints.length);
  /** Without any live prices (e.g. the US view, or before a price fetch) estimates are all there is. */
  const noLive = $derived(livePoints.length === 0);
  const all = $derived(includeEstimates || noLive ? withEstimates : livePoints);
  const counts = $derived(new Map(groups.map((g) => [g.key, all.filter((p) => groupOf(p.helmet) === g.key).length])));
  const currency = $derived(marketCurrency(filters.market));

  const xMax = $derived(Math.max(100, ...all.map((p) => p.price.amount)) * 1.04);
  const xDomain = $derived([0, xMax] as [number, number]);

  function toScatter(points: PricePoint[], subject: string | null): ScatterPoint[] {
    return points.map((p) => ({
      helmet: p.helmet,
      x: p.price.amount,
      y: p.safety,
      hollow: p.price.kind === "estimate",
      emphasis: subject == null ? "normal" : groupOf(p.helmet) === subject ? "highlight" : "context",
    }));
  }

  const asPoints = (pts: PricePoint[]): Point[] => pts.map((p) => ({ id: p.helmet.id, price: p.price.amount, safety: p.safety / 100 }));
  function analysis(pts: PricePoint[]) {
    const front = frontier(asPoints(pts));
    return { front, knee: kneeId(front), band: fairValueBand(asPoints(pts)) };
  }

  const subjectPoints = $derived(focus ? all.filter((p) => groupOf(p.helmet) === focus) : all);
  const main = $derived(analysis(subjectPoints));
  const kneeLabel = $derived.by(() => {
    const p = all.find((q) => q.helmet.id === main.knee);
    return p ? [{ id: p.helmet.id, text: `Sweet spot: ${p.helmet.model}` }] : [];
  });

  const panels = $derived(
    groups
      .filter((g) => (counts.get(g.key) ?? 0) > 0)
      .map((g) => {
        const own = all.filter((p) => groupOf(p.helmet) === g.key);
        return { ...g, points: toScatter(all, g.key), n: own.length, front: analysis(own).front, med: median(own.map((p) => p.safety)) };
      }),
  );

  function setGroupBy(next: GroupBy) {
    groupBy = next;
    focus = null;
  }

  const details = (p: ScatterPoint): [string, string][] => {
    const item = all.find((q) => q.helmet.id === p.helmet.id);
    return [
      ["Safety", String(Math.round(p.y))],
      ["Price", item ? priceLabel(item.price) : money(p.x, currency)],
      [groupBy === "style" ? "Style" : "Protection", groups.find((g) => g.key === groupOf(p.helmet))?.label ?? "–"],
    ];
  };
</script>

{#snippet frontierLine(front: Point[], xs: ScaleLinear<number, number>, ys: ScaleLinear<number, number>)}
  {@const d = line<Point>()
    .x((p) => xs(p.price))
    .y((p) => ys(p.safety * 100))
    .curve(curveStepAfter)(front)}
  {#if d}<path {d} fill="none" stroke="var(--frontier)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />{/if}
{/snippet}

{#snippet mainUnderlay(xs: ScaleLinear<number, number>, ys: ScaleLinear<number, number>)}
  {#if showBand && main.band.length > 1}
    {@const d = area<Bin>()
      .x((b) => xs(b.x))
      .y0((b) => ys(b.q25 * 100))
      .y1((b) => ys(b.q75 * 100))
      .curve(curveMonotoneX)(main.band)}
    {#if d}<path {d} fill="var(--text-3)" opacity="0.14" />{/if}
  {/if}
  {@render frontierLine(main.front, xs, ys)}
{/snippet}

<div class="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
  <div class="inline-flex rounded-xl border border-line p-0.5 text-sm" role="group" aria-label="Compare by">
    {#each [["style", "Riding style"], ["protection", "Rotational protection"]] as [key, label] (key)}
      <button
        class="rounded-[0.6rem] px-3 py-1 transition {groupBy === key ? 'bg-accent-soft font-medium text-ink' : 'text-ink-2 hover:text-ink'}"
        aria-pressed={groupBy === key}
        onclick={() => setGroupBy(key as GroupBy)}>{label}</button
      >
    {/each}
  </div>
  <div class="inline-flex rounded-xl border border-line p-0.5 text-sm" role="group" aria-label="Layout">
    <button class="rounded-[0.6rem] px-3 py-1 transition {!split ? 'bg-accent-soft font-medium text-ink' : 'text-ink-2 hover:text-ink'}" aria-pressed={!split} onclick={() => (split = false)}>One chart</button>
    <button class="rounded-[0.6rem] px-3 py-1 transition {split ? 'bg-accent-soft font-medium text-ink' : 'text-ink-2 hover:text-ink'}" aria-pressed={split} onclick={() => (split = true)}>One per group</button>
  </div>
</div>

{#if !split}
  <div class="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Highlight a group">
    <button
      class="rounded-full border px-3 py-1 text-sm transition {focus === null ? 'border-accent bg-accent-soft font-medium text-ink' : 'border-line text-ink-2 hover:border-line-strong'}"
      aria-pressed={focus === null}
      onclick={() => (focus = null)}>All <span class="text-ink-3 num">{all.length}</span></button
    >
    {#each groups as g (g.key)}
      {@const n = counts.get(g.key) ?? 0}
      <button
        class="rounded-full border px-3 py-1 text-sm transition disabled:opacity-40 {focus === g.key
          ? 'border-accent bg-accent-soft font-medium text-ink'
          : 'border-line text-ink-2 hover:border-line-strong'}"
        disabled={n === 0}
        aria-pressed={focus === g.key}
        onclick={() => (focus = focus === g.key ? null : g.key)}>{g.label} <span class="text-ink-3 num">{n}</span></button
      >
    {/each}
  </div>

  <div class="mb-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-ink-2" aria-hidden="true">
    {#if focus}
      <span class="flex items-center gap-1.5"><svg class="size-3"><circle cx="6" cy="6" r="4.5" fill="var(--highlight)" /></svg>{groups.find((g) => g.key === focus)?.label}</span>
      <span class="flex items-center gap-1.5"><svg class="size-3"><circle cx="6" cy="6" r="3.5" fill="var(--dot)" opacity="0.5" /></svg>Everything else</span>
    {/if}
    <span class="flex items-center gap-1.5"><svg class="h-3 w-5"><path d="M0 9h8V3h12" fill="none" stroke="var(--frontier)" stroke-width="2" /></svg>Best value: nothing is safer for less{focus ? " (this group)" : ""}</span>
    {#if includeEstimates || noLive}
      <span class="flex items-center gap-1.5"><svg class="size-3"><circle cx="6" cy="6" r="3.5" fill="none" stroke="var(--dot)" stroke-width="1.5" /></svg>Estimated price</span>
    {/if}
    {#if showBand}
      <span class="flex items-center gap-1.5"><svg class="h-3 w-5"><rect width="20" height="12" rx="2" fill="var(--text-3)" opacity="0.14" /></svg>Middle half of helmets at each price</span>
    {/if}
  </div>

  <Scatter
    points={toScatter(all, focus)}
    {xDomain}
    yDomain={[0, 100]}
    xLabel="Price →"
    yLabel="Safety score ↑"
    xFormat={(v) => money(v, currency)}
    xTicks={7}
    labels={kneeLabel}
    underlay={mainUnderlay}
    {details}
    ariaLabel="Price against safety score for {all.length} helmets"
  />
{:else}
  <div class="grid gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-3">
    {#each panels as panel (panel.key)}
      {#snippet panelUnderlay(xs: ScaleLinear<number, number>, ys: ScaleLinear<number, number>)}
        {@render frontierLine(panel.front, xs, ys)}
      {/snippet}
      <div>
        <div class="mb-1 flex items-baseline justify-between gap-2 text-xs">
          <span class="font-semibold text-ink">{panel.label}</span>
          <span class="text-ink-3 num">{panel.n} helmets{panel.med != null ? ` · median safety ${Math.round(panel.med)}` : ""}</span>
        </div>
        <Scatter
          points={panel.points}
          {xDomain}
          yDomain={[0, 100]}
          xLabel="Price"
          yLabel="Safety"
          xFormat={(v) => money(v, currency)}
          underlay={panelUnderlay}
          {details}
          compact
          ariaLabel="{panel.label}: price against safety for {panel.n} helmets"
        />
      </div>
    {/each}
  </div>
{/if}

<div class="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-2">
  {#if !split}
    <label class="flex items-center gap-2"><input type="checkbox" bind:checked={showBand} class="accent-(--accent)" />Show typical safety for the price</label>
  {/if}
  {#if noLive && estimates > 0}
    <span>No live shop prices in this market, so every price is estimated from the US launch price.</span>
  {:else if estimates > 0}
    <label class="flex items-center gap-2"
      ><input type="checkbox" bind:checked={includeEstimates} class="accent-(--accent)" />Include {estimates} helmets without a shop price (estimated from US launch price)</label
    >
  {/if}
</div>
