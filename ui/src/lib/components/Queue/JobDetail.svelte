<script lang="ts">
  import PromptRow from './PromptRow.svelte';
  import { api } from '$lib/api';
  import type { JobDetail as JobDetailType } from '$lib/types';

  export let detail: JobDetailType | null = null;

  let logVisible = false;
  let logLoading = false;
  let logText = '';
  let logError = '';

  function formatValue(value: unknown): string {
    if (value === null || value === undefined || value === '') return 'n/a';
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    }
    return String(value);
  }

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
    <div class="meta-grid">
      {#each Object.entries(detail.job) as [key, value]}
        <div class="meta-item">
          <span class="k">{key}</span>
          <span class="v">{formatValue(value)}</span>
        </div>
      {/each}
    </div>

    <div class="head-row">
      <strong>Prompts ({detail.prompts.length})</strong>
      <button class="log-btn" on:click={toggleLog}>{logVisible ? 'Hide Log' : 'View Log'}</button>
    </div>
    <div class="prompts">
      {#each detail.prompts as p}
        <PromptRow prompt={p} />
      {/each}
    </div>

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
    background: #0a1322;
    border: 1px solid #22324d;
    border-radius: 8px;
    padding: 10px;
    margin-top: 8px;
  }
  .meta-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(220px, 1fr));
    gap: 8px;
    margin-bottom: 10px;
  }
  .meta-item {
    display: grid;
    gap: 2px;
  }
  .k {
    font-size: 11px;
    color: #8ba6cb;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .v {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px;
    color: #d7e5fd;
    overflow-wrap: anywhere;
  }
  .head-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .prompts {
    display: grid;
    gap: 4px;
  }
  .log-btn {
    border: 1px solid #39537c;
    border-radius: 8px;
    background: #13253f;
    color: #e7efff;
    font-size: 12px;
    padding: 5px 9px;
    cursor: pointer;
  }
  .log-wrap {
    margin-top: 10px;
    border: 1px solid #2b4062;
    border-radius: 8px;
    background: #070d19;
    max-height: 280px;
    overflow: auto;
    padding: 8px;
  }
  pre {
    margin: 0;
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-word;
    color: #c9dcfb;
  }
  .muted {
    color: #9bb2d3;
    font-size: 12px;
  }
  .err {
    color: #ff9aa9;
    font-size: 12px;
  }
</style>
