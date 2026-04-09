<script lang="ts">
  import StatusBadge from './StatusBadge.svelte';
  import JobDetail from './JobDetail.svelte';
  import { api } from '$lib/api';
  import { refreshJobs } from '$lib/stores/jobs';
  import type { JobDetail as JobDetailType, JobListItem } from '$lib/types';

  export let job: JobListItem;
  export let selected = false;

  let expanded = false;
  let loadingDetail = false;
  let detailError = '';
  let detail: JobDetailType | null = null;
  let actionBusy = false;
  let actionError = '';

  function doneCount(): number {
    return Number(job.succeeded_count || 0) + Number(job.failed_count || 0) + Number(job.canceled_count || 0);
  }

  function totalCount(): number {
    return Math.max(0, Number(job.prompt_count || 0));
  }

  function progressPercent(): number {
    const total = totalCount();
    if (total <= 0) return 0;
    return Math.min(100, Math.round((doneCount() / total) * 100));
  }

  function normalizedStatus(): string {
    return String(job.status || '').toLowerCase();
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      void toggle();
    }
  }

  function relativeAge(iso: string | null): string {
    if (!iso) return 'n/a';
    const ts = new Date(String(iso)).getTime();
    if (!Number.isFinite(ts)) return 'n/a';
    const sec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
    if (sec < 60) return `${sec}s ago`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
    return `${Math.floor(sec / 86400)}d ago`;
  }

  async function toggle(): Promise<void> {
    expanded = !expanded;
    if (!expanded || detail || loadingDetail) return;
    loadingDetail = true;
    detailError = '';
    try {
      detail = await api.jobDetail(Number(job.id), { timeoutMs: 15000 });
    } catch (e) {
      detailError = e instanceof Error ? e.message : String(e);
    } finally {
      loadingDetail = false;
    }
  }

  async function doCancel(event: Event): Promise<void> {
    event.stopPropagation();
    if (actionBusy) return;
    if (!window.confirm(`Cancel job #${job.id}?`)) return;
    actionBusy = true;
    actionError = '';
    try {
      await api.cancelJob(Number(job.id), { timeoutMs: 12000 });
      await refreshJobs();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionBusy = false;
    }
  }

  async function doRetry(event: Event): Promise<void> {
    event.stopPropagation();
    if (actionBusy) return;
    actionBusy = true;
    actionError = '';
    try {
      await api.retryJob(Number(job.id), { timeoutMs: 12000 });
      await refreshJobs();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e);
    } finally {
      actionBusy = false;
    }
  }
</script>

