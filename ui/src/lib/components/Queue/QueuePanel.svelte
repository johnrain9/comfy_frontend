<script lang="ts">
  import { derived } from 'svelte/store';
  import { jobs, jobsError } from '$lib/stores/jobs';
  import JobRow from './JobRow.svelte';
  import BulkActions from './BulkActions.svelte';

  const STATUS_OPTIONS = [
    { value: 'all', label: 'All' },
    { value: 'running', label: 'Running' },
    { value: 'failed', label: 'Failed' },
    { value: 'pending', label: 'Pending' },
    { value: 'succeeded', label: 'Succeeded' },
    { value: 'canceled', label: 'Canceled' },
  ] as const;

  const RENDER_STEP = 200;

  let query = '';
  let sort = 'actionable';
  let statusFilter = 'all';
  let selected: number[] = [];
  let renderLimit = RENDER_STEP;
  let previousFilterKey = '';

  function pri(status: string): number {
    const s = String(status || '').toLowerCase();
    if (s === 'running') return 0;
    if (s === 'failed') return 1;
    if (s === 'pending') return 2;
    if (s === 'canceled') return 3;
    if (s === 'succeeded') return 4;
    return 5;
  }

  const visible = derived(jobs, ($jobs) => {
    const q = query.toLowerCase().trim();
    let rows = [...$jobs];
    if (statusFilter !== 'all') rows = rows.filter((j) => String(j.status).toLowerCase() === statusFilter);
    if (q) {
      rows = rows.filter((j) =>
        `${j.id} ${j.name || ''} ${j.workflow_name || ''} ${j.status || ''} ${j.error_summary || ''}`
          .toLowerCase()
          .includes(q),
      );
    }
    if (sort === 'newest') rows.sort((a, b) => b.id - a.id);
    else if (sort === 'oldest') rows.sort((a, b) => a.id - b.id);
    else rows.sort((a, b) => pri(String(a.status)) - pri(String(b.status)) || b.id - a.id);
    return rows;
  });

  $: allRows = $visible;
  $: shownRows = allRows.slice(0, renderLimit);
  $: statusCounts = {
    all: $jobs.length,
    running: $jobs.filter((job) => String(job.status).toLowerCase() === 'running').length,
    failed: $jobs.filter((job) => String(job.status).toLowerCase() === 'failed').length,
    pending: $jobs.filter((job) => String(job.status).toLowerCase() === 'pending').length,
    succeeded: $jobs.filter((job) => String(job.status).toLowerCase() === 'succeeded').length,
    canceled: $jobs.filter((job) => String(job.status).toLowerCase() === 'canceled').length,
  };

  $: {
    const key = `${statusFilter}|${sort}|${query}`;
    if (key !== previousFilterKey) {
      previousFilterKey = key;
      renderLimit = RENDER_STEP;
      selected = [];
    }
  }

  function onListScroll(event: Event): void {
    const el = event.currentTarget as HTMLDivElement;
    if (!el) return;
    if (renderLimit >= allRows.length) return;
    const nearBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 280;
    if (nearBottom) {
      renderLimit = Math.min(allRows.length, renderLimit + RENDER_STEP);
    }
  }

  function toggleSelected(id: number, checked: boolean): void {
    const imageId = Number(id);
    if (checked) {
      if (!selected.includes(imageId)) selected = [...selected, imageId];
      return;
    }
    selected = selected.filter((x) => x !== imageId);
  }

  function selectVisible(): void {
    selected = shownRows.map((j) => Number(j.id));
  }

  function clearSelection(): void {
    selected = [];
  }
</script>

