<script lang="ts">
  /** Single-series histogram: thin columns with a 2px gap, an optional reference line and a median marker. */
  import { scaleLinear } from "d3-scale";
  import type { HistBin } from "../../lib/chartData";

  interface Props {
    bins: HistBin[];
    format: (v: number) => string;
    axisLabel: string;
    /** Vertical reference line at this x (e.g. 0 % change). */
    reference?: { at: number; label: string } | null;
    median?: number | null;
    medianLabel?: string;
    ariaLabel: string;
  }
  let { bins, format, axisLabel, reference = null, median = null, medianLabel = "median", ariaLabel }: Props = $props();

  let width = $state(400);
  const height = 220;
  const margin = { top: 22, right: 8, bottom: 40, left: 32 };
  const x = $derived(
    scaleLinear()
      .domain([bins[0]?.x0 ?? 0, bins[bins.length - 1]?.x1 ?? 1])
      .range([margin.left, width - margin.right]),
  );
  const maxCount = $derived(Math.max(1, ...bins.map((b) => b.count)));
  const y = $derived(scaleLinear().domain([0, maxCount]).nice().range([height - margin.bottom, margin.top]));
  let hover = $state<HistBin | null>(null);

  /** Column with only its top corners rounded (4px), anchored to the baseline. */
  function column(x0: number, x1: number, top: number, base: number) {
    const r = Math.min(4, (x1 - x0) / 2, base - top);
    return `M${x0},${base}V${top + r}Q${x0},${top} ${x0 + r},${top}H${x1 - r}Q${x1},${top} ${x1},${top + r}V${base}Z`;
  }
</script>

<div class="relative" bind:clientWidth={width}>
  <svg {width} {height} role="img" aria-label={ariaLabel} class="block overflow-visible">
    {#each y.ticks(4) as t (t)}
      <line x1={margin.left} x2={width - margin.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
      <text x={margin.left - 6} y={y(t)} dy="0.32em" text-anchor="end" class="fill-ink-3 text-[10px] num">{t}</text>
    {/each}
    {#each bins as b (b.x0)}
      {#if b.count > 0}
        <path
          d={column(x(b.x0) + 1, x(b.x1) - 1, y(b.count), y(0))}
          fill={hover === b ? "var(--selected)" : "var(--highlight)"}
          role="presentation"
          onpointerenter={() => (hover = b)}
          onpointerleave={() => (hover = null)}
        />
      {/if}
    {/each}
    <line x1={margin.left} x2={width - margin.right} y1={y(0)} y2={y(0)} stroke="var(--axis)" />
    {#each bins.filter((_, i) => i % Math.ceil(bins.length / (width < 420 ? 4 : 7)) === 0) as b (b.x0)}
      <text x={x(b.x0)} y={height - margin.bottom + 14} text-anchor="middle" class="fill-ink-3 text-[10px] num">{format(b.x0)}</text>
    {/each}
    <text x={width - margin.right} y={height - 6} text-anchor="end" class="fill-ink-3 text-[11px]">{axisLabel}</text>

    {#if reference}
      <line x1={x(reference.at)} x2={x(reference.at)} y1={margin.top - 8} y2={y(0)} stroke="var(--text-2)" stroke-width="1" />
      <text x={x(reference.at) + 4} y={margin.top - 10} class="fill-ink-2 text-[10px]">{reference.label}</text>
    {/if}
    {#if median != null}
      <line x1={x(median)} x2={x(median)} y1={margin.top} y2={y(0)} stroke="var(--text)" stroke-width="2" stroke-linecap="round" />
      <text
        x={x(median) - 4}
        y={margin.top + 8}
        text-anchor="end"
        class="fill-ink text-[11px] font-semibold"
        paint-order="stroke"
        stroke="var(--chart-surface)"
        stroke-width="4"
        stroke-linejoin="round">{medianLabel} {format(median)}</text
      >
    {/if}
  </svg>
  {#if hover}
    <div
      class="pointer-events-none absolute z-20 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs shadow-card num"
      style="left: {Math.min(x(hover.x0), width - 150)}px; top: {y(hover.count) - 40}px"
    >
      <span class="font-semibold">{hover.count}</span> helmets · {format(hover.x0)} to {format(hover.x1)}
    </div>
  {/if}
</div>
