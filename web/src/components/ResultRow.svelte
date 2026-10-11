<script lang="ts">
  import type { Ranked } from "../lib/finder";
  import { priceLabel, priceSourceLabel } from "../lib/format";
  import { PICK_META } from "../lib/picks";
  import { app, MAX_COMPARE, toggleCompare } from "../lib/state.svelte";
  import { styleLabel } from "../lib/styles";
  import type { RatingSourceKey } from "../lib/types";
  import HelmetImage from "./HelmetImage.svelte";
  import SafetyMeter from "./SafetyMeter.svelte";

  let { item, labLabel }: { item: Ranked; labLabel: (k: RatingSourceKey) => string } = $props();
  const comparing = $derived(app.compare.includes(item.helmet.id));
  const tech = $derived(item.helmet.protection?.rotational_label ?? item.helmet.protection?.mips_label);
</script>

<li
  class="flex items-center gap-3 px-3 py-2.5 transition sm:gap-4 sm:px-4 {app.hovered === item.helmet.id ? 'bg-surface-2' : ''}"
  onmouseenter={() => (app.hovered = item.helmet.id)}
  onmouseleave={() => (app.hovered = null)}
>
  <span class="w-6 shrink-0 text-right text-sm text-ink-3 num">{item.rank}</span>
  <button class="flex min-w-0 flex-1 items-center gap-3 text-left" onclick={() => (app.selected = item.helmet.id)}>
    <HelmetImage helmet={item.helmet} class="size-12 shrink-0" />
    <span class="min-w-0">
      <span class="line-clamp-2 font-medium sm:line-clamp-1">{item.helmet.brand} {item.helmet.model}</span>
      <span class="flex flex-wrap gap-x-2 text-xs text-ink-3">
        <span class="font-medium text-ink sm:hidden">Safety {Math.round(item.safety * 100)} ·</span>
        <span>{styleLabel(item.helmet.style)}</span>
        {#if tech}<span>· {tech}</span>{/if}
        <span class="hidden sm:inline">· {item.labs.map(labLabel).join(", ")}</span>
        {#each item.picks as kind (kind)}
          <span class="font-semibold text-accent">· {PICK_META[kind].label}</span>
        {/each}
      </span>
    </span>
  </button>
  <div class="hidden shrink-0 sm:block"><SafetyMeter value={item.safety} size="sm" /></div>
  <div class="w-24 shrink-0 text-right">
    <span class="block font-medium num">{priceLabel(item.price)}</span>
    <span class="block truncate text-[11px] text-ink-3">{priceSourceLabel(item.price)}</span>
  </div>
  <input
    type="checkbox"
    aria-label="Compare {item.helmet.model}"
    checked={comparing}
    disabled={!comparing && app.compare.length >= MAX_COMPARE}
    onchange={() => toggleCompare(item.helmet.id)}
    class="shrink-0 accent-(--accent)"
  />
</li>
