<script lang="ts">
  import ChartsView from "./components/ChartsView.svelte";
  import CompareDialog from "./components/CompareDialog.svelte";
  import AboutView from "./components/AboutView.svelte";
  import CompareTray from "./components/CompareTray.svelte";
  import Footer from "./components/Footer.svelte";
  import ExploreTable from "./components/ExploreTable.svelte";
  import GoalsPanel from "./components/GoalsPanel.svelte";
  import Header from "./components/Header.svelte";
  import HelmetDrawer from "./components/HelmetDrawer.svelte";
  import Results from "./components/Results.svelte";
  import Welcome from "./components/Welcome.svelte";
  import { loadDataset } from "./lib/data";
  import { findHelmets, fxRates } from "./lib/finder";
  import { app, writeUrl } from "./lib/state.svelte";
  import type { Dataset } from "./lib/types";

  let dataset = $state<Dataset | null>(null);
  let error = $state<string | null>(null);

  loadDataset()
    .then((d) => (dataset = d))
    .catch((e: unknown) => (error = e instanceof Error ? e.message : String(e)));

  const fx = $derived(dataset ? fxRates(dataset) : {});
  const result = $derived(dataset ? findHelmets(dataset, app.goals, fx) : null);
  const helmetsById = $derived(new Map(dataset?.helmets.map((h) => [h.id, h]) ?? []));

  $effect(() => {
    // Track every piece of URL state, then write it.
    JSON.stringify([app.goals, app.view, app.selected, app.compare]);
    writeUrl();
  });
</script>

<a href="#main" class="sr-only z-50 rounded-xl bg-surface px-3 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2">Skip to content</a>
<div class="min-h-dvh pb-40 sm:pb-28">
  <Header {dataset} />

  <main id="main" tabindex="-1" class="mx-auto max-w-[96rem] px-4 outline-none sm:px-6">
    {#if error}
      <div class="card mx-auto mt-16 max-w-lg p-6">
        <h2 class="text-lg font-semibold">Could not load helmet data</h2>
        <p class="mt-2 text-sm text-ink-2">{error}</p>
        <p class="mt-3 text-sm text-ink-2">
          Generate it with <code class="rounded bg-surface-2 px-1">uv run helmet-data update --quick</code> and reload.
        </p>
      </div>
    {:else if !dataset || !result}
      <!-- Same shape as the first screen, so nothing jumps when the data arrives. -->
      <div class="mx-auto max-w-4xl animate-pulse pt-14 sm:pt-20" aria-busy="true">
        <span class="sr-only" aria-live="polite">Loading helmets…</span>
        <div class="mx-auto h-10 max-w-xl rounded-xl bg-surface-2"></div>
        <div class="mx-auto mt-4 h-5 max-w-lg rounded-lg bg-surface-2"></div>
        <div class="mt-12 grid grid-cols-2 gap-3 md:grid-cols-3">
          {#each Array(9) as _, i (i)}<div class="h-24 rounded-2xl bg-surface-2"></div>{/each}
        </div>
      </div>
    {:else if app.view === "about"}
      <AboutView {dataset} />
    {:else if app.view === "charts"}
      <ChartsView {dataset} {fx} />
    {:else if app.view === "explore"}
      <ExploreTable {dataset} {fx} />
    {:else if !app.goals.ride}
      <Welcome {dataset} />
    {:else}
      <div class="mt-6 grid gap-6 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <GoalsPanel {dataset} {fx} {result} />
        <Results {dataset} {result} />
      </div>
    {/if}
  </main>

  <Footer {dataset} />

  {#if dataset && result}
    <CompareTray {helmetsById} />
    {#if app.selected && helmetsById.get(app.selected)}
      <HelmetDrawer {dataset} {result} {fx} helmet={helmetsById.get(app.selected)!} />
    {/if}
    {#if app.compareOpen}
      <CompareDialog {dataset} {result} {fx} {helmetsById} />
    {/if}
  {/if}
</div>
