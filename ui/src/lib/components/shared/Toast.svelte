<script lang="ts">
  export let text = '';
</script>

{#if text}
<div class="toast">{text}</div>
{/if}

<style>
  .toast { position: fixed; right: 16px; bottom: 16px; background: #1a2a44; border: 1px solid #2f4a72; border-radius: 8px; padding: 8px 10px; color: #e7efff; }
</style>
