<script lang="ts">
  /**
   * Price vs safety for the shortlist. One component, three sizes:
   * - mini: card-sized, no axes; shows where one helmet sits.
   * - medium: drawer/compare-sized, light axes; backs a specific claim.
   * - full: the main "matches at a glance" chart with labels, band and tooltips.
   */
  import { scaleLinear } from "d3-scale";
  import { area, curveMonotoneX, curveStepAfter, line } from "d3-shape";
  import type { FinderResult, Ranked } from "../../lib/finder";
  import { money, priceLabel } from "../../lib/format";
  import { PICK_META } from "../../lib/picks";
  import type { Bin } from "../../lib/scoring";
  import { app } from "../../lib/state.svelte";
  import HelmetImage from "../HelmetImage.svelte";

  interface Props {
    result: FinderResult;
    size?: "mini" | "medium" | "full";
    /** Helmet the chart is about. */
    focusId?: string | null;
    /** Numbered, labelled helmets (compare view). */
    numbered?: string[];
    /** Similar-safety peers: dims everyone else and shades the safety window. */
    peers?: { ids: string[]; medianPrice: number; window: number } | null;
    showBand?: boolean;
    showFrontier?: boolean;
    /** Ring the frontier's knee point. */
    markKnee?: boolean;
    /** Horizontal reference line at this safety (0–1), e.g. the budget pick's safety bar. */
    threshold?: number | null;
    ariaLabel?: string;
  }

  let {
    result,
    size = "full",
    focusId = null,
    numbered = [],
    peers = null,
    showBand = false,
    showFrontier = true,
    markKnee = false,
    threshold = null,
    ariaLabel,
  }: Props = $props();

  const TOP = 10;
  const mini = $derived(size === "mini");
  const interactive = $derived(size !== "mini");
  const margin = $derived(
    mini ? { top: 8, right: 8, bottom: 8, left: 8 } : size === "medium" ? { top: 12, right: 16, bottom: 28, left: 34 } : { top: 16, right: 20, bottom: 40, left: 56 },
  );

  let width = $state(400);
  const height = $derived(mini ? 112 : size === "medium" ? 220 : Math.max(320, Math.min(460, width * 0.6)));

  const points = $derived(result.ranked.filter((r) => r.price != null));
  const currency = $derived(points[0]?.price?.currency ?? "EUR");
  const xMax = $derived(Math.max(50, ...points.map((p) => p.price!.amount)) * 1.05);
  const x = $derived(scaleLinear().domain([0, xMax]).nice().range([margin.left, width - margin.right]));
  const y = $derived(scaleLinear().domain([0, 100]).range([height - margin.bottom, margin.top]));
  const byId = $derived(new Map(points.map((p) => [p.helmet.id, p])));
  const peerSet = $derived(new Set(peers?.ids ?? []));
  const focus = $derived(focusId ? byId.get(focusId) : undefined);

  const frontierPath = $derived.by(() => {
    if (!showFrontier) return null;
    const pts = result.frontier.map((f) => byId.get(f.id)).filter((p): p is Ranked => !!p);
    return line<Ranked>()
      .x((p) => x(p.price!.amount))
      .y((p) => y(p.safety * 100))
      .curve(curveStepAfter)(pts);
  });

  const bandPath = $derived.by(() => {
    if (!showBand || result.band.length < 2) return null;
    return area<Bin>()
      .x((b) => x(b.x))
      .y0((b) => y(b.q25 * 100))
      .y1((b) => y(b.q75 * 100))
      .curve(curveMonotoneX)(result.band);
  });

  const knee = $derived(markKnee && result.kneeId ? byId.get(result.kneeId) : undefined);

  function role(p: Ranked): "focus" | "numbered" | "top" | "peer" | "other" {
    const id = p.helmet.id;
    if (id === focusId || (interactive && (id === app.hovered || id === app.selected))) return "focus";
    if (numbered.includes(id)) return "numbered";
    if (peers) return peerSet.has(id) ? "peer" : "other";
    if (size === "full" && (p.rank <= TOP || p.picks.length)) return "top";
    return "other";
  }
  const order = { other: 0, peer: 1, top: 2, numbered: 3, focus: 4 } as const;
  const layered = $derived([...points].sort((a, b) => order[role(a)] - order[role(b)] || b.rank - a.rank));

  function style(p: Ranked) {
    const r = role(p);
    if (r === "focus") return { fill: "var(--highlight)", radius: mini ? 6 : 7, opacity: 1 };
    if (r === "numbered") return { fill: "var(--highlight)", radius: 8, opacity: 1 };
    if (r === "top") return { fill: "var(--highlight)", radius: p.picks.length ? 6 : 4.5, opacity: 1 };
    if (r === "peer") return { fill: "var(--text-3)", radius: 4.5, opacity: 1 };
    // With a focus or peer set, push the rest further back so the subject reads first.
    const dim = focusId || peers || numbered.length;
    return { fill: "var(--dot)", radius: mini ? 3.5 : 4.5, opacity: dim ? 0.45 : 1 };
  }

  const hovered = $derived(interactive && app.hovered ? byId.get(app.hovered) : undefined);

  /** Direct labels, nudged apart vertically so they never overprint each other. */
  const labels = $derived.by(() => {
    const subjects = [
      ...(size === "full" ? result.picks.slice(0, 4).map((p) => p.item).filter((p) => p.price) : []),
      ...numbered.map((id) => byId.get(id)).filter((p): p is Ranked => !!p),
      ...(size === "medium" && focus ? [focus] : []),
    ];
    const seen = new Set<string>();
    const out = subjects
      .filter((p) => !seen.has(p.helmet.id) && seen.add(p.helmet.id))
      .map((p) => {
        const cx = x(p.price!.amount);
        const cy = y(p.safety * 100);
        const right = cx < width * 0.62;
        const n = numbered.indexOf(p.helmet.id);
        const text =
          n >= 0 ? p.helmet.model : size === "full" && p.picks[0] ? `${PICK_META[p.picks[0]].label}: ${p.helmet.model}` : p.helmet.model;
        return { id: p.helmet.id, x: cx + (right ? 12 : -12), y: cy - 10, anchor: right ? "start" : "end", text };
      })
      .sort((a, b) => a.y - b.y);
    const GAP = 14;
    for (let i = 0; i < out.length; i += 1) {
      out[i]!.y = Math.max(out[i]!.y, margin.top + 4, i ? out[i - 1]!.y + GAP : -Infinity);
    }
    return out;
  });
