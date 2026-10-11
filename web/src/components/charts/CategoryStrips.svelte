<script lang="ts">
  /** One row of dots per category on a shared 0–100 safety axis, with each row's median. */
  import { scaleLinear } from "d3-scale";
  import { median } from "../../lib/scoring";
  import { app } from "../../lib/state.svelte";
  import type { Helmet } from "../../lib/types";
  import HelmetImage from "../HelmetImage.svelte";

  interface Row {
    key: string;
    label: string;
    hint?: string;
    items: { helmet: Helmet; value: number }[];
  }
  let { rows, ariaLabel }: { rows: Row[]; ariaLabel: string } = $props();

  const ROW_H = 40;
  const LABEL_W = 132;
  let width = $state(600);
  const height = $derived(rows.length * ROW_H + 26);
  const x = $derived(scaleLinear().domain([0, 100]).range([LABEL_W, width - 56]));
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
    {#each [0, 25, 50, 75, 100] as t (t)}
      <line x1={x(t)} x2={x(t)} y1={0} y2={rows.length * ROW_H} stroke="var(--grid)" />
      <text x={x(t)} y={rows.length * ROW_H + 16} text-anchor="middle" class="fill-ink-3 text-[11px] num">{t}</text>
    {/each}
    {#each rows as row, i (row.key)}
      {@const cy = i * ROW_H + ROW_H / 2}
      <text x={0} y={cy} dy="0.32em" class="fill-ink text-[12px] font-medium">{row.label}</text>
      <text x={width} y={cy} dy="0.32em" text-anchor="end" class="fill-ink-3 text-[11px] num">n={row.items.length}</text>
      {#each row.items as item (item.helmet.id)}
        {@const active = app.hovered === item.helmet.id}
        <circle
          role="button"
          tabindex="-1"
          aria-label="{item.helmet.brand} {item.helmet.model}"
          cx={x(item.value)}
          cy={cy + jitter(item.helmet.id)}
          r={active ? 6 : 3.5}
          fill={active ? "var(--highlight)" : "var(--dot)"}
          stroke="var(--chart-surface)"
          stroke-width={active ? 2 : 1}
          class="cursor-pointer"
          onmouseenter={() => {
            app.hovered = item.helmet.id;
            tip = { helmet: item.helmet, value: item.value, x: x(item.value), y: cy };
          }}
          onmouseleave={() => {
            app.hovered = null;
            tip = null;
          }}
          onclick={() => (app.selected = item.helmet.id)}
          onkeydown={(e) => e.key === "Enter" && (app.selected = item.helmet.id)}
        />
      {/each}
      {#if medians[i] != null}
        <line x1={x(medians[i]!)} x2={x(medians[i]!)} y1={cy - ROW_H / 2 + 4} y2={cy + ROW_H / 2 - 4} stroke="var(--text)" stroke-width="2.5" stroke-linecap="round" />
      {/if}
    {/each}
  </svg>
  <div class="mt-1 flex items-center gap-4 text-xs text-ink-3" aria-hidden="true">
    <span class="flex items-center gap-1.5"><svg class="h-3 w-1"><rect width="2.5" height="12" fill="var(--text)" /></svg>median</span>
    <span>Safety score →</span>
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
        <div class="mt-1 num">Safety <span class="font-semibold">{Math.round(tip.value)}</span></div>
      </div>
    </div>
  {/if}
</div>
