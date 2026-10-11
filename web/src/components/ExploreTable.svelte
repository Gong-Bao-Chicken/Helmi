<script lang="ts">
  import { labsFor, priceFor, safetyFor } from "../lib/finder";
  import { makeLabLabel, priceLabel } from "../lib/format";
  import { app, MAX_COMPARE, toggleCompare } from "../lib/state.svelte";
  import { orderedStyles, styleLabel } from "../lib/styles";
  import type { Dataset } from "../lib/types";
  import HelmetImage from "./HelmetImage.svelte";
  import SafetyMeter from "./SafetyMeter.svelte";

  let { dataset, fx }: { dataset: Dataset; fx: Record<string, number> } = $props();

  type SortKey = "name" | "safety" | "vt" | "price" | "year" | "aero";
  let query = $state("");
  let style = $state("");
  let sortKey = $state<SortKey>("safety");
  let sortDesc = $state(true);
  let shown = $state(50);
  const labLabel = $derived(makeLabLabel(dataset));

  const rows = $derived.by(() => {
    const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const list = dataset.helmets
      .filter((h) => !style || h.style === style)
      .filter((h) => terms.every((t) => h.search_text.includes(t)))
      .filter((h) => !app.goals.euOnly || app.goals.market === "us" || h.european_market)
      .map((h) => ({
        h,
        safety: safetyFor(h, app.goals.safetySource),
        price: priceFor(h, app.goals.market, fx),
      }));
    const value = (r: (typeof list)[number]): number | string | null => {
      switch (sortKey) {
        case "name":
          return `${r.h.brand} ${r.h.model}`.toLowerCase();
        case "safety":
          return r.safety;
        case "vt":
          // Lower STAR is safer; negate so "descending" still means safest first.
          return r.h.ratings.virginia_tech?.score != null ? -r.h.ratings.virginia_tech.score : null;
        case "price":
          return r.price?.amount ?? null;
        case "year":
          return r.h.test_year ? Number(r.h.test_year) : null;
        case "aero":
          return r.h.aero?.score ?? null;
      }
    };
    return list.sort((a, b) => {
      const va = value(a);
      const vb = value(b);
      if (va == null) return vb == null ? 0 : 1;
      if (vb == null) return -1;
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sortDesc ? -cmp : cmp;
    });
  });

  function sortBy(key: SortKey) {
    if (sortKey === key) sortDesc = !sortDesc;
    else {
      sortKey = key;
      sortDesc = key !== "name" && key !== "price";
    }
  }

  $effect(() => {
    void [query, style, sortKey, sortDesc];
    shown = 50;
  });
</script>

{#snippet th(key: SortKey, label: string, klass = "")}
  <th class="px-3 py-2 font-semibold {klass}" aria-sort={sortKey === key ? (sortDesc ? "descending" : "ascending") : "none"}>
    <button class="inline-flex items-center gap-1 hover:text-ink" onclick={() => sortBy(key)}>
      {label}<span class="w-2 text-[10px]">{sortKey === key ? (sortDesc ? "↓" : "↑") : ""}</span>
    </button>
  </th>
{/snippet}

<section class="mt-6" aria-labelledby="explore-title">
  <div class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 id="explore-title" class="text-2xl font-semibold tracking-tight">All helmets</h1>
      <p class="mt-1 text-sm text-ink-2">{rows.length} of {dataset.helmets.length} helmets. Click a row for full lab results and prices.</p>
    </div>
    <div class="flex flex-wrap gap-2">
      <input
        type="search"
        bind:value={query}
        placeholder="Search brand or model"
        aria-label="Search helmets"
        class="w-56 rounded-xl border border-line bg-surface px-3 py-1.5 text-sm"
      />
      <select bind:value={style} aria-label="Style" class="rounded-xl border border-line bg-surface px-2 py-1.5 text-sm">
        <option value="">All styles</option>
        {#each orderedStyles(dataset.filters.styles) as s (s.key)}<option value={s.key}>{s.label}</option>{/each}
      </select>
    </div>
  </div>

  <div class="card mt-4 overflow-x-auto">
    <table class="w-full min-w-[52rem] text-sm">
      <thead class="border-b border-line text-left text-xs text-ink-3">
        <tr>
          {@render th("name", "Helmet")}
          {@render th("safety", "Safety")}
          {@render th("vt", "VT STAR")}
          <th class="px-3 py-2 font-semibold">Labs</th>
          {@render th("price", "Price", "text-right")}
          <th class="px-3 py-2 font-semibold">Rotational</th>
          {@render th("aero", "Aero")}
          {@render th("year", "Tested")}
          <th class="px-3 py-2"><span class="sr-only">Compare</span></th>
        </tr>
      </thead>
      <tbody class="divide-y divide-line">
        {#each rows.slice(0, shown) as { h, safety, price } (h.id)}
          {@const comparing = app.compare.includes(h.id)}
          <tr class="cursor-pointer hover:bg-surface-2" onclick={() => (app.selected = h.id)}>
            <td class="px-3 py-2">
              <div class="flex items-center gap-3">
                <HelmetImage helmet={h} class="size-10 shrink-0" />
                <div class="min-w-0">
                  <div class="truncate font-medium">{h.brand} {h.model}</div>
                  <div class="text-xs text-ink-3">{styleLabel(h.style)}</div>
                </div>
              </div>
            </td>
            <td class="px-3 py-2">{#if safety != null}<SafetyMeter value={safety} size="sm" />{:else}<span class="text-ink-3">–</span>{/if}</td>
            <td class="px-3 py-2 num">{h.ratings.virginia_tech?.score?.toFixed(1) ?? "–"}</td>
            <td class="px-3 py-2 text-xs text-ink-2">{labsFor(h).map(labLabel).join(", ") || "–"}</td>
            <td class="px-3 py-2 text-right font-medium num">{priceLabel(price)}</td>
            <td class="px-3 py-2 text-xs text-ink-2">{h.protection?.rotational_label ?? h.protection?.mips_label ?? "–"}</td>
            <td class="px-3 py-2 text-xs capitalize">{h.aero?.tier ?? "–"}</td>
            <td class="px-3 py-2 text-ink-2 num">{h.test_year ?? "–"}</td>
            <td class="px-3 py-2" onclick={(e) => e.stopPropagation()}>
              <input
                type="checkbox"
                aria-label="Compare {h.model}"
                checked={comparing}
                disabled={!comparing && app.compare.length >= MAX_COMPARE}
                onchange={() => toggleCompare(h.id)}
                class="accent-(--accent)"
              />
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#if shown < rows.length}
    <div class="mt-4 text-center"><button class="btn" onclick={() => (shown += 100)}>Show more ({rows.length - shown} left)</button></div>
  {/if}
</section>
