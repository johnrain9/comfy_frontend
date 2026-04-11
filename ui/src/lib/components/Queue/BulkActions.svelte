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
  <div class="summary">
    {#if selectedIds.length}
      <strong>{selectedIds.length}</strong> job(s) selected
    {:else}
      Bulk actions become available when jobs are selected.
    {/if}
  </div>
  <div class="actions">
    <button id="cancelSelBtn" class="btn primary" on:click={cancelSelected} disabled={busy || !selectedIds.length}>Cancel Selected</button>
    <button id="clearQueueBtn" class="btn" on:click={clearQueue} disabled={busy}>Clear Queue</button>
  </div>
  {#if message}
    <span class="msg">{message}</span>
  {/if}
</div>

<style>
  .row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.8rem;
    align-items: center;
    padding: 0.9rem 1rem;
    border: 1px solid var(--color-line-strong);
    border-radius: var(--radius-md);
    background: var(--color-bg-card);
    box-shadow: var(--shadow-soft);
  }
  .summary {
    color: var(--color-text-secondary);
    font-size: 0.88rem;
  }
  .summary strong {
    color: var(--color-text);
    font-size: 1rem;
    margin-right: 0.3rem;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    justify-content: flex-end;
  }
  .btn {
    padding: 0.62rem 0.95rem;
    border-radius: var(--radius-full);
    background: rgba(255, 255, 255, 0.04);
  }
  .primary {
    background: #2a2118;
    border-color: var(--color-accent);
    color: var(--color-accent-strong);
  }
  .msg {
    grid-column: 1 / -1;
    color: var(--color-text-muted);
    font-size: 0.78rem;
  }

  @media (max-width: 760px) {
    .row {
      grid-template-columns: 1fr;
    }
    .actions {
      justify-content: flex-start;
    }
  }
</style>
