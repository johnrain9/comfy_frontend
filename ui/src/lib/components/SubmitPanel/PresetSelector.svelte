<script lang="ts">
  export let label = 'Preset';
  export let id = 'presetSelect';
  export let options: string[] = [];
  export let value = '';
</script>

<label for={id}>{label}</label>
<select {id} bind:value>
  <option value="">(none)</option>
  {#each options as o}
    <option value={o}>{o}</option>
  {/each}
</select>
