<script lang="ts">
  /** One-dimensional distribution with one marked value, e.g. "#14 of 126 safest". */
  import { scaleLinear } from "d3-scale";

  interface Item {
    id: string;
    value: number;
    label: string;
  }
  interface Props {
    items: Item[];
    focusId: string;
    domain?: [number, number];
    format?: (v: number) => string;
    /** Caption for the low and high ends of the axis. */
    ends?: [string, string];
    focusLabel?: string;
    ariaLabel: string;
  }

  let { items, focusId, domain, format = (v) => String(Math.round(v)), ends, focusLabel, ariaLabel }: Props = $props();

  let width = $state(400);
  const height = 64;
  const pad = 10;
  const extent = $derived(
    domain ?? ([Math.min(...items.map((i) => i.value)), Math.max(...items.map((i) => i.value))] as [number, number]),
  );
  const x = $derived(scaleLinear().domain(extent).range([pad, width - pad]));
  const focus = $derived(items.find((i) => i.id === focusId));

  // Deterministic vertical jitter so dense values stay countable without a layout pass.
  function jitter(id: string) {
    let h = 0;
    for (let i = 0; i < id.length; i += 1) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    return ((h % 1000) / 1000 - 0.5) * 18;
  }
</script>

<div bind:clientWidth={width}>
  <svg {width} {height} role="img" aria-label={ariaLabel} class="block overflow-visible">
    <line x1={pad} x2={width - pad} y1={40} y2={40} stroke="var(--axis)" />
    {#each items as item (item.id)}
      {#if item.id !== focusId}
        <circle cx={x(item.value)} cy={40 + jitter(item.id)} r="3.5" fill="var(--dot)" opacity="0.7">
          <title>{item.label}: {format(item.value)}</title>
        </circle>
      {/if}
    {/each}
    {#if focus}
      {@const cx = x(focus.value)}
      {@const right = cx < width * 0.6}
      <line x1={cx} x2={cx} y1={18} y2={52} stroke="var(--highlight)" stroke-width="2" />
      <circle {cx} cy={40} r="6" fill="var(--highlight)" stroke="var(--chart-surface)" stroke-width="2">
        <title>{focus.label}: {format(focus.value)}</title>
      </circle>
      <text x={cx + (right ? 6 : -6)} y={12} text-anchor={right ? "start" : "end"} class="fill-ink text-[11px] font-semibold">
        {focusLabel ?? format(focus.value)}
      </text>
    {/if}
  </svg>
  {#if ends}
    <div class="flex justify-between text-[11px] text-ink-3"><span>{ends[0]}</span><span>{ends[1]}</span></div>
  {/if}
</div>
