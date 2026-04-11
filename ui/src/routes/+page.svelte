<script lang="ts">
  import '../app.css';
  import { onDestroy, onMount } from 'svelte';
  import StatusBar from '$lib/components/StatusBar.svelte';
  import QueuePanel from '$lib/components/Queue/QueuePanel.svelte';
  import SubmitPanel from '$lib/components/SubmitPanel/SubmitPanel.svelte';
  import { startHealthPolling, stopHealthPolling } from '$lib/stores/health';
  import { startJobsPolling, stopJobsPolling, refreshJobs, jobs } from '$lib/stores/jobs';
  import { refreshWorkflows, workflows } from '$lib/stores/workflows';
  import {
    createWorkspace,
    workspaceState,
    setActiveWorkspace,
    renameWorkspace,
    closeWorkspace,
  } from '$lib/stores/workspace';

  type ViewTab = 'compose' | 'queue';
  let view: ViewTab = 'compose';

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

  $: activeWorkspace =
    $workspaceState.workspaces.find((ws) => ws.id === $workspaceState.active_workspace_id) ??
    $workspaceState.workspaces[0] ??
    null;

  $: runningCount = $jobs.filter((j) => String(j.status).toLowerCase() === 'running').length;
  $: failedCount = $jobs.filter((j) => String(j.status).toLowerCase() === 'failed').length;
  $: badgeCount = runningCount + failedCount;
</script>

<svelte:head>
  <title>Video Queue</title>
</svelte:head>

<div class="app-shell">
  <header class="top-bar">
    <strong class="brand">VQ</strong>

    <nav class="view-tabs" role="tablist" aria-label="Main views">
      <button
        role="tab"
        aria-selected={view === 'compose'}
        class:active={view === 'compose'}
        on:click={() => (view = 'compose')}
      >
        Compose
      </button>
      <button
        role="tab"
        aria-selected={view === 'queue'}
        class:active={view === 'queue'}
        on:click={() => (view = 'queue')}
      >
        Queue
        {#if badgeCount > 0}
          <span class="badge" class:has-failed={failedCount > 0}>{badgeCount}</span>
        {/if}
      </button>
    </nav>

    <div class="separator"></div>

    <div class="ws-area">
      <span class="ws-label">Workspace</span>
      <div class="ws-tabs" role="tablist" aria-label="Workspaces">
        {#each $workspaceState.workspaces as ws}
          <button
            role="tab"
            class="ws-tab"
            aria-selected={ws.id === $workspaceState.active_workspace_id}
            class:active={ws.id === $workspaceState.active_workspace_id}
            on:click={() => setActiveWorkspace(ws.id)}
          >
            {ws.name}
          </button>
        {/each}
      </div>
      <div class="ws-controls">
        <button id="newWsBtn" on:click={() => createWorkspace()}>+</button>
        {#if activeWorkspace}
          <button id="renameWsBtn" on:click={() => onRename(activeWorkspace.id, activeWorkspace.name)} title="Rename workspace">Ren</button>
          <button
            id="closeWsBtn"
            disabled={$workspaceState.workspaces.length <= 1}
            on:click={() => closeWorkspace(activeWorkspace.id)}
            title="Close workspace"
          >&times;</button>
        {/if}
      </div>
    </div>
  </header>

  <StatusBar />

  <main class="content">
    {#if view === 'compose'}
      <SubmitPanel workflows={$workflows} onSubmitted={refreshJobs} />
    {:else}
      <QueuePanel />
    {/if}
  </main>
</div>

<style>
  .app-shell {
    display: grid;
    gap: 0.6rem;
    max-width: 1480px;
    margin: 0 auto;
    padding: 0.75rem 1.25rem 1.25rem;
    min-height: 100vh;
    grid-template-rows: auto auto 1fr;
  }

  /* ── Top bar ── */
  .top-bar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 1rem;
    background: var(--color-bg-panel-strong);
    border: 1px solid var(--color-line);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-soft);
    border-top: 2px solid var(--color-accent);
  }

  .brand {
    font-size: 1.15rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    color: var(--color-accent-strong);
    margin-right: 0.25rem;
  }

  /* ── View tabs (Compose / Queue) ── */
  .view-tabs {
    display: flex;
    gap: 0.3rem;
  }
  .view-tabs button {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1rem;
    border-radius: var(--radius-full);
    background: transparent;
    border: 1px solid transparent;
    color: var(--color-text-muted);
    font-size: 0.88rem;
    font-weight: 500;
    cursor: pointer;
  }
  .view-tabs button:hover {
    color: var(--color-text-secondary);
  }
  .view-tabs button.active {
    background: #2a2118;
    border-color: var(--color-accent);
    color: var(--color-accent-strong);
    font-weight: 700;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.25rem;
    height: 1.25rem;
    padding: 0 0.3rem;
    border-radius: var(--radius-full);
    background: var(--color-running);
    color: #090b0f;
    font-size: 0.65rem;
    font-weight: 800;
    line-height: 1;
  }
  .badge.has-failed {
    background: var(--color-failed);
  }

  .separator {
    width: 1px;
    height: 1.4rem;
    background: var(--color-line-strong);
    flex-shrink: 0;
  }

  /* ── Workspace area ── */
  .ws-area {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-left: auto;
  }
  .ws-label {
    color: var(--color-text-muted);
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    white-space: nowrap;
  }
  .ws-tabs {
    display: flex;
    gap: 0.25rem;
  }
  .ws-tab {
    padding: 0.38rem 0.7rem;
    border-radius: var(--radius-full);
    background: transparent;
    border: 1px solid var(--color-line);
    color: var(--color-text-secondary);
    font-size: 0.78rem;
    cursor: pointer;
  }
  .ws-tab.active {
    background: var(--color-bg-card);
    border-color: var(--color-line-strong);
    color: var(--color-text);
    font-weight: 600;
  }
  .ws-controls {
    display: flex;
    gap: 0.2rem;
  }
  .ws-controls button {
    width: 1.7rem;
    height: 1.7rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border-radius: 50%;
    background: transparent;
    border: 1px solid var(--color-line);
    color: var(--color-text-muted);
    font-size: 0.78rem;
    cursor: pointer;
  }
  .ws-controls button:hover:not(:disabled) {
    color: var(--color-text);
    border-color: var(--color-line-strong);
  }

  /* ── Content ── */
  .content {
    min-width: 0;
  }

  @media (max-width: 900px) {
    .app-shell {
      padding: 0.5rem 0.75rem 1rem;
    }
    .top-bar {
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .separator {
      display: none;
    }
    .ws-area {
      margin-left: 0;
      width: 100%;
    }
  }
</style>
