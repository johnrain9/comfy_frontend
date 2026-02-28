<script lang="ts">
  import StatusBadge from './StatusBadge.svelte';
  import JobDetail from './JobDetail.svelte';
  import { api } from '$lib/api';
  import { refreshJobs } from '$lib/stores/jobs';
  import type { JobDetail as JobDetailType, JobListItem } from '$lib/types';

  export let job: JobListItem;

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

<article class="job">
  <div class="top">
    <button class="exp" aria-label={expanded ? 'Collapse job details' : 'Expand job details'} on:click|stopPropagation={toggle}>
      {expanded ? '▾' : '▸'}
    </button>
    <strong>#{job.id}</strong>
    <span class="name">{job.name || '-'}</span>
    <span class="workflow">{job.workflow_name || '-'}</span>
    <StatusBadge status={String(job.status || '')} />
    <div class="actions">
      {#if String(job.status || '').toLowerCase() === 'failed'}
        <button disabled={actionBusy} on:click={doRetry}>Retry</button>
      {/if}
      {#if ['pending', 'running'].includes(String(job.status || '').toLowerCase())}
        <button disabled={actionBusy} on:click={doCancel}>Cancel</button>
      {/if}
    </div>
  </div>
  <div class="sub">
    <span>{doneCount()} / {totalCount()} prompts</span>
    <div class="bar">
      <div class="fill" style={`width:${progressPercent()}%`}></div>
    </div>
    <span>{progressPercent()}%</span>
    <span>created {relativeAge(job.created_at)}</span>
    <span>started {relativeAge(job.started_at)}</span>
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
  .job {
    border: 1px solid #22324d;
    border-radius: 10px;
    padding: 8px 10px;
    background: #0f1a2d;
    cursor: pointer;
  }
  .top {
    display: grid;
    grid-template-columns: auto auto minmax(140px, 1fr) minmax(120px, 200px) auto auto;
    align-items: center;
    gap: 8px;
  }
  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .workflow {
    color: #a2b8d8;
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sub {
    display: grid;
    grid-template-columns: auto minmax(120px, 1fr) auto auto auto;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
    font-size: 12px;
    color: #9bb2d3;
  }
  .bar {
    background: #0a1322;
    border: 1px solid #2c4063;
    border-radius: 999px;
    height: 8px;
    overflow: hidden;
  }
  .fill {
    background: linear-gradient(90deg, #4f9dff, #89f0b4);
    height: 100%;
  }
  .actions {
    display: flex;
    gap: 6px;
    justify-content: flex-end;
  }
  .actions button {
    border: 1px solid #39537c;
    border-radius: 8px;
    background: #13253f;
    color: #e7efff;
    font-size: 12px;
    padding: 4px 8px;
    cursor: pointer;
  }
  .actions button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .exp {
    border: 0;
    background: transparent;
    color: #c7d8f2;
    cursor: pointer;
  }
  .loading {
    margin-top: 8px;
    font-size: 12px;
    color: #9bb2d3;
  }
  .err {
    margin-top: 8px;
    color: #ff9aa9;
    font-size: 12px;
  }
</style>
