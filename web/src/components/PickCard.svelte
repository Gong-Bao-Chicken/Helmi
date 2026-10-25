<script lang="ts">
  import { explain, type FinderResult, type Ranked } from "../lib/finder";
  import { priceLabel, priceSourceLabel } from "../lib/format";
  import { PICK_META } from "../lib/picks";
  import { app, MAX_COMPARE, toggleCompare } from "../lib/state.svelte";
  import type { RatingSourceKey } from "../lib/types";
  import EvidenceChip from "./EvidenceChip.svelte";
  import HelmetImage from "./HelmetImage.svelte";

  let { item, result, labLabel }: { item: Ranked; result: FinderResult; labLabel: (k: RatingSourceKey) => string } =
    $props();

  const reasons = $derived(explain(item, result, labLabel).filter((r) => r.tone !== "neutral").slice(0, 3));
  const comparing = $derived(app.compare.includes(item.helmet.id));
</script>

<article
  class="card flex flex-col overflow-hidden transition hover:border-line-strong {item.picks.includes('best') ? 'ring-2 ring-accent' : ''}"
  onmouseenter={() => (app.hovered = item.helmet.id)}
  onmouseleave={() => (app.hovered = null)}
>
  <div class="flex flex-wrap gap-1 px-4 pt-4">
    {#each item.picks as kind (kind)}
      <span
        class="rounded-full px-2 py-0.5 text-xs font-semibold {kind === 'best' ? 'bg-accent text-accent-ink' : 'bg-pick text-pick-ink'}"
        title={PICK_META[kind].hint}>{PICK_META[kind].label}</span
      >
    {/each}
  </div>
  <button class="flex flex-col px-4 pt-3 text-left" onclick={() => (app.selected = item.helmet.id)}>
    <div class="flex items-center gap-3">
      <HelmetImage helmet={item.helmet} class="size-24 shrink-0" />
      <div class="min-w-0">
        <span class="block text-xs text-ink-3">{item.helmet.brand}</span>
        <span class="block leading-snug font-semibold">{item.helmet.model}</span>
        <span class="mt-1 block text-lg font-semibold num">{priceLabel(item.price)}</span>
        <span class="block text-xs text-ink-3">{priceSourceLabel(item.price)}</span>
      </div>
    </div>
  </button>
  <div class="mt-3 flex items-start justify-between gap-2 px-4 text-xs text-ink-3">
    <span class="pt-0.5">Safety</span>
    <EvidenceChip helmet={item.helmet} safety={item.safety} source={app.goals.safetySource} {labLabel} />
  </div>
  <ul class="mt-3 mb-4 flex-1 space-y-1 px-4 text-xs">
    {#each reasons as r (r.text)}
      <li class="flex gap-1.5 {r.tone === 'caution' ? 'text-caution' : 'text-ink-2'}">
        <span aria-hidden="true">{r.tone === "caution" ? "!" : "✓"}</span>{r.text}
      </li>
    {/each}
  </ul>
  <div class="mt-auto border-t border-line px-2 py-1">
    <button
      class="flex min-h-11 w-full items-center gap-2 rounded-lg px-2 text-xs text-ink-2 hover:bg-surface-2 {comparing ? 'font-medium text-ink' : ''}"
      aria-pressed={comparing}
      disabled={!comparing && app.compare.length >= MAX_COMPARE}
      onclick={() => toggleCompare(item.helmet.id)}
    >
      <span class="grid size-5 place-items-center rounded border border-line-strong {comparing ? 'border-accent bg-accent text-accent-ink' : ''}" aria-hidden="true">{comparing ? "✓" : ""}</span>
      {comparing ? "In comparison" : "Compare"}
    </button>
  </div>
</article>
