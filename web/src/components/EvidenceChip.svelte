<script lang="ts">
  /** Safety score with what backs it: word band, how many labs tested it, whether they agree, and the calculation on demand. */
  import { evidenceFor, scoreBand, type SafetySource } from "../lib/finder";
  import { app } from "../lib/state.svelte";
  import type { Helmet, RatingSourceKey } from "../lib/types";
  import SafetyMeter from "./SafetyMeter.svelte";

  let {
    helmet,
    safety,
    source,
    labLabel,
    size = "sm",
  }: { helmet: Helmet; safety: number; source: SafetySource; labLabel: (k: RatingSourceKey) => string; size?: "sm" | "md" } = $props();

  const evidence = $derived(evidenceFor(helmet));
  const AGREEMENT = { none: "no lab result", single: "1 lab", agree: "labs agree", disagree: "labs disagree" } as const;
  const summary = $derived(
    evidence.agreement === "agree" || evidence.agreement === "disagree"
      ? `${evidence.labs.length} labs · ${AGREEMENT[evidence.agreement].replace("labs ", "")}`
      : AGREEMENT[evidence.agreement],
  );
  const weights = $derived(helmet.ratings.fused?.weights ?? {});

  let open = $state(false);
  let root = $state<HTMLElement>();
  const id = $props.id();
</script>

<svelte:window
  onclick={(e) => open && root && !root.contains(e.target as Node) && (open = false)}
  onkeydown={(e) => open && e.key === "Escape" && (e.stopPropagation(), (open = false))}
/>

<div class="relative inline-flex flex-col items-end gap-0.5" bind:this={root}>
  <SafetyMeter value={safety} {size} />
  <button
    class="flex items-center gap-1 text-[11px] text-ink-3 hover:text-ink {evidence.agreement === 'single' || evidence.agreement === 'disagree'
      ? 'text-caution'
      : ''}"
    aria-expanded={open}
    aria-controls={id}
    onclick={(e) => {
      e.stopPropagation();
      open = !open;
    }}
  >
    <span>{scoreBand(safety)} · {summary}</span>
    <span class="grid size-4 place-items-center rounded-full border border-current text-[10px] leading-none" aria-hidden="true">?</span>
    <span class="sr-only">How this score is calculated</span>
  </button>
  {#if open}
    <div {id} class="card absolute top-full right-0 z-30 mt-1 w-72 p-3 text-left text-xs shadow-card">
      <p class="font-medium text-ink">Safer than {Math.round(safety * 100)}% of lab-tested helmets</p>
      {#if source === "fused" && evidence.labs.length}
        <p class="mt-1 text-ink-3">Each lab's result becomes a percentile among the helmets that lab tested. Labs are weighted by how rigorous their test is:</p>
        <ul class="mt-2 space-y-0.5 num">
          {#each evidence.labs as lab (lab)}
            <li class="flex justify-between gap-2">
              <span>{labLabel(lab)} {helmet.ratings[lab]?.test_year ?? ""}</span>
              <span>{Math.round((helmet.ratings[lab]?.rank_pct ?? 0) * 100)} <span class="text-ink-3">· weight {(weights[lab] ?? 0).toFixed(2)}</span></span>
            </li>
          {/each}
          <li class="flex justify-between gap-2 border-t border-line pt-0.5 font-medium text-ink">
            <span>Weighted average</span><span>{Math.round(safety * 100)}</span>
          </li>
        </ul>
        {#if evidence.agreement === "single"}
          <p class="mt-2 text-caution">Only one lab has tested this helmet, so the score rests on a single test.</p>
        {:else if evidence.agreement === "disagree"}
          <p class="mt-2 text-caution">The labs' results are more than 30 points apart; read the lab results before relying on the score.</p>
        {/if}
      {:else if source !== "fused"}
        <p class="mt-1 text-ink-3">Ranked by {labLabel(source)} only, among the helmets that lab tested.</p>
      {/if}
      <button class="mt-2 text-accent hover:underline" onclick={() => ((app.view = "about"), (app.selected = null), (open = false))}>
        How the score works →
      </button>
    </div>
  {/if}
</div>
