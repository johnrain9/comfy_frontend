<script lang="ts">
  export let open = false;
  export let message = 'Confirm';
  export let onConfirm: () => void;
  export let onCancel: () => void;
</script>

{#if open}
<div class="backdrop">
  <div class="dialog">
    <p>{message}</p>
    <div class="row">
      <button on:click={onConfirm}>Confirm</button>
      <button on:click={onCancel}>Cancel</button>
    </div>
  </div>
</div>
{/if}

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: grid; place-items: center; }
  .dialog { background: #0d1728; border: 1px solid #22324d; border-radius: 10px; padding: 12px; width: 320px; }
  .row { display: flex; justify-content: flex-end; gap: 8px; }
</style>
