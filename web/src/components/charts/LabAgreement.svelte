<script lang="ts">
  /** Each lab's percentile on one 0–100 scale, plus the combined score as a tick: do the labs agree? */
  import { labsFor } from "../../lib/finder";
  import type { Helmet, RatingSourceKey } from "../../lib/types";

  let {
    helmet,
    combined,
    labLabel,
    compact = false,
  }: { helmet: Helmet; combined: number | null; labLabel: (k: RatingSourceKey) => string; compact?: boolean } = $props();

  const labs = $derived(labsFor(helmet).map((key) => ({ key, pct: helmet.ratings[key]!.rank_pct! * 100 })));
  const spread = $derived(labs.length > 1 ? Math.max(...labs.map((l) => l.pct)) - Math.min(...labs.map((l) => l.pct)) : 0);
</script>

<div role="img" aria-label="Safety percentile by lab: {labs.map((l) => `${labLabel(l.key)} ${Math.round(l.pct)}`).join(', ')}">
  <div class="relative space-y-1.5">
    {#each labs as lab (lab.key)}
      <div class="grid grid-cols-[5.5rem_1fr_2rem] items-center gap-2 text-xs {compact ? 'grid-cols-[4rem_1fr_1.75rem]' : ''}">
        <span class="truncate text-ink-2">{labLabel(lab.key)}</span>
        <div class="relative h-3">
          <div class="absolute inset-x-0 top-1/2 h-px bg-(--axis)"></div>
          <div
            class="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-(--chart-surface) bg-(--highlight)"
            style="left: {lab.pct}%"
          ></div>
          {#if combined != null && labs.length > 1}
            <div class="absolute -inset-y-1 w-0.5 -translate-x-1/2 bg-ink" style="left: {combined * 100}%" aria-hidden="true"></div>
          {/if}
        </div>
        <span class="text-right font-medium num">{Math.round(lab.pct)}</span>
      </div>
    {/each}
  </div>
  {#if !compact}
    <div class="mt-1 grid grid-cols-[5.5rem_1fr_2rem] gap-2 text-[11px] text-ink-3">
      <span></span>
      <div class="flex justify-between"><span>least safe</span><span>safest</span></div>
      <span></span>
    </div>
    <p class="mt-2 text-xs text-ink-2">
      {#if labs.length < 2}
        Only one lab has tested this helmet, so there's nothing to cross-check yet.
      {:else if spread <= 15}
        The labs agree closely (within {Math.round(spread)} points). The black tick is the combined score.
      {:else}
        The labs disagree by {Math.round(spread)} points; they test different impacts. The black tick is the combined score.
      {/if}
    </p>
  {/if}
</div>
