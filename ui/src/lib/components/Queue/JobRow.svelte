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

  interface ParsedParams {
    prompt: string;
    negPrompt: string;
    resolution: string;
    steps: string;
    extras: Array<{ key: string; value: string }>;
  }

  function parseParams(): ParsedParams | null {
    if (!job.params_json) return null;
    try {
      const p = typeof job.params_json === 'string' ? JSON.parse(job.params_json) : job.params_json;
      if (!p || typeof p !== 'object') return null;

      const prompt = String(p.positive_prompt || p.positive_prompt_stage1 || '');
      const negPrompt = String(p.negative_prompt || '');
      const steps = p.steps ? String(p.steps) : '';

      let resolution = '';
      if (p.resolution_preset) {
        resolution = String(p.resolution_preset);
      } else if (p.width && p.height) {
        resolution = `${p.width}x${p.height}`;
      }

      const skip = new Set([
        'positive_prompt', 'negative_prompt', 'positive_prompt_stage1',
        'positive_prompt_stage2', 'positive_prompt_stage3',
        'steps', 'resolution_preset', 'width', 'height',
      ]);
      const extras: Array<{ key: string; value: string }> = [];
      for (const [k, v] of Object.entries(p)) {
        if (skip.has(k) || v === null || v === undefined || v === '') continue;
        const sv = String(v);
        if (sv.length > 80) continue;
        extras.push({ key: k.replace(/_/g, ' '), value: sv });
      }

      return { prompt, negPrompt, resolution, steps, extras: extras.slice(0, 6) };
    } catch {
      return null;
    }
  }

  function shortDir(dir: string | null): string {
    if (!dir) return '';
    const parts = dir.replace(/\\/g, '/').replace(/\/+$/, '').split('/');
    return parts.length > 2 ? `.../${parts.slice(-2).join('/')}` : dir;
  }

  function truncate(text: string, max: number): string {
    if (text.length <= max) return text;
    return text.slice(0, max) + '...';
  }

  $: params = parseParams();

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

    {#if params || job.input_dir}
      <div class="info-section">
        {#if params?.prompt}
          <div class="info-line">
            <span class="info-key">Prompt</span>
            <span class="info-val prompt-text">{truncate(params.prompt, 140)}</span>
          </div>
        {/if}
        {#if job.input_dir}
          <div class="info-line">
            <span class="info-key">Input</span>
            <span class="info-val mono">{shortDir(job.input_dir)}</span>
          </div>
        {/if}
        <div class="info-chips">
          {#if params?.resolution}
            <span class="info-chip"><span class="chip-k">Res</span> {params.resolution}</span>
          {/if}
          {#if params?.steps}
            <span class="info-chip"><span class="chip-k">Steps</span> {params.steps}</span>
          {/if}
          {#each params?.extras || [] as extra}
            <span class="info-chip"><span class="chip-k">{extra.key}</span> {truncate(extra.value, 30)}</span>
          {/each}
        </div>
      </div>
    {/if}

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
    background: var(--color-bg-panel);
    cursor: pointer;
    box-shadow: var(--shadow-soft);
  }
  .job:hover {
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
    border-left: 3px solid var(--color-running);
  }
  .job-shell[data-status='failed'] .job {
    border-left: 3px solid var(--color-failed);
  }
  .job-shell[data-status='pending'] .job {
    border-left: 3px solid var(--color-pending);
  }
  .job-shell[data-status='succeeded'] .job {
    border-left: 3px solid var(--color-succeeded);
  }
  .job-shell[data-status='canceled'] .job {
    border-left: 3px solid var(--color-canceled);
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
    font-weight: 700;
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
  .info-section {
    display: grid;
    gap: 0.45rem;
    padding: 0.65rem 0.75rem;
    border-radius: var(--radius-md);
    background: var(--color-bg-inset);
    border: 1px solid var(--color-line);
  }
  .info-line {
    display: grid;
    grid-template-columns: 52px minmax(0, 1fr);
    gap: 0.5rem;
    align-items: baseline;
  }
  .info-key {
    color: var(--color-text-muted);
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .info-val {
    color: var(--color-text-secondary);
    font-size: 0.78rem;
    line-height: 1.35;
    overflow-wrap: anywhere;
  }
  .prompt-text {
    color: var(--color-text);
    font-style: italic;
  }
  .info-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.1rem;
  }
  .info-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.5rem;
    border-radius: var(--radius-full);
    border: 1px solid var(--color-line);
    background: var(--color-bg-panel);
    color: var(--color-text-secondary);
    font-size: 0.7rem;
    font-family: var(--font-mono);
  }
  .chip-k {
    color: var(--color-text-muted);
    font-family: var(--font-sans);
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
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
    font-weight: 700;
    color: var(--color-accent-strong);
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
  }
  .fill.fill-failed {
    background: linear-gradient(90deg, rgba(216, 118, 134, 0.6), rgba(216, 118, 134, 0.85));
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
