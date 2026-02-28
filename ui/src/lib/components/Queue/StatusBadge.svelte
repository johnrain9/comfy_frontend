<script lang="ts">
  export let status = 'pending';
  const cls = (s: string): string => `s-${String(s || '').toLowerCase()}`;
</script>

<span class={`badge ${cls(status)}`}>{status}</span>

<style>
  .badge { border-radius: 999px; padding: 2px 8px; font-size: 12px; border: 1px solid #2a3e60; }
  .s-running { color: #ffd17a; }
  .s-failed { color: #ff9aa9; }
  .s-pending { color: #9dc8ff; }
  .s-succeeded { color: #89f0b4; }
  .s-canceled { color: #d8c48e; }
</style>
