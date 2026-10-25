<script lang="ts">
  /** Plain-language context for riding styles where the rules or the evidence need explaining. */
  import type { RideKey } from "../lib/finder";

  let { ride }: { ride: RideKey | null } = $props();
</script>

{#if ride === "speed" || ride === "city"}
  <aside class="card mt-4 p-4 text-sm text-ink-2">
    <p class="font-medium text-ink">Which e-bike do you have?</p>
    <ul class="mt-1.5 space-y-1">
      <li>
        <span class="font-medium text-ink">Pedelec</span> (motor helps up to 25 km/h): legally a bicycle in Germany, Austria and Switzerland;
        any bicycle helmet (EN 1078) will do.
      </li>
      <li>
        <span class="font-medium text-ink">S-pedelec</span> (up to 45 km/h, number plate): a moped by law, so a helmet is required. Germany
        and Austria ask for a moped helmet (ECE 22.05/22.06); Switzerland and the Netherlands also accept NTA 8776, the standard made for
        fast e-bikes. Choose <span class="font-medium text-ink">Speed pedelec</span> to see NTA 8776 helmets.
      </li>
    </ul>
    <p class="mt-1.5 text-xs text-ink-3">Rules change; check your country's current traffic regulations before you buy.</p>
  </aside>
{:else if ride === "kids"}
  <aside class="card mt-4 p-4 text-sm text-ink-2">
    <p class="font-medium text-ink">About kids' helmets</p>
    <p class="mt-1">
      Kids' helmets are usually tested by one lab, often CERTIMOOV, and score lower as a group than adult helmets. Each one also shows how it
      ranks among kids' helmets only. Fit matters as much as the score: measure your child's head and check the size range before you buy.
    </p>
  </aside>
{:else if ride === "gravity"}
  <aside class="card mt-4 p-4 text-sm text-ink-2">
    <p class="font-medium text-ink">What the lab scores cover</p>
    <p class="mt-1">
      The labs test the helmet shell; none of them crash-tests the chin bar. For downhill, also look for ASTM F1952, the downhill
      helmet standard, which tests chin bars.
    </p>
  </aside>
{/if}
