<script lang="ts">
  import type { JobPromptRow } from '$lib/types';

  export let prompt: JobPromptRow;

  function iconFor(status: string): string {
    const s = String(status || '').toLowerCase();
    if (s === 'succeeded') return '✅';
    if (s === 'failed') return '❌';
    if (s === 'running') return '⏳';
    if (s === 'canceled') return '⛔';
    return '⬚';
  }

  function text(v: unknown): string {
    if (v === null || v === undefined || v === '') return 'n/a';
    return String(v);
  }
</script>

<div class="row">
  <div class="status">
    <span>{iconFor(prompt.status)}</span>
    <span>#{prompt.id}</span>
    <span class="st">{prompt.status}</span>
  </div>
  <div class="paths">
    <div class="line"><strong>in</strong> {text(prompt.input_file)}</div>
    <div class="line"><strong>out</strong> {text(prompt.output_paths)}</div>
  </div>
  <div class="meta">
    <span>seed: {text(prompt.seed_used)}</span>
    <span>pid: {text(prompt.prompt_id)}</span>
  </div>
</div>

<style>
  .row {
    display: grid;
    grid-template-columns: minmax(170px, 220px) 1fr minmax(140px, 180px);
    gap: 10px;
    font-size: 12px;
    color: #c6d7f3;
    padding: 6px 8px;
    border: 1px solid #1f324f;
    border-radius: 8px;
    background: #0d182b;
  }
  .status {
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .st {
    color: #9bb2d3;
  }
  .paths {
    display: grid;
    gap: 4px;
  }
  .line {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .line strong {
    color: #8ba6cb;
    margin-right: 6px;
  }
  .meta {
    display: grid;
    gap: 4px;
    color: #9bb2d3;
  }
</style>
