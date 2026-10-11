<script lang="ts">
  import { RIDES, safetyFor, type Ride } from "../lib/finder";
  import { app } from "../lib/state.svelte";
  import type { Dataset } from "../lib/types";

  let { dataset }: { dataset: Dataset } = $props();

  function countFor(ride: Ride) {
    return dataset.helmets.filter(
      (h) =>
        safetyFor(h, "fused") != null &&
        (!ride.styles || ride.styles.includes(h.style)) &&
        (!ride.requireNta8776 || h.features.nta8776) &&
        (!app.goals.euOnly || app.goals.market === "us" || h.european_market),
    ).length;
  }

  function choose(ride: Ride) {
    app.goals.ride = ride.key;
    if (ride.suggestedPriority) app.goals.priority = ride.suggestedPriority;
    scrollTo({ top: 0 });
  }

  const labs = $derived(dataset.filters.rating_sources.filter((s) => s.key !== "hiper").map((s) => s.label));
</script>

<section class="mx-auto max-w-3xl pt-14 pb-10 text-center sm:pt-20">
  <h1 class="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">Find a helmet that actually protects you</h1>
  <p class="mx-auto mt-4 max-w-2xl text-lg text-pretty text-ink-2">
    {dataset.helmets.length} helmets with independent impact tests from {labs.slice(0, -1).join(", ")} and {labs.at(-1)},
    matched with current shop prices.
  </p>
</section>

<section aria-labelledby="ride-q" class="mx-auto max-w-4xl">
  <h2 id="ride-q" class="label mb-3 text-center">Step 1 · What do you ride?</h2>
  <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
    {#each RIDES as ride (ride.key)}
      <button
        class="card group flex flex-col items-start gap-1 p-4 text-left transition hover:-translate-y-0.5 hover:border-accent"
        onclick={() => choose(ride)}
      >
        <span class="font-semibold group-hover:text-accent">{ride.label}</span>
        <span class="text-sm text-ink-2">{ride.blurb}</span>
        <span class="mt-auto pt-2 text-xs text-ink-3 num">{countFor(ride)} helmets</span>
      </button>
    {/each}
  </div>
  <p class="mt-8 text-center text-sm text-ink-3">
    Safety scores are lab percentiles: a score of 90 means safer than 90% of tested helmets. All helmets sold in the EU
    pass the basic EN 1078 standard; these labs test much harder, including rotational impacts.
  </p>
</section>
