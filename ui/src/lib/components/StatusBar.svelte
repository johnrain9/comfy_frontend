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

<div class="status-strip" id="health" aria-live="polite">
  {#if $health}
    <div class="indicators">
      <div class="ind">
        <span class="dot" class:dot-up={$health.comfy} class:dot-down={!$health.comfy}></span>
        <span class="ind-label">Comfy</span>
        <strong class:up={$health.comfy} class:down={!$health.comfy}>{$health.comfy ? 'Online' : 'Offline'}</strong>
      </div>
      <div class="ind">
        <span class="ind-label">Worker</span>
        <strong>{$health.worker}</strong>
      </div>
      <div class="ind">
        <span class="ind-label">Pending</span>
        <strong class="num">{$health.pending}</strong>
      </div>
      <div class="ind">
        <span class="ind-label">Running</span>
        <strong class="num">{$health.running}</strong>
      </div>
    </div>
  {:else if $healthError}
    <span class="error">{$healthError}</span>
  {:else}
    <span class="loading">Connecting...</span>
  {/if}

  <div class="actions">
    <button id="pauseBtn" on:click={doPause} disabled={actionBusy}>Pause</button>
    <button id="resumeBtn" on:click={doResume} disabled={actionBusy}>Resume</button>
    <button id="reloadWfBtn" on:click={doReloadWf} disabled={actionBusy}>Reload WF</button>
    <button id="reloadLoraBtn" on:click={doReloadLoras} disabled={actionBusy}>Reload LoRAs</button>
    {#if actionMsg}
      <span class="msg">{actionMsg}</span>
    {/if}
  </div>
</div>

<style>
  .status-strip {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.5rem 1rem;
    background: var(--color-bg-panel);
    border: 1px solid var(--color-line);
    border-radius: var(--radius-md);
    font-size: 0.8rem;
  }

  .indicators {
    display: flex;
    align-items: center;
    gap: 1.2rem;
    flex-wrap: wrap;
  }

  .ind {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    white-space: nowrap;
  }

  .ind-label {
    color: var(--color-text-muted);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .ind strong {
    font-weight: 600;
    font-size: 0.82rem;
  }

  .num {
    color: var(--color-accent-strong);
  }

  .dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .dot-up {
    background: var(--color-succeeded);
  }
  .dot-down {
    background: var(--color-failed);
  }

  .up { color: var(--color-succeeded); }
  .down, .error { color: var(--color-failed); }
  .loading { color: var(--color-text-secondary); }

  .actions {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-left: auto;
    flex-wrap: wrap;
  }

  .actions button {
    padding: 0.35rem 0.65rem;
    border-radius: var(--radius-full);
    background: transparent;
    border: 1px solid var(--color-line);
    color: var(--color-text-muted);
    font-size: 0.72rem;
    cursor: pointer;
  }
  .actions button:hover:not(:disabled) {
    color: var(--color-text-secondary);
    border-color: var(--color-line-strong);
  }

  .msg {
    color: var(--color-text-secondary);
    font-size: 0.75rem;
  }

  @media (max-width: 900px) {
    .status-strip {
      flex-wrap: wrap;
    }
    .actions {
      margin-left: 0;
      width: 100%;
    }
  }
</style>
