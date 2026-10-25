<script lang="ts">
  import { PRIORITIES, RIDES, type FinderResult } from "../lib/finder";
  import RideNote from "./RideNote.svelte";
  import { makeLabLabel } from "../lib/format";
  import { app } from "../lib/state.svelte";
  import type { Dataset } from "../lib/types";
  import PickCard from "./PickCard.svelte";
  import ResultRow from "./ResultRow.svelte";

  let { dataset, result }: { dataset: Dataset; result: FinderResult } = $props();

  const PAGE = 15;
  let shown = $state(PAGE);
  const labLabel = $derived(makeLabLabel(dataset));
  const ride = $derived(RIDES.find((r) => r.key === app.goals.ride));
  const priority = $derived(PRIORITIES.find((p) => p.key === app.goals.priority));

  // Reset paging whenever the goals change.
  $effect(() => {
    JSON.stringify(app.goals);
    shown = PAGE;
  });
</script>

<section aria-labelledby="results-title" class="min-w-0">
  <div class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 id="results-title" class="text-2xl font-semibold tracking-tight">
        {#if result.ranked.length}
          {result.ranked.length} {result.ranked.length === 1 ? "helmet fits" : "helmets fit"}
        {:else}
          No helmets fit yet
        {/if}
      </h1>
      <p class="mt-1 text-sm text-ink-2">{ride?.label} · ranked by <span class="lowercase">{priority?.label}</span></p>
    </div>
  </div>

  <RideNote ride={app.goals.ride} />

  {#if !result.ranked.length}
    <div class="card mt-6 p-6">
      <p class="text-ink-2">Your filters rule out every helmet for this kind of riding. Things that removed helmets:</p>
      <ul class="mt-3 space-y-1 text-sm">
        {#each result.excluded as e (e.reason)}
          <li><span class="font-medium num">{e.count}</span> {e.reason}</li>
        {/each}
      </ul>
      <div class="mt-4 flex flex-wrap gap-2">
        {#if app.goals.budget}<button class="btn" onclick={() => (app.goals.budget = null)}>Remove budget</button>{/if}
        {#if app.goals.rotational}<button class="btn" onclick={() => (app.goals.rotational = false)}>Allow helmets without rotational tech</button>{/if}
        {#if app.goals.pricedOnly}<button class="btn" onclick={() => (app.goals.pricedOnly = false)}>Include helmets without a shop price</button>{/if}
        {#if app.goals.priority === "aero"}<button class="btn" onclick={() => (app.goals.priority = "value")}>Don't require aero data</button>{/if}
        <button class="btn" onclick={() => (app.goals.ride = "any")}>Show all styles</button>
      </div>
    </div>
  {:else}
    <div class="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {#each result.picks.slice(0, 4) as pick (pick.item.helmet.id)}
        <PickCard item={pick.item} {result} {labLabel} />
      {/each}
    </div>

    <div class="mt-8 flex items-baseline justify-between gap-3">
      <h2 class="label">Full ranking</h2>
      <button class="text-xs text-ink-3 underline hover:text-ink" onclick={() => (app.view = "charts")}>See these helmets on a chart</button>
    </div>
    <ol class="card mt-2 divide-y divide-line overflow-hidden">
      {#each result.ranked.slice(0, shown) as item (item.helmet.id)}
        <ResultRow {item} {labLabel} />
      {/each}
    </ol>
    {#if shown < result.ranked.length}
      <div class="mt-4 text-center">
        <button class="btn" onclick={() => (shown += PAGE * 2)}>
          Show more ({result.ranked.length - shown} left)
        </button>
      </div>
    {/if}

    {#if result.aeroOnly.length}
      <h2 class="label mt-8">Fast, but no crash test yet</h2>
      <p class="mt-1 text-xs text-ink-3">Wind-tunnel results only. No lab has crash-tested these, so they can't be ranked for safety.</p>
      <ul class="card mt-2 divide-y divide-line overflow-hidden">
        {#each result.aeroOnly as h (h.id)}
          <li>
            <button class="flex min-h-11 w-full items-center justify-between gap-3 px-4 py-2 text-left hover:bg-surface-2" onclick={() => (app.selected = h.id)}>
              <span class="min-w-0 truncate font-medium">{h.brand} {h.model}</span>
              <span class="shrink-0 text-xs text-ink-3 num">
                aero {h.aero?.score ?? "–"}/100{h.aero?.watts_saved != null ? ` · ${h.aero.watts_saved > 0 ? "saves" : "costs"} ${Math.abs(h.aero.watts_saved).toFixed(1)} W` : ""}
              </span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}

    {#if result.excluded.length}
      <p class="mt-6 text-xs text-ink-3">
        Filtered out: {result.excluded.map((e) => `${e.count} ${e.reason}`).join(" · ")}
      </p>
    {/if}
  {/if}
</section>
