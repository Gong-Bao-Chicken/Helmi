<script lang="ts">
  import { explain, labsFor, PEER_WINDOW, priceFor, safetyFor, type FinderResult, type Reason } from "../lib/finder";
  import { RACE_PRESETS, timeSaved } from "../lib/aero";
  import { makeLabLabel, money, pct, priceWindowLabel, shopName } from "../lib/format";
  import { certifications, LAB_EXPLAINERS, reportUrl } from "../lib/site";
  import { PICK_META } from "../lib/picks";
  import { focusTrap } from "../lib/focusTrap";
  import { styleLabel } from "../lib/styles";
  import { app, MAX_COMPARE, toggleCompare } from "../lib/state.svelte";
  import type { Dataset, Helmet, MarketKey, RatingSourceKey } from "../lib/types";
  import LabAgreement from "./charts/LabAgreement.svelte";
  import PositionChart from "./charts/PositionChart.svelte";
  import StripPlot from "./charts/StripPlot.svelte";
  import EvidenceChip from "./EvidenceChip.svelte";
  import HelmetImage from "./HelmetImage.svelte";

  let { dataset, result, fx, helmet }: { dataset: Dataset; result: FinderResult; fx: Record<string, number>; helmet: Helmet } =
    $props();

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

  const certs = $derived(certifications(helmet.certifications));
  /** How many helmets each lab's percentile is computed over. */
  const labCounts = $derived.by(() => {
    const counts: Partial<Record<RatingSourceKey, number>> = {};
    for (const h of dataset.helmets) for (const key of labsFor(h)) counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  });
  const CERT_HINTS: Record<string, string> = {
    "EN 1078": "European bicycle standard",
    CPSC: "US bicycle standard",
    "NTA 8776": "fast e-bikes",
    "ASTM F1952": "downhill, tests the chin bar",
    "ASTM F1447": "US bicycle standard",
  };
  // The newest wind-tunnel test with the numbers needed for a time estimate.
  const aeroSource = $derived(
    Object.values(helmet.aero?.sources ?? {})
      .filter((s) => s.drag_watts_40kph && s.watts_saved != null)
      .sort((a, b) => Number(b.test_year ?? 0) - Number(a.test_year ?? 0))[0],
  );
  let race = $state<(typeof RACE_PRESETS)[number]["key"]>("tt40");
  const preset = $derived(RACE_PRESETS.find((p) => p.key === race)!);

  /** The lab's own name for the helmet, when it differs from how it's listed here. */
  function testedAs(key: RatingSourceKey) {
    const name = (r[key] as { match?: { test_name: string | null } } | undefined)?.match?.test_name;
    return name && name.toLowerCase() !== `${helmet.brand} ${helmet.model}`.toLowerCase() ? name : null;
  }

  function close() {
    app.selected = null;
  }
</script>

