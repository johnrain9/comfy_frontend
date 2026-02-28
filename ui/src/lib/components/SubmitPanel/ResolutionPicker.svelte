<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let id = 'resolutionSelect';
  export let value = '';
  export let presets: Array<{ id: string; label: string }> = [];
  export let disabled = false;

  const dispatch = createEventDispatcher<{ change: string }>();

  function changed(event: Event): void {
    const next = (event.target as HTMLSelectElement).value;
    value = next;
    dispatch('change', next);
  }
</script>

<select {id} bind:value disabled={disabled} on:change={changed}>
  {#if !presets.length}
    <option value="">(none)</option>
  {/if}
  {#each presets as p}
    <option value={p.id}>{p.label}</option>
  {/each}
</select>
