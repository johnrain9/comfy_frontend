<script lang="ts">
  import PromptRow from './PromptRow.svelte';
  import { api } from '$lib/api';
  import type { JobDetail as JobDetailType } from '$lib/types';

  export let detail: JobDetailType | null = null;

  const PRIMARY_KEYS = [
    'id',
    'name',
    'workflow_name',
    'status',
    'created_at',
    'started_at',
    'completed_at',
    'input_dir',
    'resolution_preset',
    'prompt_count',
    'pending_count',
    'running_count',
    'succeeded_count',
    'failed_count',
    'canceled_count',
  ];

  let logVisible = false;
  let logLoading = false;
  let logText = '';
  let logError = '';

  const DATE_KEYS = new Set(['created_at', 'started_at', 'completed_at', 'finished_at']);

  function formatTimestamp(iso: string): string {
    const d = new Date(iso);
    if (!Number.isFinite(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  }

  function formatValue(value: unknown, key?: string): string {
    if (value === null || value === undefined || value === '') return 'n/a';
    if (key && DATE_KEYS.has(key) && typeof value === 'string') {
      return formatTimestamp(value);
    }
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    }
    return String(value);
  }

  function titleFor(key: string): string {
    return key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  $: primaryEntries = detail
    ? PRIMARY_KEYS
        .map((key) => [key, detail.job[key]] as const)
        .filter(([, value]) => value !== null && value !== undefined && value !== '')
    : [];

  $: extraEntries = detail
    ? Object.entries(detail.job).filter(
        ([key, value]) => !PRIMARY_KEYS.includes(key) && value !== null && value !== undefined && value !== '',
      )
    : [];

  async function toggleLog(): Promise<void> {
    logVisible = !logVisible;
    if (!logVisible || logText || logLoading || !detail) return;
    logLoading = true;
    logError = '';
    try {
      logText = await api.jobLog(Number(detail.job.id), { timeoutMs: 15000 });
    } catch (e) {
      logError = e instanceof Error ? e.message : String(e);
    } finally {
      logLoading = false;
    }
  }
</script>

{#if detail}
  <section class="detail">
    <div class="overview">
      {#each primaryEntries as [key, value]}
        <div class="overview-card">
          <span class="k">{titleFor(key)}</span>
          <span class="v">{formatValue(value, key)}</span>
        </div>
      {/each}
    </div>

    <div class="head-row">
      <div class="section-copy-block">
        <p class="eyebrow">Prompt Runs</p>
        <strong>Prompts ({detail.prompts.length})</strong>
      </div>
      <button class="log-btn" on:click={toggleLog}>{logVisible ? 'Hide Log' : 'View Log'}</button>
    </div>
    {#if detail.prompts.length}
      <div class="prompts">
        {#each detail.prompts as p}
          <PromptRow prompt={p} />
        {/each}
      </div>
    {:else}
      <div class="empty">No prompt rows recorded for this job yet.</div>
    {/if}

    {#if extraEntries.length}
      <details class="raw-meta">
        <summary>Full job metadata</summary>
        <div class="meta-grid">
          {#each extraEntries as [key, value]}
            <div class="meta-item">
              <span class="k">{titleFor(key)}</span>
              <span class="v">{formatValue(value, key)}</span>
            </div>
          {/each}
        </div>
      </details>
    {/if}

    {#if logVisible}
      <div class="log-wrap">
        {#if logLoading}
          <div class="muted">Loading log...</div>
        {:else if logError}
          <div class="err">{logError}</div>
        {:else}
          <pre>{logText || '(empty log)'}</pre>
        {/if}
      </div>
    {/if}
  </section>
{/if}

<style>
  .detail {
    display: grid;
    gap: 1rem;
    margin-top: 1rem;
    padding: 1rem;
    border: 1px solid var(--color-line-strong);
    border-radius: calc(var(--radius-lg) - 6px);
    background: var(--color-bg-inset);
  }
  .overview {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 0.75rem;
  }
  .overview-card,
  .meta-item {
    display: grid;
    gap: 0.25rem;
    padding: 0.85rem 0.95rem;
    border: 1px solid var(--color-line);
    border-radius: var(--radius-md);
    background: var(--color-bg-panel);
  }
  .meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.75rem;
    margin-top: 0.85rem;
  }
  .k {
    font-size: 0.7rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .v {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--color-text);
    overflow-wrap: anywhere;
  }
  .head-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }
  .section-copy-block {
    display: grid;
    gap: 0.22rem;
  }
  .section-copy-block strong {
    font-size: 1rem;
    letter-spacing: -0.02em;
  }
  .prompts {
    display: grid;
    gap: 0.6rem;
  }
  .log-btn {
    padding: 0.62rem 0.95rem;
    border-radius: var(--radius-full);
    background: rgba(255, 255, 255, 0.04);
    cursor: pointer;
  }
  .raw-meta {
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 1rem;
  }
  .raw-meta summary {
    cursor: pointer;
    color: var(--color-text-secondary);
  }
  .log-wrap {
    border: 1px solid var(--color-line);
    border-radius: var(--radius-md);
    background: #06070a;
    max-height: 280px;
    overflow: auto;
    padding: 0.85rem;
  }
  pre {
    margin: 0;
    font-size: 0.8rem;
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--color-text-secondary);
  }
  .muted,
  .empty {
    color: var(--color-text-secondary);
    font-size: 0.85rem;
  }
  .err {
    color: var(--color-failed);
    font-size: 0.85rem;
  }
</style>
