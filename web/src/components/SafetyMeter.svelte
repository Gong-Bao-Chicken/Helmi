<script lang="ts">
  let { value, size = "md" }: { value: number; size?: "sm" | "md" } = $props();
  const score = $derived(Math.round(value * 100));
</script>

<div class="flex items-center gap-2" title="Safer than {score}% of lab-tested helmets">
  <div class="relative overflow-hidden rounded-full bg-surface-2 {size === 'sm' ? 'h-1.5 w-16' : 'h-2 w-24'}">
    <div class="absolute inset-y-0 left-0 rounded-full bg-accent" style="width: {score}%"></div>
  </div>
  <span class="font-semibold num {size === 'sm' ? 'text-sm' : 'text-base'}">{score}</span>
</div>