<article class="job-shell" class:selected data-status={normalizedStatus()}>
  <div class="job" role="button" tabindex="0" on:click={toggle} on:keydown={onKeydown}>
    <div class="top">
      <div class="identity">
        <button class="exp" aria-label={expanded ? 'Collapse job details' : 'Expand job details'} on:click|stopPropagation={toggle}>
          {expanded ? '▾' : '▸'}
        </button>
        <div class="copy">
          <p class="eyebrow">Job #{job.id}</p>
          <strong>{job.name || 'Untitled queue item'}</strong>
          <span class="workflow">{job.workflow_name || 'Unknown workflow'}</span>
        </div>
      </div>
      <div class="top-right">
        <StatusBadge status={String(job.status || '')} />
        <div class="actions">
          {#if String(job.status || '').toLowerCase() === 'failed'}
            <button disabled={actionBusy} on:click|stopPropagation={doRetry}>Retry</button>
          {/if}
          {#if ['pending', 'running'].includes(String(job.status || '').toLowerCase())}
            <button disabled={actionBusy} on:click|stopPropagation={doCancel}>Cancel</button>
          {/if}
        </div>
      </div>
    </div>

    <div class="meta-row">
      <span class="meta-pill">{totalCount()} {totalCount() === 1 ? 'prompt' : 'prompts'}</span>
      <span class="meta-pill">Created {relativeAge(job.created_at)}</span>
      <span class="meta-pill">Started {relativeAge(job.started_at)}</span>
      {#if job.completed_at}
        <span class="meta-pill">Completed {relativeAge(job.completed_at)}</span>
      {/if}
    </div>

    <div class="progress-row">
      <div class="progress-copy">
        <span>Progress</span>
        <strong>{progressPercent()}%</strong>
      </div>
      <div class="bar" aria-hidden="true">
        <div class="fill" class:fill-failed={normalizedStatus() === 'failed'} style={`width:${progressPercent()}%`}></div>
      </div>
      <div class="counts">{doneCount()} of {totalCount()} {totalCount() === 1 ? 'prompt' : 'prompts'} resolved</div>
    </div>

    {#if job.error_summary}
      <div class="summary-error">{job.error_summary}</div>
    {/if}
  </div>

  {#if actionError}
    <div class="err">{actionError}</div>
  {/if}
  {#if expanded}
    {#if loadingDetail}
      <div class="loading">Loading details...</div>
    {:else if detailError}
      <div class="err">{detailError}</div>
    {:else}
      <JobDetail {detail} />
    {/if}
  {/if}
</article>

<style>
  .job-shell {
    display: grid;
    gap: 0.4rem;
  }
  .job {
    display: grid;
    gap: 0.85rem;
    padding: 1rem 1.05rem;
    border: 1px solid var(--color-line);
    border-radius: var(--radius-lg);
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent 100%),
      rgba(13, 16, 21, 0.8);
    cursor: pointer;
    box-shadow: var(--shadow-soft);
  }
  .job:hover {
    transform: translateY(-2px);
    border-color: var(--color-line-strong);
  }
  .job:focus-visible {
    outline: none;
    border-color: rgba(201, 144, 76, 0.5);
    box-shadow:
      inset 0 0 0 1px rgba(201, 144, 76, 0.14),
      0 0 0 3px rgba(201, 144, 76, 0.14),
      var(--shadow-soft);
  }
  .job-shell.selected .job {
    border-color: rgba(201, 144, 76, 0.42);
    box-shadow:
      inset 0 0 0 1px rgba(201, 144, 76, 0.1),
      var(--shadow-soft);
  }
  .job-shell[data-status='running'] .job {
    border-color: rgba(216, 161, 94, 0.24);
  }
  .job-shell[data-status='failed'] .job {
    border-color: rgba(216, 118, 134, 0.24);
  }
  .top {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: start;
  }
  .identity {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.8rem;
    align-items: start;
  }
  .copy {
    display: grid;
    gap: 0.22rem;
  }
  .copy strong {
    font-size: 1.18rem;
    font-weight: 600;
    letter-spacing: -0.03em;
    line-height: 1;
  }
  .workflow {
    color: var(--color-text-secondary);
    font-size: 0.86rem;
  }
  .top-right {
    display: grid;
    gap: 0.7rem;
    justify-items: end;
  }
  .meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
  }
  .meta-pill {
    display: inline-flex;
    align-items: center;
    min-height: 2rem;
    padding: 0.28rem 0.7rem;
    border-radius: var(--radius-full);
    border: 1px solid var(--color-line);
    background: rgba(255, 255, 255, 0.03);
    color: var(--color-text-secondary);
    font-size: 0.77rem;
    letter-spacing: 0.02em;
  }
  .progress-row {
    display: grid;
    grid-template-columns: auto minmax(180px, 1fr) auto;
    gap: 0.8rem;
    align-items: center;
  }
  .progress-copy {
    display: grid;
    gap: 0.15rem;
    min-width: 88px;
  }
  .progress-copy span,
  .counts {
    color: var(--color-text-muted);
    font-size: 0.77rem;
  }
  .progress-copy strong {
    font-size: 1rem;
    font-weight: 600;
  }
  .bar {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--color-line);
    border-radius: var(--radius-full);
    height: 0.72rem;
    overflow: hidden;
  }
  .fill {
    background: linear-gradient(90deg, var(--color-accent), var(--color-accent-strong));
    height: 100%;
    box-shadow: 0 0 20px rgba(201, 144, 76, 0.36);
  }
  .fill.fill-failed {
    background: linear-gradient(90deg, rgba(216, 118, 134, 0.6), rgba(216, 118, 134, 0.85));
    box-shadow: 0 0 20px rgba(216, 118, 134, 0.26);
  }
  .summary-error {
    padding: 0.75rem 0.85rem;
    border-radius: var(--radius-md);
    border: 1px solid rgba(216, 118, 134, 0.22);
    background: rgba(216, 118, 134, 0.08);
    color: #e4bcc2;
    font-size: 0.84rem;
    line-height: 1.45;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
  }
  .actions button {
    padding: 0.58rem 0.92rem;
    border-radius: var(--radius-full);
    background: rgba(255, 255, 255, 0.04);
    font-size: 0.8rem;
    cursor: pointer;
  }
  .exp {
    width: 2rem;
    height: 2rem;
    display: inline-grid;
    place-items: center;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.05);
    color: var(--color-text);
    cursor: pointer;
  }
  .loading {
    margin-top: 0.2rem;
    font-size: 0.84rem;
    color: var(--color-text-secondary);
  }
  .err {
    color: var(--color-failed);
    font-size: 0.84rem;
  }

  @media (max-width: 900px) {
    .top,
    .progress-row {
      grid-template-columns: 1fr;
    }
    .top-right {
      justify-items: start;
    }
    .actions {
      justify-content: flex-start;
    }
  }
</style>