{#snippet labFooter(key: RatingSourceKey, url: string | null | undefined, name: string)}
  {#if testedAs(key)}<p class="text-xs text-ink-3">Listed by the lab as “{testedAs(key)}”</p>{/if}
  {#if url}
    <a class="mt-0.5 inline-block text-xs text-accent hover:underline" href={url} target="_blank" rel="noopener">View this result at {name} ↗</a>
  {/if}
{/snippet}

{#snippet labScore(key: RatingSourceKey, value: string, unit: string)}
  <div class="shrink-0 text-right num">
    <div class="font-semibold">{value} {#if unit}<span class="text-xs font-normal text-ink-3">{unit}</span>{/if}</div>
    {#if r[key]?.rank_pct != null}
      <div class="text-xs text-ink-3">better than {pct(r[key]!.rank_pct)}%</div>
      <div class="text-[11px] text-ink-3">of {labCounts[key]} tested</div>
    {/if}
  </div>
{/snippet}

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
  use:focusTrap
  role="dialog"
  aria-modal="true"
  aria-labelledby="drawer-title"
  tabindex="-1"
  class="fixed inset-x-0 bottom-0 z-50 flex max-h-[92dvh] w-full flex-col overflow-y-auto rounded-t-2xl border-t border-line bg-bg shadow-2xl outline-none sm:inset-y-0 sm:right-0 sm:left-auto sm:max-h-none sm:max-w-xl sm:rounded-none sm:border-t-0 sm:border-l"
>
  <div class="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-bg/90 px-5 py-3 backdrop-blur">
    <span class="absolute top-1.5 left-1/2 h-1 w-10 -translate-x-1/2 rounded-full bg-line-strong sm:hidden" aria-hidden="true"></span>
    <span class="text-sm text-ink-3">{styleLabel(helmet.style)} · {helmet.test_year ? `tested ${helmet.test_year}` : "test year unknown"}</span>
    <button class="btn size-11 p-0 sm:size-8" onclick={close} aria-label="Close">✕</button>
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
        <div class="flex items-start justify-between">
          <h3 class="label">Safety score</h3>
          <EvidenceChip {helmet} {safety} source={app.goals.safetySource} {labLabel} size="md" />
        </div>
        {#if ranked?.groupSafety}
          <p class="mt-2 text-sm text-ink-2">
            Among kids' helmets: safer than {Math.round(ranked.groupSafety.pct * 100)}% of the {ranked.groupSafety.n} with a lab result.
          </p>
        {/if}
        {#if helmet.style === "Full-Face"}
          <p class="mt-2 text-xs text-ink-3">The labs test the shell; the chin bar is not crash-tested.</p>
        {/if}
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
              <p class="font-medium">Virginia Tech STAR {r.virginia_tech.test_year ?? ""}</p>
              <p class="text-xs text-ink-3">Lower STAR score is safer. Low / high impact: {r.virginia_tech.score_low_impact?.toFixed(1) ?? "–"} / {r.virginia_tech.score_high_impact?.toFixed(1) ?? "–"}</p>
              <p class="text-xs text-ink-3">{LAB_EXPLAINERS.virginia_tech}</p>
              {@render labFooter("virginia_tech", r.virginia_tech.result_url ?? r.virginia_tech.url, "Virginia Tech")}
            </div>
            {@render labScore("virginia_tech", r.virginia_tech.score?.toFixed(2) ?? "–", "")}
          </div>
        {/if}
        {#if r.folksam}
          <div class="flex items-start justify-between gap-4 p-3">
            <div>
              <p class="font-medium">Folksam {r.folksam.test_year ?? ""}</p>
              <p class="text-xs text-ink-3">{r.folksam.recommended ? "Recommended by Folksam" : "Overall result vs best in test"}</p>
              <p class="text-xs text-ink-3">{LAB_EXPLAINERS.folksam}</p>
              {@render labFooter("folksam", r.folksam.url, "Folksam")}
            </div>
            {@render labScore("folksam", r.folksam.overall_result_pct != null ? `${r.folksam.overall_result_pct}%` : "–", "")}
          </div>
        {/if}
        {#if r.certimoov}
          <div class="flex items-start justify-between gap-4 p-3">
            <div>
              <p class="font-medium">CERTIMOOV {r.certimoov.test_year ?? ""}</p>
              <p class="text-xs text-ink-3">{LAB_EXPLAINERS.certimoov}</p>
              {@render labFooter("certimoov", r.certimoov.url, "CERTIMOOV")}
            </div>
            {@render labScore("certimoov", String(r.certimoov.score ?? "–"), "/ 5")}
          </div>
        {/if}
        {#if r.nsw_helmet_star}
          {@const nsw = r.nsw_helmet_star}
          {@const partsTotal = nsw.metrics ? Object.values(nsw.metrics).reduce((sum, m) => sum + m.score, 0) : null}
          <div class="flex items-start justify-between gap-4 p-3">
            <div class="min-w-0">
              <p class="font-medium">NSW Helmet STAR {nsw.test_year ?? ""}</p>
              <p class="text-xs text-ink-3">{nsw.category ?? ""}{nsw.category ? " · " : ""}{"★".repeat(nsw.stars ?? 0)}<span class="opacity-40">{"★".repeat(5 - (nsw.stars ?? 0))}</span></p>
              <p class="text-xs text-ink-3">{LAB_EXPLAINERS.nsw_helmet_star}</p>
              {#if nsw.modifier}
                <p class="mt-1 text-xs text-caution">
                  Penalty: {nsw.modifier}{partsTotal != null && nsw.score != null && partsTotal - nsw.score > 1
                    ? ` Without it the parts add up to ${partsTotal.toFixed(1)}.`
                    : ""}
                </p>
              {/if}
              {#if nsw.metrics}
                <details class="mt-1 text-xs text-ink-3">
                  <summary class="cursor-pointer hover:text-ink">Score breakdown</summary>
                  <ul class="mt-1 space-y-0.5 num">
                    {#each Object.entries(nsw.metrics) as [name, m] (name)}
                      <li class="flex justify-between gap-3"><span>{name}</span><span>{m.score.toFixed(1)} / {m.max}</span></li>
                    {/each}
                  </ul>
                </details>
              {/if}
              {@render labFooter("nsw_helmet_star", nsw.url, "NSW Helmet STAR")}
            </div>
            {@render labScore("nsw_helmet_star", nsw.score != null ? nsw.score.toFixed(1) : "★".repeat(nsw.stars ?? 0), nsw.score != null ? "/ 100" : "")}
          </div>
        {/if}
        {#if !labsFor(helmet).length}
          <p class="p-3 text-ink-3">No lab results.</p>
        {/if}
      </div>
      {#if helmet.merged_from?.length}
        {@const otherNames = helmet.merged_from.map((m) => m.name).filter((name) => name !== helmet.model)}
        <p class="mt-2 px-1 text-xs text-ink-3">
          {otherNames.length
            ? `Also tested as ${otherNames.map((name) => `“${name}”`).join(", ")}; those results are included here.`
            : "Another lab listed this helmet separately; its results are included here."}
        </p>
      {/if}
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
                <a class="font-semibold num hover:underline" href={listing.url ?? "#"} target="_blank" rel="noopener">{money(listing.price, listing.currency)}</a>
                <span class="block text-xs text-ink-3">{[shopName(listing.source), priceWindowLabel(listing.price_window)].filter(Boolean).join(" · ")}</span>
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
        {#if helmet.features.nta8776 && !certs.includes("NTA 8776")}<span class="chip">NTA 8776 (speed pedelec)</span>{/if}
        {#if helmet.features.asia_fit}<span class="chip">Asian fit</span>{/if}
        {#if helmet.features.round_fit}<span class="chip">Round fit</span>{/if}
        {#if helmet.european_market}<span class="chip">Sold in Europe</span>{/if}
      </div>
      <h3 class="label mt-4 mb-2">Certifications</h3>
      {#if certs.length}
        <div class="flex flex-wrap gap-1.5">
          {#each certs as cert (cert)}
            <span class="chip" title={CERT_HINTS[cert] ?? ""}>{cert}{CERT_HINTS[cert] ? ` · ${CERT_HINTS[cert]}` : ""}</span>
          {/each}
        </div>
      {:else}
        <p class="text-sm text-ink-3">Not listed in the lab data. That doesn't mean uncertified; check the label inside the helmet.</p>
      {/if}
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
              {src.baseline_helmet ? `vs ${src.baseline_helmet}` : ""} at {src.speed_kph ?? 40} km/h{src.error_margin_w != null ? ` (test error ±${src.error_margin_w.toFixed(1)} W)` : ""}{src.match && src.match.test_name !== `${helmet.brand} ${helmet.model}` ? ` (tested as "${src.match.test_name}")` : ""}
            </p>
          {/each}
          {#if aeroSource?.drag_watts_40kph && aeroSource.watts_saved != null}
            {@const saved = timeSaved(aeroSource, preset.distanceKm, preset.speedKph)}
            <div class="mt-3 border-t border-line pt-3">
              <label class="flex items-center justify-between gap-2 text-xs text-ink-2">
                <span>Race time</span>
                <select bind:value={race} class="rounded-lg border border-line bg-surface px-2 py-1">
                  {#each RACE_PRESETS as p (p.key)}<option value={p.key}>{p.label} at {p.speedKph} km/h</option>{/each}
                </select>
              </label>
              {#if saved}
                <p class="mt-2 font-medium num">
                  {Math.abs(saved.seconds) < 1 ? "Under 1 s" : `${Math.round(Math.abs(saved.seconds))} s`}
                  {saved.seconds >= 0 ? "faster" : "slower"} than the {aeroSource.baseline_helmet ?? "test's reference helmet"}
                </p>
                <p class="text-xs text-ink-3">
                  {saved.withinError ? "Within the test's error margin, so it may be no faster at all." : "At the same power output."}
                </p>
              {/if}
            </div>
          {/if}
        </div>
      </section>
    {/if}

    <a class="block text-sm text-ink-2 hover:underline" href={reportUrl(dataset, helmet)} target="_blank" rel="noopener">
      Something wrong with this helmet's data? Report it ↗
    </a>

    {#if helmet.manufacturer?.website}
      <a class="text-sm text-ink-2 hover:underline" href={helmet.manufacturer.website} target="_blank" rel="noopener">Manufacturer website ↗</a>
    {/if}
  </div>
</div>
