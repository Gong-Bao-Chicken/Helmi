<script lang="ts">
  /** Methodology, independence and how to cite: what a careful buyer, a club or a reviewer needs to trust a score. */
  import { relativeDate } from "../lib/format";
  import { LAB_EXPLAINERS, REPO_URL, reportUrl } from "../lib/site";
  import type { Dataset } from "../lib/types";

  let { dataset }: { dataset: Dataset } = $props();

  const labs = $derived(dataset.filters.rating_sources.filter((s) => s.key !== "hiper"));
  const rates = $derived(dataset.meta.exchange_rates);
  const counts = $derived.by(() => {
    const byLabs = [0, 0, 0, 0, 0];
    for (const h of dataset.helmets) {
      const n = labs.filter((l) => h.ratings[l.key]?.rank_pct != null).length;
      byLabs[n] = (byLabs[n] ?? 0) + 1;
    }
    return byLabs;
  });
  const dataDate = $derived(relativeDate(dataset.meta.generated_at));
  const citation = $derived(`Helmi – independent bicycle helmet ratings, data of ${dataDate}. ${location.origin}${location.pathname}`);
</script>

<article class="prose-helmi mx-auto max-w-3xl py-10">
  <h1 class="text-3xl font-semibold tracking-tight">How Helmi works</h1>
  <p class="mt-3 text-lg text-ink-2">
    Helmi ranks bicycle helmets by independent crash tests, not by marketing, stickers or reviews. It is a non-commercial project: no ads,
    no affiliate links, no tracking, and no manufacturer or shop has any say in the results.
  </p>

  <h2>The safety score</h2>
  <p>
    Four labs crash-test bicycle helmets and publish their results. Each tests different helmets in a different way, so Helmi first turns
    each lab's result into a <strong>percentile</strong>: a score of 80 means the helmet did better than 80% of the helmets that lab
    tested. Where several labs tested the same helmet, their percentiles are averaged, weighted by how rigorous each lab's test is.
  </p>
  <div class="card mt-4 divide-y divide-line text-sm">
    {#each labs as lab (lab.key)}
      <div class="flex items-start justify-between gap-4 p-3">
        <div>
          <p class="font-medium">{lab.label}</p>
          <p class="text-xs text-ink-3">{LAB_EXPLAINERS[lab.key] ?? ""}</p>
        </div>
        <span class="shrink-0 text-xs text-ink-3 num">weight {lab.confidence.toFixed(2)}</span>
      </div>
    {/each}
  </div>
  <p>
    Next to every score Helmi says how much backs it: <em>1 lab</em>, <em>labs agree</em> or <em>labs disagree</em> (their percentiles are
    more than 30 points apart). Tap the score to see the calculation. Of {dataset.helmets.length} helmets, {counts[1]} were tested by one lab,
    {counts[2]} by two and {(counts[3] ?? 0) + (counts[4] ?? 0)} by three or more.
  </p>

  <h2>What the score can't tell you</h2>
  <ul>
    <li>A percentile compares helmets <em>within</em> a lab's test. Labs choose which helmets to test, so a score from one lab is less certain than one confirmed by two.</li>
    <li>
      NSW Helmet STAR scores out of 100 and caps a helmet at 29 for a design fault, such as a buckle part that can come off or a helmet
      that shifts on the head. Helmi uses NSW's capped total and shows the reason next to it.
    </li>
    <li>The labs test the helmet shell. None of them crash-tests the chin bar of a full-face helmet.</li>
    <li>Kids' helmets score lower as a group, so Helmi also ranks each one among kids' helmets only.</li>
    <li>A model on sale today may be a newer version than the one tested. Check the test year.</li>
    <li>Fit matters as much as the score. A helmet that doesn't fit well can't protect you as tested.</li>
  </ul>

  <h2>Prices</h2>
  <p>
    Prices come from comparison sites and shops in each country: Geizhals and Idealo for Germany and Austria, toppreise.ch for
    Switzerland, and Amazon. Each country only shows prices from its own shops. Helmi uses the median price of the last 14 days (30 days
    when there are too few prices), so one-day spikes don't count. Offers that don't fit (a helmet light at €30, a different model) are filtered
    out.
  </p>
  <p>
    When a country has no shop price, Helmi shows a neighbouring country's price or the US price at test time, marked with “≈”.
    Conversions use the European Central Bank's reference rates{#if rates?.date}, currently from {relativeDate(rates.date)}{/if}.
    Prices and lab results are updated every week.
  </p>

  <h2>Riding styles</h2>
  <p>
    Styles come from Virginia Tech's own category, from a check of each model by hand, or from words in the model name. Helmets none of
    these can place are listed as Unclassified rather than guessed.
  </p>

  <h2>Choosing a helmet: five rules</h2>
  <ol>
    <li><strong>Trust lab tests, not stickers.</strong> Rotational systems like MIPS help on average, but a well-tested helmet without one can beat a poor one with it.</li>
    <li><strong>A cheaper helmet can be safer.</strong> Price and protection are only loosely related; look for the sweet spot.</li>
    <li><strong>Fit first.</strong> Try it on: it should sit level, not rock, and the straps should form a V under each ear.</li>
    <li><strong>Replace it after any crash,</strong> even without visible damage, and when it reaches the manufacturer's recommended age, often 3–5 years.</li>
    <li><strong>Match it to your bike.</strong> A 45 km/h S-pedelec needs a helmet approved for it; a normal pedelec or bicycle doesn't.</li>
  </ol>

  <h2>Data, citation and corrections</h2>
  <p>
    The data is from {dataDate}. All of it is in one public file:
    <a href="data/helmets.json">helmets.json</a>. The code is on <a href={REPO_URL} target="_blank" rel="noopener">GitHub</a>.
  </p>
  <p class="card p-3 text-sm">To cite: {citation}</p>
  <p>
    Found a wrong match, price or style? <a href={reportUrl(dataset)} target="_blank" rel="noopener">Report it on GitHub</a>, or use the
    link on any helmet's page.
  </p>
</article>
