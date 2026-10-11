<script lang="ts">
  import { explain, type FinderResult, type Ranked } from "../lib/finder";
  import { priceLabel, priceSourceLabel } from "../lib/format";
  import { PICK_META } from "../lib/picks";
  import { app, MAX_COMPARE, toggleCompare } from "../lib/state.svelte";
  import type { RatingSourceKey } from "../lib/types";
  import HelmetImage from "./HelmetImage.svelte";
  import SafetyMeter from "./SafetyMeter.svelte";

  let { item, result, labLabel }: { item: Ranked; result: FinderResult; labLabel: (k: RatingSourceKey) => string } =
    $props();

  const reasons = $derived(explain(item, result, labLabel).filter((r) => r.tone !== "neutral").slice(0, 3));
  const comparing = $derived(app.compare.includes(item.helmet.id));
</script>

<article
  class="card flex flex-col overflow-hidden transition hover:border-line-strong {item.picks.includes('best')
    ? 'ring-2 ring-accent'
    : ''}"
>
  <div class="flex flex-wrap gap-1 px-4 pt-4">
    {#each item.picks as kind (kind)}
      <span
        class="rounded-full px-2 py-0.5 text-xs font-semibold {kind === 'best' ? 'bg-accent text-accent-ink' : 'bg-accent-soft text-ink'}"
        title={PICK_META[kind].hint}>{PICK_META[kind].label}</span
      >
    {/each}
  </div>
  <button class="flex flex-1 flex-col px-4 pt-3 text-left" onclick={() => (app.selected = item.helmet.id)}>
    <HelmetImage helmet={item.helmet} class="aspect-[4/3] w-full max-sm:aspect-auto max-sm:h-28" />
    <span class="mt-3 text-xs text-ink-3">{item.helmet.brand}</span>
    <span class="leading-snug font-semibold">{item.helmet.model}</span>
    <div class="mt-3 flex items-end justify-between gap-2">
      <div>
        <span class="block text-xs text-ink-3">Safety</span>
        <SafetyMeter value={item.safety} size="sm" />
      </div>
      <div class="text-right">
        <span class="block text-lg font-semibold num">{priceLabel(item.price)}</span>
        <span class="block text-xs text-ink-3">{priceSourceLabel(item.price)}</span>
      </div>
    </div>
    <ul class="mt-3 mb-4 space-y-1 text-xs">
      {#each reasons as r (r.text)}
        <li class="flex gap-1.5 {r.tone === 'caution' ? 'text-caution' : 'text-ink-2'}">
          <span aria-hidden="true">{r.tone === "caution" ? "!" : "✓"}</span>{r.text}
        </li>
      {/each}
    </ul>
  </button>
  <div class="mt-auto border-t border-line px-4 py-2">
    <label class="flex items-center gap-2 text-xs text-ink-2">
      <input
        type="checkbox"
        checked={comparing}
        disabled={!comparing && app.compare.length >= MAX_COMPARE}
        onchange={() => toggleCompare(item.helmet.id)}
        class="accent-(--accent)"
      />
      Compare
    </label>
  </div>
</article>
