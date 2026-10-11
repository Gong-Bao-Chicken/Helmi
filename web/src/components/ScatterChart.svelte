<script lang="ts">
  import { scaleLinear } from "d3-scale";
  import { line, curveStepAfter } from "d3-shape";
  import type { FinderResult, Ranked } from "../lib/finder";
  import { money, priceLabel } from "../lib/format";
  import { PICK_META } from "../lib/picks";
  import { app } from "../lib/state.svelte";

  let { result, currency }: { result: FinderResult; currency: string } = $props();

  const TOP = 10;
  const margin = { top: 16, right: 20, bottom: 40, left: 56 };
  let width = $state(720);
  const height = $derived(Math.max(320, Math.min(480, width * 0.6)));

  const points = $derived(result.ranked.filter((r) => r.price != null));
  const xMax = $derived(Math.max(50, ...points.map((p) => p.price!.amount)) * 1.05);
  const x = $derived(scaleLinear().domain([0, xMax]).nice().range([margin.left, width - margin.right]));
  const y = $derived(scaleLinear().domain([0, 100]).range([height - margin.bottom, margin.top]));

  const byId = $derived(new Map(points.map((p) => [p.helmet.id, p])));
  const frontierPath = $derived.by(() => {
    const pts = result.frontier.map((f) => byId.get(f.id)).filter((p): p is Ranked => !!p);
    return line<Ranked>()
      .x((p) => x(p.price!.amount))
      .y((p) => y(p.safety * 100))
      .curve(curveStepAfter)(pts);
  });

  // Draw order: background dots, then top matches, then picks, so highlights sit on top.
  const layered = $derived(
    [...points].sort((a, b) => layer(a) - layer(b) || b.rank - a.rank),
  );
  function layer(p: Ranked) {
    return p.picks.length ? 2 : p.rank <= TOP ? 1 : 0;
  }
  function fill(p: Ranked) {
    if (app.hovered === p.helmet.id || app.selected === p.helmet.id) return "var(--selected)";
    return p.rank <= TOP || p.picks.length ? "var(--highlight)" : "var(--dot)";
  }

  const hovered = $derived(app.hovered ? byId.get(app.hovered) : undefined);
  const labelled = $derived(result.picks.slice(0, 4).map((p) => p.item).filter((p) => p.price));
</script>

<div class="relative" bind:clientWidth={width}>
  <div class="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-ink-2" aria-hidden="true">
    <span class="flex items-center gap-1.5"><svg class="size-3"><circle cx="6" cy="6" r="4.5" fill="var(--highlight)" /></svg>Your top {TOP} and picks</span>
    <span class="flex items-center gap-1.5"><svg class="size-3"><circle cx="6" cy="6" r="4.5" fill="var(--dot)" /></svg>Other matches</span>
    <span class="flex items-center gap-1.5"><svg class="size-3"><circle cx="6" cy="6" r="3.5" fill="none" stroke="var(--dot)" stroke-width="2" /></svg>Estimated price</span>
    <span class="flex items-center gap-1.5"><svg class="h-3 w-5"><path d="M0 9h8V3h12" fill="none" stroke="var(--frontier)" stroke-width="2" /></svg>Best-value frontier</span>
  </div>

  <svg {width} {height} role="img" aria-label="Scatter plot of price against safety score for {points.length} helmets">
    <!-- grid + axes -->
    {#each y.ticks(5) as t (t)}
      <line x1={margin.left} x2={width - margin.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
      <text x={margin.left - 8} y={y(t)} dy="0.32em" text-anchor="end" class="fill-ink-3 text-[11px] num">{t}</text>
    {/each}
    {#each x.ticks(width < 500 ? 4 : 7) as t (t)}
      <text x={x(t)} y={height - margin.bottom + 18} text-anchor="middle" class="fill-ink-3 text-[11px] num">{money(t, currency)}</text>
    {/each}
    <line x1={margin.left} x2={width - margin.right} y1={y(0)} y2={y(0)} stroke="var(--axis)" />
    <text x={width - margin.right} y={height - 4} text-anchor="end" class="fill-ink-3 text-[11px]">Price →</text>
    <text x={10} y={margin.top} transform="rotate(-90 10 {margin.top})" text-anchor="end" dy="0.7em" class="fill-ink-3 text-[11px]">
      Safety score ↑
    </text>

    {#if frontierPath}
      <path d={frontierPath} fill="none" stroke="var(--frontier)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
    {/if}

    {#each layered as p (p.helmet.id)}
      {@const cx = x(p.price!.amount)}
      {@const cy = y(p.safety * 100)}
      {@const active = app.hovered === p.helmet.id || app.selected === p.helmet.id}
      {@const r = active ? 7 : p.picks.length ? 6 : 4.5}
      <g
        role="button"
        tabindex="-1"
        aria-label="{p.helmet.brand} {p.helmet.model}"
        class="cursor-pointer"
        onmouseenter={() => (app.hovered = p.helmet.id)}
        onmouseleave={() => (app.hovered = null)}
        onclick={() => (app.selected = p.helmet.id)}
        onkeydown={(e) => e.key === "Enter" && (app.selected = p.helmet.id)}
      >
        <circle {cx} {cy} r="11" fill="transparent" />
        {#if p.price!.kind === "estimate"}
          <circle {cx} {cy} r={r - 1} fill="var(--chart-surface)" stroke={fill(p)} stroke-width="2" />
        {:else}
          <circle {cx} {cy} {r} fill={fill(p)} stroke="var(--chart-surface)" stroke-width="2" />
        {/if}
      </g>
    {/each}

    <!-- direct labels for the highlighted picks only -->
    {#each labelled as p (p.helmet.id)}
      {@const cx = x(p.price!.amount)}
      {@const cy = y(p.safety * 100)}
      {@const right = cx < width * 0.7}
      <text
        x={cx + (right ? 10 : -10)}
        y={cy - 9}
        text-anchor={right ? "start" : "end"}
        class="pointer-events-none fill-ink text-[11px] font-semibold"
        paint-order="stroke"
        stroke="var(--chart-surface)"
        stroke-width="4"
        stroke-linejoin="round">{PICK_META[p.picks[0]!].label}: {p.helmet.model}</text
      >
    {/each}
  </svg>

  {#if hovered}
    {@const left = x(hovered.price!.amount)}
    {@const top = y(hovered.safety * 100)}
    <div
      class="pointer-events-none absolute z-10 w-56 rounded-xl border border-line bg-surface p-3 text-xs shadow-card"
      style="left: {Math.min(left + 14, width - 230)}px; top: {top + 50}px"
    >
      <div class="text-ink-3">{hovered.helmet.brand}</div>
      <div class="font-semibold text-ink">{hovered.helmet.model}</div>
      <div class="mt-2 grid grid-cols-2 gap-y-0.5 num">
        <span class="text-ink-3">Safety</span><span class="text-right font-medium">{Math.round(hovered.safety * 100)}</span>
        <span class="text-ink-3">Price</span><span class="text-right font-medium">{priceLabel(hovered.price)}</span>
        <span class="text-ink-3">Rank</span><span class="text-right font-medium">#{hovered.rank}</span>
      </div>
    </div>
  {/if}

  <p class="mt-2 text-xs text-ink-3">
    Up and to the left is better. Helmets on the green line can't be beaten on both safety and price. Click a dot for details.
  </p>
</div>
