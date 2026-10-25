<script lang="ts">
  import { relativeDate } from "../lib/format";
  import { REPO_URL, reportUrl } from "../lib/site";
  import { app } from "../lib/state.svelte";
  import type { Dataset } from "../lib/types";

  let { dataset }: { dataset: Dataset | null } = $props();
</script>

<footer class="mx-auto mt-16 max-w-[96rem] border-t border-line px-4 py-6 text-xs text-ink-3 sm:px-6">
  <p class="font-medium text-ink-2">Independent · no affiliate links · no ads · no tracking</p>
  <p class="mt-1 flex flex-wrap gap-x-4 gap-y-1">
    {#if dataset}<span>Data from {relativeDate(dataset.meta.generated_at)}, updated weekly</span>{/if}
    <button class="underline hover:text-ink" onclick={() => (app.view = "about")}>How it works</button>
    {#if dataset}<a class="underline hover:text-ink" href={reportUrl(dataset)} target="_blank" rel="noopener">Report a problem</a>{/if}
    <a class="underline hover:text-ink" href={REPO_URL} target="_blank" rel="noopener">Source code</a>
    <a class="underline hover:text-ink" href="data/helmets.json">Data (JSON)</a>
  </p>
</footer>
