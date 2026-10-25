<script lang="ts" module>
  import type { Helmet } from "../../lib/types";

  export interface ScatterPoint {
    helmet: Helmet;
    x: number;
    y: number;
    /** highlight = the subject, context = pushed back, normal = plain. */
    emphasis?: "highlight" | "context" | "normal";
    /** Hollow marker (e.g. an estimated price). */
    hollow?: boolean;
    /** Fill for a highlighted or normal point, e.g. its category's color (default: --highlight / --dot). */
    color?: string;
    /** Drawn larger and above everything else, e.g. the best-value helmets. */
    key?: boolean;
  }
</script>

<script lang="ts">
  /**
   * Generic helmet scatter: hairline grid, nearest-point hover (no pixel hunting), click opens
   * the helmet. Hovering a helmet rings it in every chart on the page via app.hovered.
   */
  import { scaleLinear, type ScaleLinear } from "d3-scale";
  import type { Snippet } from "svelte";
  import { app } from "../../lib/state.svelte";
  import { styleLabel } from "../../lib/styles";
  import HelmetImage from "../HelmetImage.svelte";

  interface Props {
    points: ScatterPoint[];
    xDomain: [number, number];
    yDomain: [number, number];
    xLabel: string;
    yLabel: string;
    xFormat?: (v: number) => string;
    yFormat?: (v: number) => string;
    xTicks?: number;
    yTicks?: number;
    /** Draw the corner-to-corner line: y = x when both domains match (agreement / parity charts). */
    diagonal?: boolean;
    /** Direct labels: selective, never on every point. */
    labels?: { id: string; text: string }[];
    /** Drawn under the dots; receives the scales. */
    underlay?: Snippet<[ScaleLinear<number, number>, ScaleLinear<number, number>]>;
    /** Extra tooltip rows for a point. */
    details?: (p: ScatterPoint) => [string, string][];
    compact?: boolean;
    height?: number;
    title?: string;
    ariaLabel: string;
  }

  let {
    points,
    xDomain,
    yDomain,
    xLabel,
    yLabel,
    xFormat = (v) => String(Math.round(v)),
    yFormat = (v) => String(Math.round(v)),
    xTicks = 5,
    yTicks = 5,
    diagonal = false,
    labels = [],
    underlay,
    details,
    compact = false,
    height: fixedHeight,
    title,
    ariaLabel,
  }: Props = $props();

  let width = $state(400);
  const margin = $derived(compact ? { top: 8, right: 10, bottom: 24, left: 30 } : { top: 12, right: 16, bottom: 40, left: 46 });
  const height = $derived(fixedHeight ?? (compact ? 200 : Math.max(280, Math.min(420, width * 0.62))));
  const x = $derived(scaleLinear().domain(xDomain).range([margin.left, width - margin.right]));
  const y = $derived(scaleLinear().domain(yDomain).range([height - margin.bottom, margin.top]));

  const RADIUS = { highlight: 4.5, normal: 3.5, context: 3 } as const;
  const FILL = { highlight: "var(--highlight)", normal: "var(--dot)", context: "var(--dot)" } as const;
  const OPACITY = { highlight: 1, normal: 0.85, context: 0.35 } as const;
  const LAYER = { context: 0, normal: 1, highlight: 2 } as const;
  const layer = (p: ScatterPoint) => LAYER[p.emphasis ?? "normal"] + (p.key ? 3 : 0);
  const layered = $derived([...points].sort((a, b) => layer(a) - layer(b)));
  const fill = (p: ScatterPoint, e: keyof typeof FILL) => (e !== "context" && p.color) || FILL[e];

  const byId = $derived(new Map(points.map((p) => [p.helmet.id, p])));
  let hoverId = $state<string | null>(null);
  const hovered = $derived(hoverId ? byId.get(hoverId) : undefined);
  /** The helmet hovered in another chart, if it is in this one. */
  const echoed = $derived(!hoverId && app.hovered ? byId.get(app.hovered) : undefined);

  function nearest(event: PointerEvent) {
    const svg = event.currentTarget as SVGSVGElement;
    const box = svg.getBoundingClientRect();
    const mx = event.clientX - box.left;
    const my = event.clientY - box.top;
    let best: ScatterPoint | undefined;
    let bestD = 24 * 24;
    for (const p of points) {
      const d = (x(p.x) - mx) ** 2 + (y(p.y) - my) ** 2;
      // Prefer emphasised points when they overlap context ones.
      const bias = p.emphasis === "context" ? 1.6 : 1;
      if (d * bias < bestD) {
        bestD = d * bias;
        best = p;
      }
    }
    return best;
  }

  function onMove(event: PointerEvent) {
    const p = nearest(event);
    hoverId = p?.helmet.id ?? null;
    app.hovered = hoverId;
  }
  function onLeave() {
    hoverId = null;
    app.hovered = null;
  }
  /** Keyboard: arrows step through helmets left to right, Enter opens one. */
  const byX = $derived([...points].sort((a, b) => x(a.x) - x(b.x)));
  function onKey(event: KeyboardEvent) {
    if (event.key === "Enter" && hoverId) {
      app.selected = hoverId;
      return;
    }
    const step = event.key === "ArrowRight" || event.key === "ArrowUp" ? 1 : event.key === "ArrowLeft" || event.key === "ArrowDown" ? -1 : 0;
    if (!step || !byX.length) return;
    event.preventDefault();
    const i = byX.findIndex((p) => p.helmet.id === hoverId);
    const next = byX[i < 0 ? 0 : (i + step + byX.length) % byX.length]!;
    hoverId = next.helmet.id;
    app.hovered = hoverId;
  }

  function onClick(event: MouseEvent) {
    const p = nearest(event as PointerEvent);
    if (p) app.selected = p.helmet.id;
  }

  const placedLabels = $derived.by(() => {
    const out = labels
      .map((l) => byId.get(l.id) && { ...l, p: byId.get(l.id)! })
      .filter((l): l is { id: string; text: string; p: ScatterPoint } => !!l)
      .map((l) => {
        const cx = x(l.p.x);
        const right = cx < width * 0.6;
        return { id: l.id, text: l.text, x: cx + (right ? 9 : -9), y: y(l.p.y) - 8, anchor: right ? "start" : "end" };
      })
      .sort((a, b) => a.y - b.y);
    for (let i = 1; i < out.length; i += 1) out[i]!.y = Math.max(out[i]!.y, out[i - 1]!.y + 14);
    return out;
  });