<section class="panel p-3" id="queuePanel">
  <div class="head">
    <div class="head-copy">
      <p class="eyebrow">Queue Board</p>
      <h3>Jobs in flight</h3>
      <p class="copy">Running and failed work stays prominent so you can act without digging.</p>
    </div>
    <div class="stats">
      <div class="stat">
        <span>Running</span>
        <strong>{statusCounts.running}</strong>
      </div>
      <div class="stat">
        <span>Pending</span>
        <strong>{statusCounts.pending}</strong>
      </div>
      <div class="stat">
        <span>Failed</span>
        <strong>{statusCounts.failed}</strong>
      </div>
    </div>
  </div>
  <div class="toolbar">
    <div class="chips" role="tablist" aria-label="Queue status filters">
      {#each STATUS_OPTIONS as option}
        <button
          type="button"
          class:active={statusFilter === option.value}
          aria-pressed={statusFilter === option.value}
          on:click={() => (statusFilter = option.value)}
        >
          {option.label}
          <span>{statusCounts[option.value]}</span>
        </button>
      {/each}
    </div>
    <div class="controls">
      <input id="queueSearch" bind:value={query} placeholder="Search ids, names, workflows, errors..." />
      <select id="queueSort" bind:value={sort}>
        <option value="actionable">Actionable</option>
        <option value="newest">Newest</option>
        <option value="oldest">Oldest</option>
      </select>
      <button id="selectVisible" type="button" on:click={selectVisible}>Select Visible</button>
      <button type="button" on:click={clearSelection} disabled={!selected.length}>Clear Selection</button>
    </div>
  </div>

  <div class="status-line">
    <span>{shownRows.length} shown of {allRows.length}</span>
    {#if selected.length}
      <span>{selected.length} selected</span>
    {/if}
    {#if $jobsError}
      <span class="err">{$jobsError}</span>
    {/if}
  </div>

  <div class="list" on:scroll={onListScroll} id="jobList">
    {#if !allRows.length}
      <div class="empty-state">
        <div class="empty-mark"></div>
        <strong>No jobs match the current filters.</strong>
        <span>Clear the search or submit a new run to populate the board.</span>
      </div>
    {:else}
      {#each shownRows as j (j.id)}
        <div class="sel-row">
          <div class="check-wrap">
            <input
              type="checkbox"
              aria-label={`Select job ${j.id}`}
              checked={selected.includes(Number(j.id))}
              on:change={(e) => {
                toggleSelected(Number(j.id), (e.target as HTMLInputElement).checked);
              }}
            />
          </div>
          <JobRow job={j} selected={selected.includes(Number(j.id))} />
        </div>
      {/each}
      {#if shownRows.length < allRows.length}
        <button
          class="load-more"
          on:click={() => {
            renderLimit = Math.min(allRows.length, renderLimit + RENDER_STEP);
          }}
        >
          Load More ({allRows.length - shownRows.length} remaining)
        </button>
      {/if}
    {/if}
  </div>
  <BulkActions selectedIds={selected} />
</section>

<style>
  #queuePanel {
    display: grid;
    gap: 1rem;
    padding: 1.15rem;
  }
  .head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: end;
  }
  .head-copy {
    display: grid;
    gap: 0.28rem;
  }
  .head-copy h3 {
    margin: 0;
    font-size: 1.4rem;
    letter-spacing: -0.04em;
  }
  .copy {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.9rem;
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(3, minmax(92px, 1fr));
    gap: 0.65rem;
  }
  .stat {
    display: grid;
    gap: 0.22rem;
    padding: 0.8rem 0.85rem;
    border: 1px solid var(--color-line);
    border-radius: var(--radius-md);
    background: rgba(255, 255, 255, 0.03);
  }
  .stat span {
    color: var(--color-text-muted);
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .stat strong {
    font-size: 1.1rem;
    font-weight: 600;
  }
  .toolbar {
    display: grid;
    gap: 0.8rem;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  .chips button {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.45rem 0.65rem;
    border-radius: var(--radius-full);
    background: rgba(255, 255, 255, 0.03);
    color: var(--color-text-secondary);
    font-size: 0.82rem;
  }
  .chips button span {
    font-size: 0.76rem;
    color: var(--color-text-muted);
  }
  .chips button.active {
    background: linear-gradient(180deg, rgba(201, 144, 76, 0.22), rgba(201, 144, 76, 0.08));
    border-color: rgba(201, 144, 76, 0.34);
    color: var(--color-text);
  }
  .controls {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto auto;
    gap: 0.65rem;
  }
  .controls input,
  .controls select,
  .controls button {
    padding: 0.7rem 0.85rem;
  }
  .status-line {
    display: flex;
    flex-wrap: wrap;
    gap: 0.7rem;
    color: var(--color-text-muted);
    font-size: 0.78rem;
  }
  .err {
    color: var(--color-failed);
  }
  .list {
    display: grid;
    gap: 0.85rem;
    max-height: 66vh;
    overflow: auto;
    padding-right: 0.15rem;
  }
  .sel-row {
    display: grid;
    grid-template-columns: 34px minmax(0, 1fr);
    gap: 0.75rem;
    align-items: start;
  }
  .check-wrap {
    padding-top: 1rem;
  }
  .check-wrap input {
    width: 1rem;
    height: 1rem;
    accent-color: var(--color-accent);
  }
  .empty-state {
    display: grid;
    justify-items: center;
    gap: 0.5rem;
    padding: 3.2rem 1rem;
    border: 1px dashed var(--color-line);
    border-radius: var(--radius-lg);
    color: var(--color-text-secondary);
    text-align: center;
  }
  .empty-mark {
    width: 3rem;
    height: 3rem;
    border-radius: 50%;
    border: 1px solid var(--color-line);
    background:
      radial-gradient(circle at 50% 50%, rgba(201, 144, 76, 0.18), transparent 58%),
      rgba(255, 255, 255, 0.03);
  }
  .load-more {
    border-radius: var(--radius-full);
    background: rgba(255, 255, 255, 0.04);
    color: var(--color-text);
    padding: 0.8rem 1rem;
    cursor: pointer;
  }

  @media (max-width: 900px) {
    .head,
    .controls {
      grid-template-columns: 1fr;
    }
    .stats {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  @media (max-width: 620px) {
    .sel-row {
      grid-template-columns: 1fr;
    }
    .check-wrap {
      padding-top: 0;
    }
  }
</style>
