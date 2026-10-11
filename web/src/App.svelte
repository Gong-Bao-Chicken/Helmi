<script lang="ts">
  import CompareDialog from "./components/CompareDialog.svelte";
  import CompareTray from "./components/CompareTray.svelte";
  import ExploreTable from "./components/ExploreTable.svelte";
  import GoalsPanel from "./components/GoalsPanel.svelte";
  import Header from "./components/Header.svelte";
  import HelmetDrawer from "./components/HelmetDrawer.svelte";
  import Results from "./components/Results.svelte";
  import Welcome from "./components/Welcome.svelte";
  import { loadDataset } from "./lib/data";
  import { deriveFxRates, findHelmets } from "./lib/finder";
  import { app, writeUrl } from "./lib/state.svelte";
  import type { Dataset } from "./lib/types";

  let dataset = $state<Dataset | null>(null);
  let error = $state<string | null>(null);

  loadDataset()
    .then((d) => (dataset = d))
    .catch((e: unknown) => (error = e instanceof Error ? e.message : String(e)));

  const fx = $derived(dataset ? deriveFxRates(dataset.helmets) : {});
  const result = $derived(dataset ? findHelmets(dataset, app.goals, fx) : null);
  const helmetsById = $derived(new Map(dataset?.helmets.map((h) => [h.id, h]) ?? []));

  $effect(() => {
    // Track every piece of URL state, then write it.
    JSON.stringify([app.goals, app.view, app.selected, app.compare]);
    writeUrl();
  });
</script>

<div class="min-h-dvh pb-28">
  <Header {dataset} />

  <main class="mx-auto max-w-[96rem] px-4 sm:px-6">
    {#if error}
      <div class="card mx-auto mt-16 max-w-lg p-6">
        <h2 class="text-lg font-semibold">Could not load helmet data</h2>
        <p class="mt-2 text-sm text-ink-2">{error}</p>
        <p class="mt-3 text-sm text-ink-2">
          Generate it with <code class="rounded bg-surface-2 px-1">uv run helmet-data update --quick</code> and reload.
        </p>
      </div>
    {:else if !dataset || !result}
      <div class="mt-24 text-center text-sm text-ink-3" aria-live="polite">Loading helmets…</div>
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
