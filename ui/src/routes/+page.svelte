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

  $: activeWorkspace =
    $workspaceState.workspaces.find((ws) => ws.id === $workspaceState.active_workspace_id) ??
    $workspaceState.workspaces[0] ??
    null;
</script>

<svelte:head>
  <title>Video Queue Control Room</title>
</svelte:head>

<main class="page-shell">
  <header class="hero panel">
    <div class="hero-copy">
      <p class="eyebrow">Video Queue Control Room</p>
      <h1>Stage jobs like a workbench. Watch the queue like a live board.</h1>
      <p class="hero-text">
        The left side is for preparing batches and presets. The right side stays focused on execution state,
        failures, and throughput so the queue remains readable under load.
      </p>
    </div>
    <div class="hero-meta">
      <div class="hero-stat">
        <span>Workspaces</span>
        <strong>{$workspaceState.workspaces.length}</strong>
      </div>
      <div class="hero-stat">
        <span>Active Desk</span>
        <strong>{activeWorkspace?.name || 'Workspace'}</strong>
      </div>
    </div>
  </header>

  <StatusBar />

  <section class="workspace-strip panel" aria-label="Workspace Tabs">
    <div class="workspace-copy">
      <p class="eyebrow">Workspaces</p>
      <h2 class="section-title">Keep experiments isolated.</h2>
    </div>
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

  <div class="workspace-layout">
    <section class="submit-column">
      <div class="column-intro">
        <p class="eyebrow">Submission Desk</p>
        <h2 class="section-title">Compose jobs, presets, and staged inputs.</h2>
        <p class="section-copy">
          Configure the workflow, attach assets, and keep prompt variations contained to the current workspace.
        </p>
      </div>
      <SubmitPanel workflows={$workflows} onSubmitted={refreshJobs} />
    </section>

    <aside class="queue-column">
      <div class="column-intro">
        <p class="eyebrow">Queue Board</p>
        <h2 class="section-title">Track the render line in real time.</h2>
        <p class="section-copy">
          Running jobs stay at the top, failed jobs remain visible, and details expand inline when you need the
          full execution trail.
        </p>
      </div>
      <QueuePanel />
    </aside>
  </div>
</main>

<style>
  .page-shell {
    position: relative;
    z-index: 1;
    display: grid;
    gap: 1rem;
    max-width: 1480px;
    margin: 0 auto;
    padding: 1.25rem;
  }
  .hero {
    display: grid;
    grid-template-columns: minmax(0, 1.45fr) minmax(260px, 0.75fr);
    gap: 1.25rem;
    padding: 1.35rem 1.45rem;
    overflow: hidden;
  }
  .hero-copy {
    display: grid;
    gap: 0.8rem;
    align-content: start;
  }
  .hero-copy h1 {
    margin: 0;
    max-width: 12ch;
    font-size: clamp(2.3rem, 4vw, 4.5rem);
    line-height: 0.94;
    letter-spacing: -0.06em;
    font-weight: 600;
  }
  .hero-text {
    margin: 0;
    max-width: 62ch;
    color: var(--color-text-secondary);
    font-size: 1rem;
    line-height: 1.55;
  }
  .hero-meta {
    display: grid;
    gap: 0.8rem;
    align-content: end;
  }
  .hero-stat {
    display: grid;
    gap: 0.35rem;
    padding: 1rem 1.05rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--color-line);
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.05), transparent),
      rgba(255, 255, 255, 0.03);
  }
  .hero-stat span {
    color: var(--color-text-muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .hero-stat strong {
    font-size: clamp(1.25rem, 2vw, 1.85rem);
    font-weight: 600;
    letter-spacing: -0.04em;
  }
  .workspace-strip {
    display: grid;
    gap: 1rem;
    padding: 1rem 1.2rem;
  }
  .workspace-copy {
    display: grid;
    gap: 0.3rem;
  }
  .workspace-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 1rem;
    align-items: end;
  }
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
  }
  .tabs button,
  .controls button {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--color-line);
    color: var(--color-text-secondary);
    border-radius: var(--radius-full);
    padding: 0.62rem 0.95rem;
    cursor: pointer;
  }
  .tabs button.active {
    background: linear-gradient(180deg, rgba(201, 144, 76, 0.22), rgba(201, 144, 76, 0.08));
    border-color: rgba(201, 144, 76, 0.45);
    color: var(--color-text);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
  }
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
  }
  .workspace-layout {
    display: grid;
    grid-template-columns: minmax(520px, 1.08fr) minmax(420px, 0.92fr);
    gap: 1rem;
    align-items: start;
  }
  .submit-column,
  .queue-column,
  .column-intro {
    display: grid;
    gap: 0.7rem;
  }
  .queue-column :global(#queuePanel) {
    position: sticky;
    top: 1.25rem;
  }

  @media (max-width: 1200px) {
    .workspace-layout {
      grid-template-columns: 1fr;
    }
    .queue-column :global(#queuePanel) {
      position: static;
    }
  }

  @media (max-width: 820px) {
    .page-shell {
      padding: 0.9rem;
    }
    .hero {
      grid-template-columns: 1fr;
      padding: 1.15rem;
    }
    .hero-copy h1 {
      max-width: none;
      font-size: clamp(2rem, 12vw, 3rem);
    }
  }
</style>
