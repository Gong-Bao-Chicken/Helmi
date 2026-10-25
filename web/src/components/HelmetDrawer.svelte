<script lang="ts">
  import { explain, labsFor, PEER_WINDOW, priceFor, safetyFor, type FinderResult, type Reason } from "../lib/finder";
  import { makeLabLabel, money, pct, shopName } from "../lib/format";
  import { PICK_META } from "../lib/picks";
  import { styleLabel } from "../lib/styles";
  import { app, MAX_COMPARE, toggleCompare } from "../lib/state.svelte";
  import type { Dataset, Helmet, MarketKey } from "../lib/types";
  import LabAgreement from "./charts/LabAgreement.svelte";
  import PositionChart from "./charts/PositionChart.svelte";
  import StripPlot from "./charts/StripPlot.svelte";
  import HelmetImage from "./HelmetImage.svelte";
  import SafetyMeter from "./SafetyMeter.svelte";

  let { dataset, result, fx, helmet }: { dataset: Dataset; result: FinderResult; fx: Record<string, number>; helmet: Helmet } =
    $props();

  let panel = $state<HTMLElement>();
  const labLabel = $derived(makeLabLabel(dataset));
  const ranked = $derived(result.ranked.find((r) => r.helmet.id === helmet.id));
  const safety = $derived(safetyFor(helmet, app.goals.safetySource) ?? safetyFor(helmet, "fused"));
  const comparing = $derived(app.compare.includes(helmet.id));
  const r = $derived(helmet.ratings);
  const tech = $derived(helmet.protection?.rotational_label ?? helmet.protection?.mips_label);

  // Group reasons by the graphic that backs them; the position chart covers both the peer and frontier claims.
  const reasons = $derived(ranked ? explain(ranked, result, labLabel) : []);
  const byKind = (kinds: string[]) => reasons.filter((x) => x.evidence && kinds.includes(x.evidence.kind));
  const rankReasons = $derived(byKind(["rank"]));
  const positionReasons = $derived(byKind(["peers", "frontier"]));
  const labReasons = $derived(byKind(["labs"]));
  const aeroReasons = $derived(byKind(["aero"]));
  const otherReasons = $derived(reasons.filter((x) => !x.evidence));
  const peerEvidence = $derived(positionReasons.map((x) => x.evidence).find((e) => e?.kind === "peers"));

  const safetyItems = $derived(
    result.ranked.map((x) => ({ id: x.helmet.id, value: x.safety * 100, label: `${x.helmet.brand} ${x.helmet.model}` })),
  );
  const aeroItems = $derived(
    dataset.helmets
      .filter((h) => h.aero?.score != null)
      .map((h) => ({ id: h.id, value: h.aero!.score!, label: `${h.brand} ${h.model}` })),
  );

  const markets: { key: MarketKey; label: string }[] = [
    { key: "de", label: "Germany" },
    { key: "at", label: "Austria" },
    { key: "ch", label: "Switzerland" },
  ];

  function close() {
    app.selected = null;
  }

  $effect(() => {
    panel?.focus();
  });
</script>

