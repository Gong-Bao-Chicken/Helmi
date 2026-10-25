<script lang="ts">
  import { app, MAX_COMPARE, toggleCompare } from "../lib/state.svelte";
  import type { Helmet } from "../lib/types";
  import HelmetImage from "./HelmetImage.svelte";

  let { helmetsById }: { helmetsById: Map<string, Helmet> } = $props();
  const items = $derived(app.compare.map((id) => helmetsById.get(id)).filter((h): h is Helmet => !!h));
</script>

{#if items.length}
  <div class="fixed inset-x-0 bottom-16 z-30 px-4 pb-2 sm:bottom-0 sm:pb-4">
    <div class="card mx-auto flex max-w-3xl items-center gap-3 p-2.5 pl-4 shadow-xl">
      <span class="label hidden sm:block">Compare</span>
      <ul class="flex min-w-0 flex-1 gap-2">
        {#each items as h (h.id)}
          <li class="group relative">
            <button onclick={() => (app.selected = h.id)} title="{h.brand} {h.model}">
              <HelmetImage helmet={h} class="size-11 border border-line" />
            </button>
            <button
              class="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full bg-ink text-[10px] text-bg sm:hidden sm:group-hover:flex sm:group-focus-within:flex"
              aria-label="Remove {h.model}"
              onclick={() => toggleCompare(h.id)}>✕</button
            >
          </li>
        {/each}
        {#each Array(MAX_COMPARE - items.length) as _, i (i)}
          <li class="size-11 rounded-xl border border-dashed border-line" aria-hidden="true"></li>
        {/each}
      </ul>
      <button class="btn" onclick={() => (app.compare = [])}>Clear</button>
      <button class="btn btn-primary" disabled={items.length < 2} onclick={() => (app.compareOpen = true)}>
        Compare {items.length}
      </button>
    </div>
  </div>
{/if}
