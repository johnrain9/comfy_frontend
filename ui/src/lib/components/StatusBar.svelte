<script lang="ts">
  import { api } from '$lib/api';
  import { health, healthError, refreshHealth } from '$lib/stores/health';
  import { refreshJobs } from '$lib/stores/jobs';
  import { refreshWorkflows } from '$lib/stores/workflows';
  let actionMsg = '';
  let actionBusy = false;

  async function doPause(): Promise<void> {
    if (actionBusy) return;
    actionBusy = true;
    actionMsg = '';
    try {
      await api.pause({ timeoutMs: 12000 });
      await refreshHealth();
      actionMsg = 'Worker paused.';
    } catch (e) {
      actionMsg = e instanceof Error ? e.message : String(e);
    } finally {
      actionBusy = false;
    }
  }
  async function doResume(): Promise<void> {
    if (actionBusy) return;
    actionBusy = true;
    actionMsg = '';
    try {
      await api.resume({ timeoutMs: 12000 });
      await refreshHealth();
      actionMsg = 'Worker resumed.';
    } catch (e) {
      actionMsg = e instanceof Error ? e.message : String(e);
    } finally {
      actionBusy = false;
    }
  }
  async function doReloadWf(): Promise<void> {
    if (actionBusy) return;
    actionBusy = true;
    actionMsg = '';
    try {
      await api.reloadWorkflows({ timeoutMs: 20000 });
      await refreshWorkflows();
      await refreshJobs();
      actionMsg = 'Workflows reloaded.';
    } catch (e) {
      actionMsg = e instanceof Error ? e.message : String(e);
    } finally {
      actionBusy = false;
    }
  }
  async function doReloadLoras(): Promise<void> {
    if (actionBusy) return;
    actionBusy = true;
    actionMsg = '';
    try {
      await api.reloadLoras({ timeoutMs: 20000 });
      actionMsg = 'LoRAs reloaded.';
    } catch (e) {
      actionMsg = e instanceof Error ? e.message : String(e);
    } finally {
      actionBusy = false;
    }
  }
</script>

<section class="panel p-3" id="health" aria-live="polite">
  <div class="rail">
    <div class="snapshot">
      <p class="eyebrow">System</p>
      {#if $health}
        <div class="stats">
          <div class="stat">
            <span>Comfy</span>
            <strong class:up={$health.comfy} class:down={!$health.comfy}>{$health.comfy ? 'Online' : 'Offline'}</strong>
          </div>
          <div class="stat">
            <span>Worker</span>
            <strong>{$health.worker}</strong>
          </div>
          <div class="stat">
            <span>Pending</span>
            <strong>{$health.pending}</strong>
          </div>
          <div class="stat">
            <span>Running</span>
            <strong>{$health.running}</strong>
          </div>
        </div>
      {:else if $healthError}
        <div class="error">Health error: {$healthError}</div>
      {:else}
        <div class="loading">Loading health...</div>
      {/if}
    </div>

    <div class="action-cluster">
      <button id="pauseBtn" class="btn" on:click={doPause} disabled={actionBusy}>Pause</button>
      <button id="resumeBtn" class="btn" on:click={doResume} disabled={actionBusy}>Resume</button>
      <button id="reloadWfBtn" class="btn" on:click={doReloadWf} disabled={actionBusy}>Reload Workflows</button>
      <button id="reloadLoraBtn" class="btn" on:click={doReloadLoras} disabled={actionBusy}>Reload LoRAs</button>
      {#if actionMsg}
        <span class="msg">{actionMsg}</span>
      {/if}
    </div>
  </div>
</section>

<style>
  #health {
    padding: 1rem 1.2rem;
  }
  .rail {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: end;
  }
  .snapshot {
    display: grid;
    gap: 0.7rem;
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(4, minmax(110px, 1fr));
    gap: 0.7rem;
  }
  .stat {
    display: grid;
    gap: 0.3rem;
    padding: 0.8rem 0.9rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--color-line);
    background: var(--color-bg-panel-soft);
  }
  .stat span {
    color: var(--color-text-muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .stat strong {
    font-size: 1rem;
    font-weight: 600;
    letter-spacing: -0.03em;
  }
  .up {
    color: var(--color-succeeded);
  }
  .down,
  .error {
    color: var(--color-failed);
  }
  .loading {
    color: var(--color-text-secondary);
  }
  .action-cluster {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.65rem;
    align-items: center;
  }
  .btn {
    padding: 0.65rem 0.95rem;
    border-radius: var(--radius-full);
    background: rgba(255, 255, 255, 0.04);
  }
  .msg {
    color: var(--color-text-secondary);
    font-size: 0.82rem;
  }

  @media (max-width: 1100px) {
    .rail {
      grid-template-columns: 1fr;
    }
    .action-cluster {
      justify-content: flex-start;
    }
  }

  @media (max-width: 760px) {
    .stats {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