</script>

{#snippet dot(p: Ranked, cx: number, cy: number, s: { fill: string; radius: number }, r: string)}
  {#if p.price!.kind === "estimate" && r !== "numbered"}
    <circle {cx} {cy} r={s.radius - 1} fill="var(--chart-surface)" stroke={s.fill} stroke-width="2" />
  {:else}
    <circle {cx} {cy} r={s.radius} fill={s.fill} stroke="var(--chart-surface)" stroke-width="2" />
  {/if}
  {#if r === "numbered"}
    <text x={cx} y={cy} dy="0.35em" text-anchor="middle" class="pointer-events-none fill-white text-[10px] font-bold">{numbered.indexOf(p.helmet.id) + 1}</text>
  {/if}
{/snippet}

<div class="relative" bind:clientWidth={width}>
  {#if size === "full"}
    <div class="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-ink-2" aria-hidden="true">
      <span class="flex items-center gap-1.5"><svg class="size-3"><circle cx="6" cy="6" r="4.5" fill="var(--highlight)" /></svg>Your top {TOP} and picks</span>
      <span class="flex items-center gap-1.5"><svg class="size-3"><circle cx="6" cy="6" r="4.5" fill="var(--dot)" /></svg>Other matches</span>
      <span class="flex items-center gap-1.5"><svg class="size-3"><circle cx="6" cy="6" r="3.5" fill="none" stroke="var(--dot)" stroke-width="2" /></svg>Estimated price</span>
      <span class="flex items-center gap-1.5"><svg class="h-3 w-5"><path d="M0 9h8V3h12" fill="none" stroke="var(--frontier)" stroke-width="2" /></svg>Best-value frontier</span>
      {#if bandPath}
        <span class="flex items-center gap-1.5"><svg class="h-3 w-5"><rect width="20" height="12" rx="2" fill="var(--text-3)" opacity="0.14" /></svg>Typical safety for the price</span>
      {/if}
    </div>
  {/if}

  <svg {width} {height} role="img" aria-label={ariaLabel ?? `Price against safety score for ${points.length} helmets`} class="block overflow-visible">
    {#if !mini}
      {#each y.ticks(size === "medium" ? 3 : 5) as t (t)}
        <line x1={margin.left} x2={width - margin.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
        <text x={margin.left - 8} y={y(t)} dy="0.32em" text-anchor="end" class="fill-ink-3 text-[11px] num">{t}</text>
      {/each}
      {#each x.ticks(width < 420 ? 3 : size === "medium" ? 4 : 7) as t (t)}
        <text x={x(t)} y={height - margin.bottom + 18} text-anchor="middle" class="fill-ink-3 text-[11px] num">{money(t, currency)}</text>
      {/each}
      <line x1={margin.left} x2={width - margin.right} y1={y(0)} y2={y(0)} stroke="var(--axis)" />
      {#if size === "full"}
        <text x={width - margin.right} y={height - 4} text-anchor="end" class="fill-ink-3 text-[11px]">Price →</text>
        <text x={10} y={margin.top} transform="rotate(-90 10 {margin.top})" text-anchor="end" dy="0.7em" class="fill-ink-3 text-[11px]">Safety score ↑</text>
      {/if}
    {:else}
      <rect x="0" y="0" {width} {height} rx="10" fill="var(--surface-2)" />
    {/if}

    {#if bandPath}
      <path d={bandPath} fill="var(--text-3)" opacity="0.14" />
    {/if}

    {#if peers && focus}
      {@const top = y(Math.min(1, focus.safety + peers.window) * 100)}
      {@const bottom = y(Math.max(0, focus.safety - peers.window) * 100)}
      <rect x={margin.left} y={top} width={width - margin.left - margin.right} height={bottom - top} fill="var(--highlight)" opacity="0.08" />
      <line x1={x(peers.medianPrice)} x2={x(peers.medianPrice)} y1={top} y2={bottom} stroke="var(--text-2)" stroke-width="1.5" />
    {/if}

    {#if threshold != null}
      <line x1={margin.left} x2={width - margin.right} y1={y(threshold * 100)} y2={y(threshold * 100)} stroke="var(--text-2)" stroke-width="1" />
      <text x={width - margin.right - 4} y={y(threshold * 100) - 4} text-anchor="end" class="fill-ink-2 text-[10px] font-medium">safety bar {Math.round(threshold * 100)}</text>
    {/if}

    {#if frontierPath}
      <path d={frontierPath} fill="none" stroke="var(--frontier)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" opacity={mini && !markKnee ? 0.7 : 1} />
    {/if}

    {#each layered as p (p.helmet.id)}
      {@const cx = x(p.price!.amount)}
      {@const cy = y(p.safety * 100)}
      {@const s = style(p)}
      {@const r = role(p)}
      {#if interactive}
        <g
          role="button"
          tabindex="-1"
          aria-label="{p.helmet.brand} {p.helmet.model}"
          class="cursor-pointer"
          opacity={s.opacity}
          onmouseenter={() => (app.hovered = p.helmet.id)}
          onmouseleave={() => (app.hovered = null)}
          onclick={() => (app.selected = p.helmet.id)}
          onkeydown={(e) => e.key === "Enter" && (app.selected = p.helmet.id)}
        >
          <circle {cx} {cy} r="11" fill="transparent" />
          {@render dot(p, cx, cy, s, r)}
        </g>
      {:else}
        <g opacity={s.opacity}>{@render dot(p, cx, cy, s, r)}</g>
      {/if}
    {/each}

    {#if knee}
      <circle cx={x(knee.price!.amount)} cy={y(knee.safety * 100)} r="11" fill="none" stroke="var(--frontier)" stroke-width="2" />
    {/if}

    <!-- direct labels last, so they sit above the dots -->
    {#if peers && focus}
      <text
        x={x(peers.medianPrice) + 6}
        y={y(Math.max(0, focus.safety - peers.window) * 100) + 14}
        class="pointer-events-none fill-ink-2 text-[11px] font-medium"
        paint-order="stroke"
        stroke="var(--chart-surface)"
        stroke-width="4"
        stroke-linejoin="round">peer median {money(peers.medianPrice, currency)}</text
      >
    {/if}
    {#each labels as l (l.id)}
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
    {@const left = x(hovered.price!.amount)}
    {@const top = y(hovered.safety * 100)}
    {@const below = top < height / 2}
    <div
      class="pointer-events-none absolute z-20 flex w-64 gap-3 rounded-xl border border-line bg-surface p-3 text-xs shadow-card"
      style="left: {Math.max(0, Math.min(left + 14, width - 260))}px; top: {below ? top + 16 : top - 110}px"
    >
      <HelmetImage helmet={hovered.helmet} class="size-16 shrink-0" />
      <div class="min-w-0 flex-1">
        <div class="truncate text-ink-3">{hovered.helmet.brand}</div>
        <div class="font-semibold text-ink">{hovered.helmet.model}</div>
        <div class="mt-1.5 grid grid-cols-2 gap-y-0.5 num">
          <span class="text-ink-3">Safety</span><span class="text-right font-medium">{Math.round(hovered.safety * 100)}</span>
          <span class="text-ink-3">Price</span><span class="text-right font-medium">{priceLabel(hovered.price)}</span>
          <span class="text-ink-3">Rank</span><span class="text-right font-medium">#{hovered.rank}</span>
        </div>
      </div>
    </div>
  {/if}
</div>