{#snippet claims(list: Reason[])}
  <ul class="mb-3 space-y-1 text-sm">
    {#each list as reason (reason.text)}
      <li class="flex gap-2 {reason.tone === 'caution' ? 'text-caution' : reason.tone === 'good' ? 'text-ink' : 'text-ink-2'}">
        <span aria-hidden="true" class="w-3 shrink-0">{reason.tone === "caution" ? "!" : reason.tone === "good" ? "✓" : "·"}</span>
        {reason.text}
      </li>
    {/each}
  </ul>
{/snippet}

<svelte:window onkeydown={(e) => e.key === "Escape" && close()} />

<div class="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" onclick={close} aria-hidden="true"></div>
<div
  bind:this={panel}
  role="dialog"
  aria-modal="true"
  aria-labelledby="drawer-title"
  tabindex="-1"
  class="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col overflow-y-auto border-l border-line bg-bg shadow-2xl outline-none"
>
  <div class="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-bg/90 px-5 py-3 backdrop-blur">
    <span class="text-sm text-ink-3">{styleLabel(helmet.style)} · {helmet.test_year ? `tested ${helmet.test_year}` : "test year unknown"}</span>
    <button class="btn size-8 p-0" onclick={close} aria-label="Close">✕</button>
  </div>

  <div class="space-y-6 p-5">
    <div class="flex gap-4">
      <HelmetImage {helmet} class="size-32 shrink-0" />
      <div class="min-w-0">
        <p class="text-sm text-ink-3">{helmet.brand}</p>
        <h2 id="drawer-title" class="text-2xl leading-tight font-semibold tracking-tight">{helmet.model}</h2>
        {#if ranked?.picks.length}
          <div class="mt-2 flex flex-wrap gap-1">
            {#each ranked.picks as kind (kind)}
              <span class="rounded-full px-2 py-0.5 text-xs font-semibold {kind === 'best' ? 'bg-accent text-accent-ink' : 'bg-pick text-pick-ink'}">{PICK_META[kind].label}</span>
            {/each}
          </div>
        {/if}
        <div class="mt-3 flex flex-wrap gap-2">
          <button class="btn {comparing ? 'btn-primary' : ''}" disabled={!comparing && app.compare.length >= MAX_COMPARE} onclick={() => toggleCompare(helmet.id)}>
            {comparing ? "✓ In comparison" : "Add to compare"}
          </button>
        </div>
      </div>
    </div>

    {#if safety != null}
      <section class="card p-4">
        <div class="flex items-center justify-between">
          <h3 class="label">Safety score</h3>
          <SafetyMeter value={safety} />
        </div>
        {#if !ranked}
          <p class="mt-1 text-sm text-ink-2">Safer than {pct(safety)}% of lab-tested helmets.</p>
          <p class="mt-2 text-xs text-ink-3">Not on your current shortlist; your goals filter it out.</p>
        {/if}
      </section>
    {/if}

    <section>
      <h3 class="label mb-2">How it compares</h3>
      <div class="space-y-3">
        {#if ranked && rankReasons.length}
          <figure class="card p-4">
            {@render claims(rankReasons)}
            <StripPlot
              items={safetyItems}
              focusId={helmet.id}
              domain={[0, 100]}
              ends={["less safe", "safer"]}
              focusLabel="#{ranked.safetyRank} of {result.ranked.length}"
              ariaLabel="Safety of {helmet.model} among {result.ranked.length} matches"
            />
          </figure>
        {/if}
        {#if ranked?.price}
          <figure class="card p-4">
            {#if positionReasons.length}
              {@render claims(positionReasons)}
            {:else}
              <p class="mb-2 text-sm text-ink-2">Where it sits on price and safety among your matches.</p>
            {/if}
            <PositionChart
              {result}
              size="medium"
              focusId={helmet.id}
              peers={peerEvidence?.kind === "peers" ? { ids: peerEvidence.ids, medianPrice: peerEvidence.medianPrice, window: PEER_WINDOW } : null}
              ariaLabel="{helmet.model} by price and safety among your matches"
            />
            {#if peerEvidence?.kind === "peers"}
              <figcaption class="mt-2 text-xs text-ink-3">
                Shaded: the {peerEvidence.ids.length} helmets within {Math.round(PEER_WINDOW * 100)} safety points. The line is their median price.
              </figcaption>
            {/if}
          </figure>
        {/if}
        <figure class="card p-4">
          {#if labReasons.length}{@render claims(labReasons)}{/if}
          <LabAgreement {helmet} combined={safety} {labLabel} />
        </figure>
        {#if helmet.aero?.score != null && aeroItems.length > 1}
          <figure class="card p-4">
            {#if aeroReasons.length}{@render claims(aeroReasons)}{/if}
            <StripPlot
              items={aeroItems}
              focusId={helmet.id}
              domain={[0, 100]}
              ends={["draggy", "fast"]}
              focusLabel="aero {helmet.aero.score}"
              ariaLabel="Aero score of {helmet.model} among {aeroItems.length} wind-tunnel-tested helmets"
            />
            <figcaption class="mt-1 text-xs text-ink-3">Among all {aeroItems.length} wind-tunnel-tested helmets</figcaption>
          </figure>
        {/if}
        {#if otherReasons.length}
          <div class="px-1">{@render claims(otherReasons)}</div>
        {/if}
      </div>
    </section>

    <section>
      <h3 class="label mb-2">Lab results</h3>
      <div class="card divide-y divide-line text-sm">
        {#if r.virginia_tech}
          <div class="flex items-start justify-between gap-4 p-3">
            <div>
              <a class="font-medium hover:underline" href={r.virginia_tech.url ?? helmet.source?.url ?? "https://www.helmet.beam.vt.edu/"} target="_blank" rel="noopener">Virginia Tech STAR {r.virginia_tech.test_year ?? ""}</a>
              <p class="text-xs text-ink-3">Lower STAR score is safer. Low / high impact: {r.virginia_tech.score_low_impact?.toFixed(1) ?? "–"} / {r.virginia_tech.score_high_impact?.toFixed(1) ?? "–"}</p>
              {#if r.virginia_tech.result_url}
                <a class="text-xs text-accent hover:underline" href={r.virginia_tech.result_url} target="_blank" rel="noopener">This helmet's test result at Virginia Tech ↗</a>
              {/if}
            </div>
            <div class="text-right num">
              <div class="font-semibold">{r.virginia_tech.score?.toFixed(2) ?? "–"}</div>
              <div class="text-xs text-ink-3">{pct(r.virginia_tech.rank_pct)} pct</div>
            </div>
          </div>
        {/if}
        {#if r.folksam}
          <div class="flex items-start justify-between gap-4 p-3">
            <div>
              <a class="font-medium hover:underline" href={r.folksam.url ?? "#"} target="_blank" rel="noopener">Folksam {r.folksam.test_year ?? ""}</a>
              <p class="text-xs text-ink-3">{r.folksam.recommended ? "Recommended by Folksam" : "Overall result vs best in test"}</p>
            </div>
            <div class="text-right num">
              <div class="font-semibold">{r.folksam.overall_result_pct != null ? `${r.folksam.overall_result_pct}%` : "–"}</div>
              <div class="text-xs text-ink-3">{pct(r.folksam.rank_pct)} pct</div>
            </div>
          </div>
        {/if}
        {#if r.certimoov}
          <div class="flex items-start justify-between gap-4 p-3">
            <div>
              <a class="font-medium hover:underline" href={r.certimoov.url ?? "#"} target="_blank" rel="noopener">CERTIMOOV {r.certimoov.test_year ?? ""}</a>
              <p class="text-xs text-ink-3">Oblique and linear impacts, scored out of 5</p>
            </div>
            <div class="text-right num">
              <div class="font-semibold">{r.certimoov.score ?? "–"} <span class="text-xs font-normal text-ink-3">/ 5</span></div>
              <div class="text-xs text-ink-3">{pct(r.certimoov.rank_pct)} pct</div>
            </div>
          </div>
        {/if}
        {#if r.nsw_helmet_star}
          <div class="flex items-start justify-between gap-4 p-3">
            <div>
              <a class="font-medium hover:underline" href={r.nsw_helmet_star.url ?? "#"} target="_blank" rel="noopener">NSW Helmet STAR {r.nsw_helmet_star.test_year ?? ""}</a>
              <p class="text-xs text-ink-3">{r.nsw_helmet_star.category ?? "Australian government rating"}</p>
            </div>
            <div class="text-right num">
              <div class="font-semibold">{"★".repeat(r.nsw_helmet_star.stars ?? 0)}<span class="text-ink-3">{"★".repeat(5 - (r.nsw_helmet_star.stars ?? 0))}</span></div>
              <div class="text-xs text-ink-3">{pct(r.nsw_helmet_star.rank_pct)} pct</div>
            </div>
          </div>
        {/if}
        {#if !labsFor(helmet).length}
          <p class="p-3 text-ink-3">No lab results.</p>
        {/if}
      </div>
    </section>

    <section>
      <h3 class="label mb-2">Prices</h3>
      <div class="card divide-y divide-line text-sm">
        {#each markets as m (m.key)}
          {@const listing = helmet.listings[m.key]}
          {@const price = priceFor(helmet, m.key, fx)}
          <div class="flex items-center justify-between gap-4 p-3">
            <span>{m.label}</span>
            {#if listing?.price != null}
              <span class="text-right">
                <a class="font-semibold num hover:underline" href={listing.url ?? "#"} target="_blank" rel="noopener sponsored">{money(listing.price, listing.currency)}</a>
                <span class="block text-xs text-ink-3">{shopName(listing.source)}{listing.price_window === "14d_median" ? " · 14-day median" : ""}</span>
              </span>
            {:else}
              <span class="text-right text-ink-3">
                {price ? `≈ ${money(price.amount, price.currency)}` : "–"}
                <span class="block text-xs">no shop listing found</span>
              </span>
            {/if}
          </div>
        {/each}
        <div class="flex items-center justify-between gap-4 p-3">
          <span>US retail at test time</span>
          <span class="font-semibold num">{money(helmet.price_at_test_usd, "USD")}</span>
        </div>
      </div>
    </section>

    <section>
      <h3 class="label mb-2">Features</h3>
      <div class="flex flex-wrap gap-1.5">
        <span class="chip">{tech ? `Rotational: ${tech}` : "No rotational system detected"}</span>
        {#if helmet.features.nta8776}<span class="chip">NTA 8776 (speed pedelec)</span>{/if}
        {#if helmet.features.asia_fit}<span class="chip">Asian fit</span>{/if}
        {#if helmet.features.round_fit}<span class="chip">Round fit</span>{/if}
        {#if helmet.certifications}<span class="chip">{helmet.certifications}</span>{/if}
        {#if helmet.european_market}<span class="chip">Sold in Europe</span>{/if}
      </div>
    </section>

    {#if helmet.aero?.tier}
      <section>
        <h3 class="label mb-2">Aerodynamics</h3>
        <div class="card p-3 text-sm">
          <div class="flex justify-between"><span class="capitalize">{helmet.aero.tier}</span><span class="font-semibold num">{helmet.aero.score}/100</span></div>
          {#each Object.values(helmet.aero.sources) as src (src.source)}
            <p class="mt-1 text-xs text-ink-3">
              <a class="hover:underline" href={src.source_url} target="_blank" rel="noopener">Cyclingnews wind tunnel {src.test_year}</a>:
              {src.watts_saved != null ? `${src.watts_saved > 0 ? "saves" : "costs"} ${Math.abs(src.watts_saved).toFixed(1)} W` : ""}
              {src.baseline_helmet ? `vs ${src.baseline_helmet}` : ""} at {src.speed_kph ?? 40} km/h{src.match && src.match.test_name !== `${helmet.brand} ${helmet.model}` ? ` (tested as "${src.match.test_name}")` : ""}
            </p>
          {/each}
        </div>
      </section>
    {/if}

    {#if helmet.manufacturer?.website}
      <a class="text-sm text-ink-2 hover:underline" href={helmet.manufacturer.website} target="_blank" rel="noopener">Manufacturer website ↗</a>
    {/if}
  </div>
</div>
