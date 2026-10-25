<script lang="ts">
  import { AERO_CLASSES, marketCurrency, priceFor, PRIORITIES, RIDES, type FinderResult, type SafetySource } from "../lib/finder";
  import { money } from "../lib/format";
  import { app } from "../lib/state.svelte";
  import type { Dataset } from "../lib/types";

  let { dataset, fx, result }: { dataset: Dataset; fx: Record<string, number>; result: FinderResult } = $props();

  const currency = $derived(marketCurrency(app.goals.market));
  // Slider ceiling: the priciest helmet in this market, rounded up to a clean step.
  const maxPrice = $derived.by(() => {
    let max = 0;
    for (const h of dataset.helmets) max = Math.max(max, priceFor(h, app.goals.market, fx)?.amount ?? 0);
    return Math.ceil(max / 50) * 50 || 500;
  });
  const sliderValue = $derived(app.goals.budget ?? maxPrice);

  // On small screens the panel collapses behind a summary bar so results come first.
  let open = $state(false);
  const summary = $derived(
    [
      RIDES.find((r) => r.key === app.goals.ride)?.label,
      PRIORITIES.find((p) => p.key === app.goals.priority)?.label,
      app.goals.budget ? `≤ ${money(app.goals.budget, currency)}` : null,
    ]
      .filter(Boolean)
      .join(" · "),
  );

  const sources: { key: SafetySource; label: string }[] = [
    { key: "fused", label: "All labs combined (recommended)" },
    { key: "virginia_tech", label: "Virginia Tech only" },
    { key: "folksam", label: "Folksam only" },
    { key: "certimoov", label: "CERTIMOOV only" },
    { key: "nsw_helmet_star", label: "NSW Helmet STAR only" },
  ];
</script>

<!-- Sticky on large screens, and scrollable on its own when it is taller than the window. -->
<aside class="lg:sticky lg:top-20 lg:max-h-[calc(100dvh-6rem)] lg:self-start lg:overflow-y-auto lg:overscroll-contain lg:rounded-2xl" aria-label="Your goals">
  <button
    class="card flex w-full items-center justify-between gap-3 px-4 py-3 text-left lg:hidden"
    aria-expanded={open}
    onclick={() => (open = !open)}
  >
    <span class="min-w-0">
      <span class="label block">Your goals</span>
      <span class="block truncate text-sm">{summary}</span>
    </span>
    <span class="btn shrink-0">{open ? "Done" : "Edit"}</span>
  </button>
  <div class="card mt-2 space-y-6 p-5 lg:mt-0 {open ? '' : 'max-lg:hidden'}">
    <fieldset>
      <legend class="label mb-2">Riding</legend>
      <div class="flex flex-wrap gap-1.5">
        {#each RIDES as ride (ride.key)}
          <button
            class="rounded-full border px-3 py-1 text-sm transition {app.goals.ride === ride.key
              ? 'border-accent bg-accent-soft font-medium text-ink'
              : 'border-line text-ink-2 hover:border-line-strong'}"
            aria-pressed={app.goals.ride === ride.key}
            onclick={() => (app.goals.ride = ride.key)}>{ride.label}</button
          >
        {/each}
      </div>
    </fieldset>

    <fieldset>
      <legend class="label mb-2">What matters most</legend>
      <div class="space-y-1.5">
        {#each PRIORITIES as p (p.key)}
          <label
            class="flex cursor-pointer gap-3 rounded-xl border p-2.5 transition {app.goals.priority === p.key
              ? 'border-accent bg-accent-soft'
              : 'border-line hover:border-line-strong'}"
          >
            <input type="radio" name="priority" value={p.key} bind:group={app.goals.priority} class="mt-1 accent-(--accent)" />
            <span>
              <span class="block text-sm font-medium">{p.label}</span>
              <span class="block text-xs text-ink-3">{p.blurb}</span>
            </span>
          </label>
        {/each}
      </div>
    </fieldset>

    <div>
      <div class="mb-2 flex items-baseline justify-between">
        <label for="budget" class="label">Budget</label>
        <span class="text-sm font-medium num">{app.goals.budget ? `up to ${money(app.goals.budget, currency)}` : "No limit"}</span>
      </div>
      <input
        id="budget"
        type="range"
        min="30"
        max={maxPrice}
        step="10"
        value={sliderValue}
        oninput={(e) => {
          const v = Number(e.currentTarget.value);
          app.goals.budget = v >= maxPrice ? null : v;
        }}
        class="w-full accent-(--accent)"
      />
    </div>

    <fieldset class="space-y-2.5">
      <legend class="label mb-2">Must have</legend>
      <label class="flex items-start gap-2.5 text-sm">
        <input type="checkbox" bind:checked={app.goals.rotational} class="mt-0.5 accent-(--accent)" />
        <span>Rotational protection <span class="block text-xs text-ink-3">MIPS, SPIN, WaveCel and similar</span></span>
      </label>
      <label class="flex items-start gap-2.5 text-sm">
        <input type="checkbox" bind:checked={app.goals.pricedOnly} class="mt-0.5 accent-(--accent)" disabled={app.goals.market === "us"} />
        <span>Currently in shops <span class="block text-xs text-ink-3">Has a live price in your market</span></span>
      </label>
      <label class="flex items-start gap-2.5 text-sm">
        <input type="checkbox" bind:checked={app.goals.euOnly} class="mt-0.5 accent-(--accent)" disabled={app.goals.market === "us"} />
        <span>Sold in Europe</span>
      </label>
      <label class="flex items-start gap-2.5 text-sm">
        <input type="checkbox" bind:checked={app.goals.multiLab} class="mt-0.5 accent-(--accent)" />
        <span>Tested by 2 or more labs <span class="block text-xs text-ink-3">Scores confirmed by an independent second test</span></span>
      </label>
    </fieldset>

    {#if app.goals.ride === "race" || app.goals.priority === "aero"}
      <fieldset>
        <legend class="label mb-2">Aero class</legend>
        <div class="flex flex-wrap gap-1.5">
          {#each [{ key: null, label: "Any" }, ...AERO_CLASSES] as c (c.key ?? "any")}
            <button
              class="rounded-full border px-3 py-1 text-sm transition {app.goals.aeroClass === c.key
                ? 'border-accent bg-accent-soft font-medium text-ink'
                : 'border-line text-ink-2 hover:border-line-strong'}"
              aria-pressed={app.goals.aeroClass === c.key}
              onclick={() => (app.goals.aeroClass = c.key)}>{c.label}</button
            >
          {/each}
        </div>
        <p class="mt-1.5 text-xs text-ink-3">From the wind-tunnel test; only wind-tunnel-tested helmets have a class.</p>
      </fieldset>
    {/if}

    <details class="group">
      <summary class="label cursor-pointer list-none">
        <span class="inline-block transition group-open:rotate-90">›</span> Advanced
      </summary>
      <label class="mt-3 block text-sm">
        <span class="mb-1 block text-ink-2">Safety rating source</span>
        <select bind:value={app.goals.safetySource} class="w-full rounded-xl border border-line bg-surface px-2 py-1.5">
          {#each sources as s (s.key)}
            <option value={s.key}>{s.label}</option>
          {/each}
        </select>
      </label>
      <p class="mt-2 text-xs text-ink-3">
        {result.ratedTotal} helmets have a rating from this source. Combining labs weighs each by how rigorous its protocol is.
      </p>
    </details>
  </div>
</aside>
