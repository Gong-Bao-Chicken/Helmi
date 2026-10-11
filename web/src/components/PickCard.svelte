<script lang="ts">
  import { explain, SAFE_ENOUGH, type FinderResult, type Ranked } from "../lib/finder";
  import { priceLabel, priceSourceLabel } from "../lib/format";
  import { PICK_META } from "../lib/picks";
  import { app, MAX_COMPARE, toggleCompare } from "../lib/state.svelte";
  import type { RatingSourceKey } from "../lib/types";
  import PositionChart from "./charts/PositionChart.svelte";
  import StripPlot from "./charts/StripPlot.svelte";
  import HelmetImage from "./HelmetImage.svelte";
  import SafetyMeter from "./SafetyMeter.svelte";

  let { item, result, labLabel }: { item: Ranked; result: FinderResult; labLabel: (k: RatingSourceKey) => string } =
    $props();

  const reasons = $derived(explain(item, result, labLabel).filter((r) => r.tone !== "neutral").slice(0, 2));
  const comparing = $derived(app.compare.includes(item.helmet.id));
  const lead = $derived(item.picks[0] ?? "alt");
  const total = $derived(result.ranked.length);

  const caption = $derived.by(() => {
    switch (lead) {
      case "safest":
        return `Highest safety of your ${total} matches`;
      case "value":
        return "The bend in the green line: beyond it, more money buys little safety";
      case "budget":
        return "Cheapest helmet above the safety bar";
      case "aero":
        return "Aero score against every wind-tunnel-tested match";
      default:
        return `#${item.rank} of ${total} for your goals · up and left is better`;
    }
  });

  const aeroItems = $derived(
    result.ranked
      .filter((r) => r.helmet.aero?.score != null)
      .map((r) => ({ id: r.helmet.id, value: r.helmet.aero!.score!, label: r.helmet.model })),
  );
</script>

<article
  class="card flex flex-col overflow-hidden transition hover:border-line-strong {item.picks.includes('best') ? 'ring-2 ring-accent' : ''}"
  onmouseenter={() => (app.hovered = item.helmet.id)}
  onmouseleave={() => (app.hovered = null)}
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
    <div class="flex items-center gap-3">
      <HelmetImage helmet={item.helmet} class="size-20 shrink-0" />
      <div class="min-w-0">
        <span class="block text-xs text-ink-3">{item.helmet.brand}</span>
        <span class="block leading-snug font-semibold">{item.helmet.model}</span>
        <span class="mt-1 block text-lg font-semibold num">{priceLabel(item.price)}</span>
        <span class="block text-xs text-ink-3">{priceSourceLabel(item.price)}</span>
      </div>
    </div>
    <div class="mt-3 flex items-center justify-between text-xs text-ink-3">
      <span>Safety</span>
      <SafetyMeter value={item.safety} size="sm" />
    </div>

    <figure class="mt-3">
      {#if lead === "aero" && aeroItems.length > 1}
        <div class="rounded-[10px] bg-surface-2 px-2 pt-1">
          <StripPlot
            items={aeroItems}
            focusId={item.helmet.id}
            domain={[0, 100]}
            ends={["draggy", "fast"]}
            focusLabel="aero {item.helmet.aero?.score}"
            ariaLabel="Aero score of {item.helmet.model} compared with {aeroItems.length} tested matches"
          />
        </div>
      {:else}
        <PositionChart
          {result}
          size="mini"
          focusId={item.helmet.id}
          markKnee={lead === "value"}
          threshold={lead === "budget" ? SAFE_ENOUGH : null}
          ariaLabel="Position of {item.helmet.model} among {total} matches by price and safety"
        />
      {/if}
      <figcaption class="mt-1.5 text-[11px] leading-snug text-ink-3">{caption}</figcaption>
    </figure>

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