</script>

<div class="relative" bind:clientWidth={width}>
  {#if title}
    <div class="mb-1 text-xs font-semibold text-ink">{title}</div>
  {/if}
  <!-- Keyboard-operable (arrows + Enter, see onKey); Svelte doesn't treat role="application" as interactive. -->
  <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
  <svg
    {width}
    {height}
    role="application"
    tabindex="0"
    aria-label="{ariaLabel}. Use the arrow keys to step through helmets and Enter to open one."
    aria-roledescription="chart"
    class="block cursor-crosshair touch-none overflow-visible"
    onpointermove={onMove}
    onpointerleave={onLeave}
    onclick={onClick}
    onkeydown={onKey}
    onblur={onLeave}
  >
    {#each y.ticks(compact ? 3 : yTicks) as t (t)}
      <line x1={margin.left} x2={width - margin.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
      <text x={margin.left - 6} y={y(t)} dy="0.32em" text-anchor="end" class="fill-ink-3 text-[10px] num">{yFormat(t)}</text>
    {/each}
    {#each x.ticks(compact || width < 420 ? 3 : xTicks) as t (t)}
      <line x1={x(t)} x2={x(t)} y1={margin.top} y2={height - margin.bottom} stroke="var(--grid)" />
      <text x={x(t)} y={height - margin.bottom + 14} text-anchor="middle" class="fill-ink-3 text-[10px] num">{xFormat(t)}</text>
    {/each}
    {#if !compact}
      <text x={width - margin.right} y={height - 4} text-anchor="end" class="fill-ink-3 text-[11px]">{xLabel}</text>
      <text x={10} y={margin.top} transform="rotate(-90 10 {margin.top})" text-anchor="end" dy="0.7em" class="fill-ink-3 text-[11px]">{yLabel}</text>
    {/if}

    {#if diagonal}
      <line x1={x(xDomain[0])} y1={y(yDomain[0])} x2={x(xDomain[1])} y2={y(yDomain[1])} stroke="var(--axis)" stroke-width="1.5" />
    {/if}

    {#if underlay}{@render underlay(x, y)}{/if}

    {#each layered as p (p.helmet.id)}
      {@const e = p.emphasis ?? "normal"}
      {#if p.hollow}
        <circle cx={x(p.x)} cy={y(p.y)} r={RADIUS[e] - 0.75 + (p.key ? 1 : 0)} fill="none" stroke={fill(p, e)} stroke-width="1.5" opacity={OPACITY[e]} />
      {:else}
        <circle
          cx={x(p.x)}
          cy={y(p.y)}
          r={p.key ? 5 : RADIUS[e]}
          fill={fill(p, e)}
          stroke="var(--chart-surface)"
          stroke-width={p.key ? 2 : 1}
          opacity={p.key ? 1 : OPACITY[e]}
        />
      {/if}
    {/each}

    {#if hovered ?? echoed}
      {@const active = (hovered ?? echoed)!}
      <circle cx={x(active.x)} cy={y(active.y)} r="7" fill="var(--selected)" stroke="var(--chart-surface)" stroke-width="2" />
    {/if}

    {#each placedLabels as l (l.id)}
      <text
        x={l.x}
        y={l.y}
        text-anchor={l.anchor as "start" | "end"}
        class="pointer-events-none fill-ink text-[11px] font-semibold"
        paint-order="stroke"
        stroke="var(--chart-surface)"
        stroke-width="4"
        stroke-linejoin="round">{l.text}</text
      >
    {/each}
  </svg>

  {#if hovered}
    {@const left = x(hovered.x)}
    {@const top = y(hovered.y)}
    <div
      class="pointer-events-none absolute z-20 flex w-60 gap-3 rounded-xl border border-line bg-surface p-3 text-xs shadow-card"
      style="left: {Math.max(0, Math.min(left + 14, width - 244))}px; top: {top < height / 2 ? top + 14 : top - 104}px"
    >
      <HelmetImage helmet={hovered.helmet} class="size-14 shrink-0" />
      <div class="min-w-0 flex-1">
        <div class="truncate text-ink-3">{hovered.helmet.brand}</div>
        <div class="font-semibold text-ink">{hovered.helmet.model}</div>
        <div class="text-ink-3">{styleLabel(hovered.helmet.style)}</div>
        <div class="mt-1.5 grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 num">
          {#each details ? details(hovered) : [[xLabel.replace(/\s*[→↑]$/, ""), xFormat(hovered.x)], [yLabel.replace(/\s*[→↑]$/, ""), yFormat(hovered.y)]] as [k, v] (k)}
            <span class="text-ink-3">{k}</span><span class="text-right font-medium">{v}</span>
          {/each}
        </div>
      </div>
    </div>
  {/if}
</div>
