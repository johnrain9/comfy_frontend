<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { WorkflowParamDef } from '$lib/types';

  export let id = 'paramFields';
  export let params: Record<string, WorkflowParamDef> = {};
  export let values: Record<string, unknown> = {};
  export let disabled = false;

  const dispatch = createEventDispatcher<{ change: { name: string; value: unknown } }>();

  function toNumber(value: string, float: boolean): number | null {
    const parsed = float ? Number.parseFloat(value) : Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function changed(name: string, def: WorkflowParamDef, event: Event): void {
    if (disabled) return;
    const target = event.target as HTMLInputElement | HTMLTextAreaElement;
    let next: unknown;
    if (def.type === 'bool') {
      next = (event.target as HTMLInputElement).checked;
    } else if (def.type === 'int') {
      next = toNumber(target.value, false);
    } else if (def.type === 'float') {
      next = toNumber(target.value, true);
    } else {
      next = target.value;
    }
    dispatch('change', { name, value: next });
  }

  function inputValue(name: string, def: WorkflowParamDef): string {
    const value = values[name];
    if (value === undefined || value === null) {
      return def.default === undefined || def.default === null ? '' : String(def.default);
    }
    return String(value);
  }
</script>

<div class="grid" {id}>
  {#each Object.entries(params) as [name, p]}
    <label class="field">
      <span>{p.label} <span class="n">({name})</span></span>
      {#if p.type === 'bool'}
        <input
          type="checkbox"
          checked={Boolean(values[name] ?? p.default)}
          disabled={disabled}
          data-param-name={name}
          data-param-type={p.type}
          on:change={(event) => changed(name, p, event)}
        />
      {:else if p.type === 'int' || p.type === 'float'}
        <input
          type="number"
          value={inputValue(name, p)}
          min={p.min ?? undefined}
          max={p.max ?? undefined}
          step={p.type === 'float' ? '0.01' : '1'}
          disabled={disabled}
          data-param-name={name}
          data-param-type={p.type}
          on:input={(event) => changed(name, p, event)}
        />
      {:else}
        <textarea
          rows="2"
          value={inputValue(name, p)}
          disabled={disabled}
          data-param-name={name}
          data-param-type={p.type}
          on:input={(event) => changed(name, p, event)}
        ></textarea>
      {/if}
    </label>
  {/each}
</div>

<style>
  .grid {
    display: grid;
    gap: 8px;
  }
  .field {
    display: grid;
    gap: 4px;
    font-size: 13px;
    color: #c7d8f2;
  }
  .n {
    color: #8ba6cb;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 11px;
  }
  input,
  textarea {
    background: #0a1322;
    color: #e7efff;
    border: 1px solid #2f4a72;
    border-radius: 8px;
    padding: 6px;
  }
</style>
