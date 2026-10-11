<script lang="ts">
  import type { Helmet } from "../lib/types";

  let { helmet, class: klass = "" }: { helmet: Helmet; class?: string } = $props();
  let failed = $state(false);
</script>

<div class="flex items-center justify-center overflow-hidden rounded-xl bg-white {klass}">
  {#if helmet.image_url && !failed}
    <img
      src={helmet.image_url}
      alt=""
      loading="lazy"
      decoding="async"
      class="size-full object-contain p-1"
      onerror={() => (failed = true)}
    />
  {:else}
    <svg viewBox="0 0 32 32" class="w-1/2 opacity-25" aria-hidden="true">
      <path d="M4 20a12 12 0 0 1 24 0v2H4z" fill="#555" />
    </svg>
  {/if}
</div>
