<script lang="ts">
  /** Key for dots colored by riding style: only the styles present, in the fixed style order. */
  import { orderedStyles, styleColor } from "../../lib/styles";
  import type { Helmet } from "../../lib/types";

  let { helmets }: { helmets: Helmet[] } = $props();
  const styles = $derived(orderedStyles([...new Set(helmets.map((h) => h.style))]));
</script>

{#if styles.length > 1}
  <ul class="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-3" aria-label="Dot colors: riding style">
    {#each styles as s (s.key)}
      <li class="flex items-center gap-1">
        <svg class="size-2.5 shrink-0" aria-hidden="true"><circle cx="5" cy="5" r="5" fill={styleColor(s.key)} /></svg>{s.label}
      </li>
    {/each}
  </ul>
{/if}
