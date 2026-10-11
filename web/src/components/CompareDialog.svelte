<script lang="ts">
  import { labsFor, priceFor, safetyFor, type FinderResult } from "../lib/finder";
  import { makeLabLabel, pct, priceLabel, priceSourceLabel } from "../lib/format";
  import { PICK_META } from "../lib/picks";
  import { app, toggleCompare } from "../lib/state.svelte";
  import type { Dataset, Helmet } from "../lib/types";
  import HelmetImage from "./HelmetImage.svelte";
  import SafetyMeter from "./SafetyMeter.svelte";

  let {
    dataset,
    result,
    fx,
    helmetsById,
  }: { dataset: Dataset; result: FinderResult; fx: Record<string, number>; helmetsById: Map<string, Helmet> } = $props();

  const labLabel = $derived(makeLabLabel(dataset));
  const items = $derived(app.compare.map((id) => helmetsById.get(id)).filter((h): h is Helmet => !!h));
  const rows = $derived(
    items.map((h) => {
      const safety = safetyFor(h, app.goals.safetySource) ?? safetyFor(h, "fused");
      const price = priceFor(h, app.goals.market, fx);
      return { h, safety, price, ranked: result.ranked.find((r) => r.helmet.id === h.id) };
    }),
  );
  const bestSafety = $derived(Math.max(...rows.map((r) => r.safety ?? 0)));
  const bestPrice = $derived(Math.min(...rows.map((r) => r.price?.amount ?? Infinity)));

  let dialog = $state<HTMLElement>();
  $effect(() => dialog?.focus());
  const close = () => (app.compareOpen = false);
  $effect(() => {
    if (items.length < 2) close();
  });
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && close()} />

<div class="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" onclick={close} aria-hidden="true"></div>
<div
  bind:this={dialog}
  role="dialog"
  aria-modal="true"
  aria-label="Compare helmets"
  tabindex="-1"
  class="fixed inset-x-2 top-[5vh] z-50 mx-auto max-h-[90vh] max-w-5xl overflow-auto rounded-2xl border border-line bg-bg shadow-2xl outline-none"
>
  <div class="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-bg/90 px-5 py-3 backdrop-blur">
    <h2 class="font-semibold">Compare {items.length} helmets</h2>
    <button class="btn size-8 p-0" onclick={close} aria-label="Close">✕</button>
  </div>
  <table class="w-full min-w-[40rem] text-sm">
    <thead>
      <tr>
        <th class="w-36"></th>
        {#each rows as { h } (h.id)}
          <th class="p-3 text-left align-top font-normal">
            <HelmetImage helmet={h} class="aspect-[4/3] w-full max-w-40" />
            <span class="mt-2 block text-xs text-ink-3">{h.brand}</span>
            <button class="block text-left font-semibold hover:underline" onclick={() => ((app.selected = h.id), close())}>{h.model}</button>
            <button class="mt-1 text-xs text-ink-3 hover:text-ink" onclick={() => toggleCompare(h.id)}>Remove</button>
          </th>
        {/each}
      </tr>
    </thead>
    <tbody class="divide-y divide-line [&_th]:p-3 [&_th]:text-left [&_th]:align-top [&_th]:text-xs [&_th]:font-semibold [&_th]:text-ink-3 [&_td]:p-3 [&_td]:align-top">
      <tr>
        <th>Safety score</th>
        {#each rows as r (r.h.id)}
          <td>
            {#if r.safety != null}
              <SafetyMeter value={r.safety} size="sm" />
              {#if r.safety === bestSafety}<span class="text-xs font-semibold text-good">Safest</span>{/if}
            {:else}–{/if}
          </td>
        {/each}
      </tr>
      <tr>
        <th>Price</th>
        {#each rows as r (r.h.id)}
          <td>
            <span class="font-semibold num">{priceLabel(r.price)}</span>
            {#if r.price?.amount === bestPrice}<span class="ml-1 text-xs font-semibold text-good">Cheapest</span>{/if}
            <span class="block text-xs text-ink-3">{priceSourceLabel(r.price)}</span>
          </td>
        {/each}
      </tr>
      <tr>
        <th>For your goals</th>
        {#each rows as r (r.h.id)}
          <td>
            {#if r.ranked}
              #{r.ranked.rank} of {result.ranked.length}
              {#each r.ranked.picks as k (k)}<span class="block text-xs font-semibold text-accent">{PICK_META[k].label}</span>{/each}
            {:else}<span class="text-ink-3">Filtered out</span>{/if}
          </td>
        {/each}
      </tr>
      <tr>
        <th>Labs</th>
        {#each rows as { h } (h.id)}
          <td>{labsFor(h).map(labLabel).join(", ") || "–"}</td>
        {/each}
      </tr>
      <tr>
        <th>Virginia Tech STAR</th>
        {#each rows as { h } (h.id)}
          <td class="num">{h.ratings.virginia_tech?.score?.toFixed(2) ?? "–"} <span class="text-xs text-ink-3">(lower is safer)</span></td>
        {/each}
      </tr>
      <tr>
        <th>Other labs</th>
        {#each rows as { h } (h.id)}
          <td class="space-y-0.5 text-xs">
            {#if h.ratings.folksam}<div>Folksam: {h.ratings.folksam.overall_result_pct ?? "–"}%{h.ratings.folksam.recommended ? " · recommended" : ""}</div>{/if}
            {#if h.ratings.certimoov}<div>CERTIMOOV: {h.ratings.certimoov.score ?? "–"}/5</div>{/if}
            {#if h.ratings.nsw_helmet_star}<div>NSW: {h.ratings.nsw_helmet_star.stars ?? "–"}★</div>{/if}
            {#if !h.ratings.folksam && !h.ratings.certimoov && !h.ratings.nsw_helmet_star}<span class="text-ink-3">–</span>{/if}
          </td>
        {/each}
      </tr>
      <tr>
        <th>Rotational system</th>
        {#each rows as { h } (h.id)}
          <td>{h.protection?.rotational_label ?? h.protection?.mips_label ?? "None detected"}</td>
        {/each}
      </tr>
      <tr>
        <th>Aero</th>
        {#each rows as { h } (h.id)}
          <td class="capitalize">{h.aero?.tier ? `${h.aero.tier} · ${h.aero.score}/100` : "Not tested"}</td>
        {/each}
      </tr>
      <tr>
        <th>Style · tested</th>
        {#each rows as { h } (h.id)}
          <td>{h.style} · {h.test_year ?? "–"}</td>
        {/each}
      </tr>
      <tr>
        <th>Safety percentile by lab</th>
        {#each rows as { h } (h.id)}
          <td class="text-xs num">{labsFor(h).map((k) => `${labLabel(k)} ${pct(h.ratings[k]?.rank_pct)}`).join(" · ") || "–"}</td>
        {/each}
      </tr>
    </tbody>
  </table>
</div>
