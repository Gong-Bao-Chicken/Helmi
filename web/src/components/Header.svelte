<script lang="ts">
  import type { MarketChoice } from "../lib/finder";
  import { relativeDate } from "../lib/format";
  import { app, currentTheme, setTheme } from "../lib/state.svelte";
  import type { Dataset } from "../lib/types";

  let { dataset }: { dataset: Dataset | null } = $props();
  let theme = $state(currentTheme());

  const markets: { key: MarketChoice; label: string }[] = [
    { key: "de", label: "Germany · EUR" },
    { key: "at", label: "Austria · EUR" },
    { key: "ch", label: "Switzerland · CHF" },
    { key: "us", label: "US · USD (test-time)" },
  ];

  function toggleTheme() {
    theme = theme === "dark" ? "light" : "dark";
    setTheme(theme);
  }
</script>

<header class="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur">
  <div class="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
    <button
      class="flex items-center gap-2 text-left"
      onclick={() => {
        app.view = "find";
        app.goals.ride = null;
      }}
    >
      <svg viewBox="0 0 32 32" class="size-7" aria-hidden="true">
        <path d="M4 20a12 12 0 0 1 24 0v2H4z" fill="var(--accent)" />
        <path d="M8 22h20l-2 4H8z" fill="var(--accent)" opacity=".55" />
      </svg>
      <span class="font-semibold tracking-tight">Helmet Compare</span>
    </button>

    <nav class="flex gap-1 rounded-xl bg-surface-2 p-1 text-sm" aria-label="Views">
      {#each [["find", "Find a helmet"], ["explore", "All helmets"]] as [key, label] (key)}
        <button
          class="rounded-lg px-3 py-1 font-medium transition {app.view === key
            ? 'bg-surface text-ink shadow-card'
            : 'text-ink-3 hover:text-ink'}"
          aria-current={app.view === key ? "page" : undefined}
          onclick={() => (app.view = key as typeof app.view)}>{label}</button
        >
      {/each}
    </nav>

    <div class="ml-auto flex items-center gap-3">
      {#if dataset}
        <span class="hidden text-xs text-ink-3 md:inline">
          Data from {relativeDate(dataset.meta.generated_at)}
        </span>
      {/if}
      <label class="sr-only" for="market">Market</label>
      <select
        id="market"
        bind:value={app.goals.market}
        class="rounded-xl border border-line bg-surface px-2 py-1.5 text-sm"
      >
        {#each markets as m (m.key)}
          <option value={m.key}>{m.label}</option>
        {/each}
      </select>
      <button class="btn size-9 p-0" onclick={toggleTheme} aria-label="Switch to {theme === 'dark' ? 'light' : 'dark'} mode">
        {#if theme === "dark"}
          <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2"
            ><circle cx="12" cy="12" r="4" /><path
              d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
            /></svg
          >
        {:else}
          <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2"
            ><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg
          >
        {/if}
      </button>
    </div>
  </div>
</header>
