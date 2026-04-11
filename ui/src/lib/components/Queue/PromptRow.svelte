<script lang="ts">
  import type { JobPromptRow } from '$lib/types';
  import StatusBadge from './StatusBadge.svelte';

  export let prompt: JobPromptRow;

  function text(v: unknown): string {
    if (v === null || v === undefined || v === '') return 'n/a';
    return String(v);
  }
</script>

<div class="row">
  <div class="status">
    <StatusBadge status={prompt.status} />
    <div class="prompt-id">
      <strong>Prompt #{prompt.id}</strong>
      <span class="mono">{text(prompt.prompt_id)}</span>
    </div>
  </div>
  <div class="paths">
    <div class="line">
      <span class="k">Input</span>
      <span class="mono path">{text(prompt.input_file)}</span>
    </div>
    <div class="line">
      <span class="k">Output</span>
      <span class="mono path">{text(prompt.output_paths)}</span>
    </div>
  </div>
  <div class="meta">
    <span class="meta-label">Seed</span>
    <strong class="mono">{text(prompt.seed_used)}</strong>
  </div>
</div>

<style>
  .row {
    display: grid;
    grid-template-columns: minmax(190px, 240px) 1fr minmax(110px, 150px);
    gap: 0.9rem;
    align-items: start;
    font-size: 0.82rem;
    color: var(--color-text-secondary);
    padding: 0.82rem 0.92rem;
    border: 1px solid var(--color-line);
    border-radius: var(--radius-md);
    background: var(--color-bg-panel);
  }
  .status {
    display: grid;
    gap: 0.55rem;
  }
  .prompt-id {
    display: grid;
    gap: 0.2rem;
  }
  .prompt-id strong {
    color: var(--color-text);
    font-size: 0.92rem;
    font-weight: 600;
  }
  .paths {
    display: grid;
    gap: 0.55rem;
  }
  .line {
    display: grid;
    gap: 0.18rem;
  }
  .k,
  .meta-label {
    color: var(--color-text-muted);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .path {
    overflow-wrap: anywhere;
    color: var(--color-text);
    font-size: 0.76rem;
  }
  .meta {
    display: grid;
    gap: 0.18rem;
    justify-items: end;
    text-align: right;
  }
  .meta strong {
    color: var(--color-text);
  }

  @media (max-width: 860px) {
    .row {
      grid-template-columns: 1fr;
    }
    .meta {
      justify-items: start;
      text-align: left;
    }
  }
</style>
