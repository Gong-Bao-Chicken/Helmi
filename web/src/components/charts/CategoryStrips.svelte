<script lang="ts">
  /**
   * One row of dots per category on a shared 0–100 safety axis, with each row's median. Rows with a
   * `recent` trend also get the recent helmets' median (hollow diamond) and the direction it moved.
   */
  import { scaleLinear } from "d3-scale";
  import { median } from "../../lib/scoring";
  import { app } from "../../lib/state.svelte";
  import { styleLabel } from "../../lib/styles";
  import type { Helmet } from "../../lib/types";
  import HelmetImage from "../HelmetImage.svelte";

  interface Row {
    key: string;
    label: string;
    hint?: string;
    items: { helmet: Helmet; value: number }[];
    recent?: { value: number; n: number; delta: number | null } | null;
  }
  interface Props {
    rows: Row[];
    ariaLabel: string;
    domain?: [number, number];
    ticks?: number[];
    axisLabel?: string;
    format?: (v: number) => string;
    rowHeight?: number;
    /** Dot color per row (e.g. the riding style's hue); default grey. */
    color?: (key: string) => string;
    /** Dot color per helmet (e.g. its riding style), used when rows aren't styles themselves. */
    dotColor?: (helmet: Helmet) => string;
    /** Legend text for the recent-median marker, e.g. "median of 2025–26 helmets". */
    recentLabel?: string;
  }
  let {
    rows,
    ariaLabel,
    domain = [0, 100],
    ticks = [0, 25, 50, 75, 100],
    axisLabel = "Safety score →",
    format = (v) => String(Math.round(v)),
    rowHeight = 40,
    color,
    dotColor,
    recentLabel = "recent median",
  }: Props = $props();

  const ROW_H = $derived(rowHeight);
  const LABEL_W = 132;
  let width = $state(600);
  const height = $derived(rows.length * ROW_H + 26);
  const hasTrend = $derived(rows.some((r) => r.recent));
  const x = $derived(scaleLinear().domain(domain).range([LABEL_W, width - (hasTrend ? 100 : 56)]));
  /** Values past the axis sit on its end instead of spilling over the labels. */
  const at = (v: number) => x(Math.min(Math.max(v, domain[0]), domain[1]));
  /** Moves under 5 points are within noise for a handful of helmets. */
  const arrow = (delta: number | null) => (delta == null ? "" : delta >= 5 ? `▲${Math.round(delta)}` : delta <= -5 ? `▼${Math.round(-delta)}` : "≈");
  const medians = $derived(rows.map((r) => median(r.items.map((i) => i.value))));

  // Deterministic jitter keeps dense rows countable without a force layout.
  function jitter(id: string) {
    let h = 0;
    for (let i = 0; i < id.length; i += 1) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    return ((h % 1000) / 1000 - 0.5) * (ROW_H - 16);
  }

  let tip = $state<{ helmet: Helmet; value: number; x: number; y: number } | null>(null);
</script>

<div class="relative" bind:clientWidth={width}>
  <svg {width} {height} role="img" aria-label={ariaLabel} class="block overflow-visible">
    {#each ticks as t (t)}
      <line x1={x(t)} x2={x(t)} y1={0} y2={rows.length * ROW_H} stroke="var(--grid)" />
      <text x={x(t)} y={rows.length * ROW_H + 16} text-anchor="middle" class="fill-ink-3 text-[11px] num">{format(t)}</text>
    {/each}
    {#each rows as row, i (row.key)}
      {@const cy = i * ROW_H + ROW_H / 2}
      {#if color}
        <circle cx={5} cy={cy} r={4.5} fill={color(row.key)} />
      {/if}
      <text x={color ? 15 : 0} y={cy} dy="0.32em" class="fill-ink text-[12px] font-medium">{row.label}</text>
      <text x={width} y={cy} dy="0.32em" text-anchor="end" class="fill-ink-3 text-[11px] num">n={row.items.length}</text>
      {#if row.recent}
        <text x={width - 40} y={cy} dy="0.32em" text-anchor="end" class="fill-ink-2 text-[11px] font-medium num"
          >{arrow(row.recent.delta)}<title>{recentLabel}: {format(row.recent.value)} from {row.recent.n} helmets{row.recent.delta != null
              ? `, ${row.recent.delta >= 0 ? "+" : "−"}${Math.abs(Math.round(row.recent.delta))} against older ones`
              : ""}</title></text
        >
      {/if}
      {#each row.items as item (item.helmet.id)}
        {@const active = app.hovered === item.helmet.id}
        <circle
          role="button"
          tabindex="-1"
          aria-label="{item.helmet.brand} {item.helmet.model}"
          cx={at(item.value)}
          cy={cy + jitter(item.helmet.id)}
          r={active ? 6 : rowHeight < 32 ? 3 : 3.5}
          fill={active ? "var(--selected)" : (dotColor?.(item.helmet) ?? color?.(row.key) ?? "var(--dot)")}
          fill-opacity={active || !(color || dotColor) ? 1 : 0.75}
          stroke="var(--chart-surface)"
          stroke-width={active ? 2 : 1}
          class="cursor-pointer"
          onmouseenter={() => {
            app.hovered = item.helmet.id;
            tip = { helmet: item.helmet, value: item.value, x: at(item.value), y: cy };
          }}
          onmouseleave={() => {
            app.hovered = null;
            tip = null;
          }}
          onclick={() => (app.selected = item.helmet.id)}
          onkeydown={(e) => e.key === "Enter" && (app.selected = item.helmet.id)}
        />
      {/each}
      {#if row.recent}
        {@const rx = at(row.recent.value)}
        <path
          d="M{rx} {cy - 6} L{rx + 5} {cy} L{rx} {cy + 6} L{rx - 5} {cy} Z"
          fill="var(--chart-surface)"
          stroke="var(--text)"
          stroke-width="1.75"
          class="pointer-events-none"
        />
      {/if}
      {#if medians[i] != null}
        <line x1={at(medians[i]!)} x2={at(medians[i]!)} y1={cy - ROW_H / 2 + 4} y2={cy + ROW_H / 2 - 4} stroke="var(--text)" stroke-width="2.5" stroke-linecap="round" />
      {/if}
    {/each}
  </svg>
  <div class="mt-1 flex items-center gap-4 text-xs text-ink-3" aria-hidden="true">
    <span class="flex items-center gap-1.5"><svg class="h-3 w-1"><rect width="2.5" height="12" fill="var(--text)" /></svg>median</span>
    {#if hasTrend}
      <span class="flex items-center gap-1.5"
        ><svg class="size-3"><path d="M6 1 L11 6 L6 11 L1 6 Z" fill="none" stroke="var(--text)" stroke-width="1.5" /></svg>{recentLabel}</span
      >
    {/if}
    <span>{axisLabel}</span>
  </div>

  {#if tip}
    <div
      class="pointer-events-none absolute z-20 flex w-60 gap-3 rounded-xl border border-line bg-surface p-3 text-xs shadow-card"
      style="left: {Math.max(0, Math.min(tip.x + 12, width - 244))}px; top: {tip.y + 14}px"
    >
      <HelmetImage helmet={tip.helmet} class="size-14 shrink-0" />
      <div class="min-w-0">
        <div class="truncate text-ink-3">{tip.helmet.brand}</div>
        <div class="font-semibold text-ink">{tip.helmet.model}</div>
        <div class="text-ink-3">{styleLabel(tip.helmet.style)}</div>
        <div class="mt-1 num">{axisLabel.replace(/\s*→$/, "")} <span class="font-semibold">{format(tip.value)}</span></div>
      </div>
    </div>
  {/if}
</div>
