<script lang="ts">
  import { api } from '$lib/api';
  import { refreshJobs } from '$lib/stores/jobs';

  export let selectedIds: number[] = [];
  let message = '';
  let busy = false;

  async function cancelSelected(): Promise<void> {
    if (!selectedIds.length || busy) return;
    if (!confirm(`Cancel ${selectedIds.length} selected jobs?`)) return;
    busy = true;
    message = '';
    try {
      const results = await Promise.allSettled(selectedIds.map((id) => api.cancelJob(id)));
      const failed = results.filter((r) => r.status === 'rejected').length;
      message = failed > 0 ? `Canceled ${selectedIds.length - failed}, failed ${failed}.` : `Canceled ${selectedIds.length} job(s).`;
      await refreshJobs();
    } finally {
      busy = false;
    }
  }

  async function clearQueue(): Promise<void> {
    if (busy) return;
    if (!confirm('Clear entire queue?')) return;
    if (!confirm('Confirm clear queue now.')) return;
    busy = true;
    message = '';
    try {
      await api.clearQueue();
      await refreshJobs();
      message = 'Queue cleared.';
    } finally {
      busy = false;
    }
  }
</script>

<div class="row">
  <button id="cancelSelBtn" class="btn" on:click={cancelSelected} disabled={busy || !selectedIds.length}>Cancel Selected</button>
  <button id="clearQueueBtn" class="btn" on:click={clearQueue} disabled={busy}>Clear Queue</button>
  <span class="msg">{message}</span>
</div>

<style>
  .row { display: flex; gap: 8px; }
  .btn { background: #1a2a44; border: 1px solid #2f4a72; color: #e7efff; border-radius: 8px; padding: 6px 10px; }
  .btn:disabled { opacity: 0.5; cursor: default; }
  .msg { color: #9bb2d3; font-size: 12px; align-self: center; }
</style>
