<script lang="ts">
  import '../app.css';
  import { onDestroy, onMount } from 'svelte';
  import StatusBar from '$lib/components/StatusBar.svelte';
  import QueuePanel from '$lib/components/Queue/QueuePanel.svelte';
  import SubmitPanel from '$lib/components/SubmitPanel/SubmitPanel.svelte';
  import { startHealthPolling, stopHealthPolling } from '$lib/stores/health';
  import { startJobsPolling, stopJobsPolling, refreshJobs } from '$lib/stores/jobs';
  import { refreshWorkflows, workflows } from '$lib/stores/workflows';
  import {
    createWorkspace,
    workspaceState,
    setActiveWorkspace,
    renameWorkspace,
    closeWorkspace,
  } from '$lib/stores/workspace';

  onMount(async () => {
    await refreshWorkflows();
    startHealthPolling();
    startJobsPolling();
  });

  onDestroy(() => {
    stopHealthPolling();
    stopJobsPolling();
  });

  function onRename(wsId: string, current: string): void {
    const next = window.prompt('Workspace name', current);
    if (next === null) return;
    renameWorkspace(wsId, next);
  }
</script>

<svelte:head>
  <title>Video Queue UI V2</title>
</svelte:head>

<main class="mx-auto grid max-w-6xl gap-3 p-4">
  <StatusBar />

  <section class="panel p-3" aria-label="Workspace Tabs">
    <div class="workspace-row">
      <div id="workspaceTabs" class="tabs" role="tablist" aria-label="Workspaces">
        {#each $workspaceState.workspaces as ws}
          <button
            role="tab"
            aria-selected={ws.id === $workspaceState.active_workspace_id}
            class:active={ws.id === $workspaceState.active_workspace_id}
            on:click={() => setActiveWorkspace(ws.id)}
          >
            {ws.name}
          </button>
        {/each}
      </div>
      <div class="controls">
        <button id="newWsBtn" on:click={() => createWorkspace()}>New</button>
        {#if $workspaceState.workspaces.length > 0}
          {#each $workspaceState.workspaces as ws}
            {#if ws.id === $workspaceState.active_workspace_id}
              <button id="renameWsBtn" on:click={() => onRename(ws.id, ws.name)}>Rename</button>
              <button id="closeWsBtn" disabled={$workspaceState.workspaces.length <= 1} on:click={() => closeWorkspace(ws.id)}>Close</button>
            {/if}
          {/each}
        {/if}
      </div>
    </div>
  </section>

  <SubmitPanel workflows={$workflows} onSubmitted={refreshJobs} />
  <QueuePanel />
</main>

<style>
  .workspace-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 10px;
    align-items: center;
  }
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .tabs button,
  .controls button {
    background: #111f34;
    border: 1px solid #2f4a72;
    color: #e7efff;
    border-radius: 8px;
    padding: 6px 10px;
    cursor: pointer;
  }
  .tabs button.active {
    background: #1b2f4d;
    border-color: #4f79b8;
  }
  .controls {
    display: flex;
    gap: 8px;
  }
  button:disabled {
    opacity: 0.55;
    cursor: default;
  }
</style>
