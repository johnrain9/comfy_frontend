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
  <div class="flex flex-wrap items-center gap-2 text-sm">
    <div class="grow">
      {#if $health}
        Comfy: <strong class={$health.comfy ? 'text-emerald-300' : 'text-rose-300'}>{$health.comfy ? 'up' : 'down'}</strong>
        | Worker: <strong>{$health.worker}</strong>
        | Pending: {$health.pending}
        | Running: {$health.running}
      {:else if $healthError}
        Health error: {$healthError}
      {:else}
        Loading health...
      {/if}
    </div>
    <button id="pauseBtn" class="btn" on:click={doPause} disabled={actionBusy}>Pause</button>
    <button id="resumeBtn" class="btn" on:click={doResume} disabled={actionBusy}>Resume</button>
    <button id="reloadWfBtn" class="btn" on:click={doReloadWf} disabled={actionBusy}>Reload Workflows</button>
    <button id="reloadLoraBtn" class="btn" on:click={doReloadLoras} disabled={actionBusy}>Reload LoRAs</button>
    {#if actionMsg}
      <span class="msg">{actionMsg}</span>
    {/if}
  </div>
</section>

<style>
  .btn { background: #1a2a44; border: 1px solid #2f4a72; color: #e7efff; border-radius: 8px; padding: 6px 10px; }
  .btn:disabled { opacity: 0.5; cursor: default; }
  .msg { color: #9bb2d3; font-size: 12px; }
</style>
