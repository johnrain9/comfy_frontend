<script lang="ts">
  import { derived } from 'svelte/store';
  import { jobs, jobsError } from '$lib/stores/jobs';
  import JobRow from './JobRow.svelte';
  import BulkActions from './BulkActions.svelte';

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
    <strong>Queue</strong>
    <span class="count">{shownRows.length} of {allRows.length}</span>
    <span class="err">{$jobsError}</span>
  </div>
  <div class="controls">
    <select id="statusFilter" bind:value={statusFilter}>
      <option value="all">All</option>
      <option value="running">Running</option>
      <option value="failed">Failed</option>
      <option value="pending">Pending</option>
      <option value="succeeded">Succeeded</option>
      <option value="canceled">Canceled</option>
    </select>
    <input id="queueSearch" bind:value={query} placeholder="Search jobs..." />
    <select id="queueSort" bind:value={sort}>
      <option value="actionable">Actionable</option>
      <option value="newest">Newest</option>
      <option value="oldest">Oldest</option>
    </select>
    <button id="selectVisible" type="button" on:click={selectVisible}>Select Visible</button>
    <button type="button" on:click={clearSelection} disabled={!selected.length}>Clear Selection</button>
  </div>
  <div class="list" on:scroll={onListScroll} id="jobList">
    {#each shownRows as j}
      <label class="sel">
        <input
          type="checkbox"
          checked={selected.includes(Number(j.id))}
          on:change={(e) => {
            toggleSelected(Number(j.id), (e.target as HTMLInputElement).checked);
          }}
        />
        <JobRow job={j} />
      </label>
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
  </div>
  <BulkActions selectedIds={selected} />
</section>

<style>
  .head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }
  .count {
    color: #9bb2d3;
    font-size: 12px;
  }
  .err {
    margin-left: auto;
    color: #ff9aa9;
    font-size: 12px;
  }
  .controls {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
  }
  .controls input,
  .controls select {
    background: #0a1322;
    border: 1px solid #2f4a72;
    color: #e7efff;
    border-radius: 8px;
    padding: 6px;
  }
  .controls button {
    background: #13253f;
    border: 1px solid #2f4a72;
    color: #e7efff;
    border-radius: 8px;
    padding: 6px 9px;
    cursor: pointer;
  }
  .controls button:disabled {
    opacity: 0.55;
    cursor: default;
  }
  .list {
    display: grid;
    gap: 8px;
    margin-bottom: 8px;
    max-height: 66vh;
    overflow: auto;
    padding-right: 2px;
  }
  .sel {
    display: grid;
    grid-template-columns: 24px 1fr;
    gap: 8px;
    align-items: start;
  }
  .load-more {
    border: 1px solid #39537c;
    border-radius: 8px;
    background: #0d1b2f;
    color: #dce9ff;
    padding: 8px;
    cursor: pointer;
  }
</style>
