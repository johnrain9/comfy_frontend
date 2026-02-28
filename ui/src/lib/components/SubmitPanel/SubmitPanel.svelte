<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { api } from '$lib/api';
  import type { PromptPreset, SettingsPreset, WorkflowDef, WorkflowParamDef } from '$lib/types';
  import DropZone from './DropZone.svelte';
  import ParamFields from './ParamFields.svelte';
  import ResolutionPicker from './ResolutionPicker.svelte';
  import { updateWorkspace, workspaceState } from '$lib/stores/workspace';

  export let workflows: WorkflowDef[] = [];
  export let onSubmitted: () => Promise<void>;

  type ModeTab = 'batch' | 'image_gen' | 'upscale' | 'upscale_images';

  const TAB_TO_CATEGORY: Record<ModeTab, WorkflowDef['category']> = {
    batch: 'video_gen',
    image_gen: 'image_gen',
    upscale: 'video_upscale',
    upscale_images: 'image_upscale',
  };

  const TAB_TO_MODE: Record<ModeTab, string> = {
    batch: 'video_gen',
    image_gen: 'image_gen',
    upscale: 'video_upscale',
    upscale_images: 'image_upscale',
  };

  const IMAGE_ACCEPT = '.png,.jpg,.jpeg,.webp,.bmp';

  let resolutionPresets: Array<{ id: string; label: string; width: number; height: number }> = [];
  let promptPresets: PromptPreset[] = [];
  let settingsPresets: SettingsPreset[] = [];
  let submitMsg = '';
  let submitting = false;
  let loadingMeta = false;
  let thumbnailUrls: string[] = [];
  let lastPromptMode = '';

  $: activeWs =
    $workspaceState.workspaces.find((w) => w.id === $workspaceState.active_workspace_id) ??
    $workspaceState.workspaces[0] ??
    null;

  $: activeTab = (activeWs?.active_tab ?? 'batch') as ModeTab;
  $: filteredWorkflows = workflows.filter((w) => w.category === TAB_TO_CATEGORY[activeTab]);
  $: selectedWorkflow = filteredWorkflows.find((w) => w.name === activeWs?.workflow_name) ?? filteredWorkflows[0] ?? null;

  $: if (activeWs && selectedWorkflow && activeWs.workflow_name !== selectedWorkflow.name) {
    patchWorkspace({ workflow_name: selectedWorkflow.name });
  }

  $: if (activeWs && selectedWorkflow) {
    const existing = activeWs.params_by_workflow[selectedWorkflow.name];
    if (!existing) {
      const next = {
        ...activeWs.params_by_workflow,
        [selectedWorkflow.name]: defaultsForWorkflow(selectedWorkflow),
      };
      patchWorkspace({ params_by_workflow: next });
    }
  }

  $: currentParams =
    (activeWs && selectedWorkflow
      ? activeWs.params_by_workflow[selectedWorkflow.name]
      : {}) || {};

  $: promptMode = TAB_TO_MODE[activeTab];
  $: if (promptMode && promptMode !== lastPromptMode) {
    lastPromptMode = promptMode;
    void refreshPromptPresets(promptMode);
  }

  $: allowImageDrop =
    !!selectedWorkflow &&
    selectedWorkflow.input_type === 'image' &&
    !(activeTab === 'image_gen' && activeWs?.image_gen_source_mode === 't2i');

  $: inputRequired =
    !!selectedWorkflow &&
    selectedWorkflow.input_type !== 'none' &&
    !(activeTab === 'image_gen' && activeWs?.image_gen_source_mode === 't2i');

  $: effectiveInputDir = (activeWs?.dropped_input_dir || activeWs?.input_dir || '').trim();

  function patchWorkspace(patch: Record<string, unknown>): void {
    if (!activeWs) return;
    updateWorkspace(activeWs.id, patch);
  }

  function defaultsForWorkflow(workflow: WorkflowDef): Record<string, unknown> {
    const out: Record<string, unknown> = {};
    for (const [name, def] of Object.entries(workflow.parameters || {})) {
      out[name] = def.default;
    }
    return out;
  }

  function setTab(tab: ModeTab): void {
    patchWorkspace({ active_tab: tab, workflow_name: '', prompt_preset_name: '' });
    submitMsg = '';
  }

  function setWorkflow(name: string): void {
    if (!activeWs) return;
    const wf = filteredWorkflows.find((w) => w.name === name);
    if (!wf) return;
    const hasParams = activeWs.params_by_workflow[wf.name];
    patchWorkspace({
      workflow_name: wf.name,
      params_by_workflow: hasParams
        ? activeWs.params_by_workflow
        : {
            ...activeWs.params_by_workflow,
            [wf.name]: defaultsForWorkflow(wf),
          },
    });
  }

  function patchParam(name: string, value: unknown): void {
    if (!activeWs || !selectedWorkflow) return;
    const byWorkflow = { ...activeWs.params_by_workflow };
    byWorkflow[selectedWorkflow.name] = {
      ...(byWorkflow[selectedWorkflow.name] || {}),
      [name]: value,
    };
    patchWorkspace({ params_by_workflow: byWorkflow });
  }

  function cleanupThumbs(): void {
    for (const url of thumbnailUrls) {
      if (url.startsWith('blob:')) URL.revokeObjectURL(url);
    }
    thumbnailUrls = [];
  }

  onDestroy(() => {
    cleanupThumbs();
    window.removeEventListener('keydown', onKeyDown);
  });

  async function loadMetadata(): Promise<void> {
    loadingMeta = true;
    try {
      const [resolutionResp, settingsResp] = await Promise.all([
        api.resolutionPresets(),
        api.settingsPresets(),
      ]);
      resolutionPresets = resolutionResp.presets;
      settingsPresets = settingsResp.items;

      if (activeWs && !activeWs.input_dir.trim()) {
        const d = await api.defaultInputDir();
        if (d.exists) {
          patchWorkspace({ input_dir: d.default_path });
        }
      }
    } catch (error) {
      submitMsg = error instanceof Error ? error.message : String(error);
    } finally {
      loadingMeta = false;
    }
  }

  onMount(() => {
    void loadMetadata();
    window.addEventListener('keydown', onKeyDown);
  });

  async function refreshPromptPresets(mode: string): Promise<void> {
    try {
      const response = await api.promptPresets(mode);
      promptPresets = response.items;
    } catch (error) {
      submitMsg = error instanceof Error ? error.message : String(error);
    }
  }

  async function refreshSettingsPresets(): Promise<void> {
    try {
      const response = await api.settingsPresets();
      settingsPresets = response.items;
    } catch (error) {
      submitMsg = error instanceof Error ? error.message : String(error);
    }
  }

  async function handleDrop(files: File[]): Promise<void> {
    if (!files.length || !activeWs) return;

    cleanupThumbs();
    thumbnailUrls = files.slice(0, 16).map((file) => URL.createObjectURL(file));

    const subdir = `uploads/v2/${activeWs.id}/${Date.now()}`;
    let uploadedDir = '';
    try {
      for (const file of files) {
        const uploaded = await api.uploadInputImage(file, subdir, { timeoutMs: 30_000 });
        uploadedDir = uploaded.dir;
      }
    } catch (error) {
      submitMsg = error instanceof Error ? error.message : String(error);
      return;
    }

    if (uploadedDir) {
      patchWorkspace({ input_dir: uploadedDir, dropped_input_dir: uploadedDir });
      submitMsg = `Uploaded ${files.length} file(s) to ${uploadedDir}`;
    }
  }

  function clearDropped(): void {
    cleanupThumbs();
    patchWorkspace({ dropped_input_dir: '' });
    submitMsg = 'Dropped file set cleared.';
  }

  function normalizeParam(def: WorkflowParamDef, raw: unknown): unknown {
    if (def.type === 'bool') return Boolean(raw);
    if (def.type === 'int' || def.type === 'float') {
      const parsed =
        typeof raw === 'number'
          ? raw
          : def.type === 'float'
          ? Number.parseFloat(String(raw ?? ''))
          : Number.parseInt(String(raw ?? ''), 10);
      if (!Number.isFinite(parsed)) return def.default;
      let next = parsed;
      if (typeof def.min === 'number') next = Math.max(def.min, next);
      if (typeof def.max === 'number') next = Math.min(def.max, next);
      return def.type === 'int' ? Math.trunc(next) : next;
    }
    return raw === undefined || raw === null ? '' : String(raw);
  }

  function buildParams(workflow: WorkflowDef, values: Record<string, unknown>): Record<string, unknown> {
    const out: Record<string, unknown> = {};
    for (const [name, def] of Object.entries(workflow.parameters || {})) {
      out[name] = normalizeParam(def, values[name]);
    }
    return out;
  }

  async function savePromptPreset(): Promise<void> {
    if (!activeWs || !selectedWorkflow) return;
    const name = window.prompt('Prompt preset name');
    if (!name || !name.trim()) return;

    const positive = String(currentParams.positive_prompt ?? '');
    const negative = String(currentParams.negative_prompt ?? '');

    try {
      await api.savePromptPreset({
        name: name.trim(),
        mode: promptMode,
        positive_prompt: positive,
        negative_prompt: negative,
      });
      await refreshPromptPresets(promptMode);
      patchWorkspace({ prompt_preset_name: name.trim() });
      submitMsg = `Saved prompt preset "${name.trim()}".`;
    } catch (error) {
      submitMsg = error instanceof Error ? error.message : String(error);
    }
  }

  function applyPromptPreset(): void {
    if (!activeWs || !selectedWorkflow) return;
    const presetName = activeWs.prompt_preset_name;
    if (!presetName) {
      submitMsg = 'Select a prompt preset first.';
      return;
    }
    const preset = promptPresets.find((item) => item.name === presetName);
    if (!preset) {
      submitMsg = `Prompt preset "${presetName}" not found.`;
      return;
    }

    const byWorkflow = { ...activeWs.params_by_workflow };
    byWorkflow[selectedWorkflow.name] = {
      ...(byWorkflow[selectedWorkflow.name] || {}),
      positive_prompt: preset.positive_prompt,
      negative_prompt: preset.negative_prompt,
    };

    patchWorkspace({ params_by_workflow: byWorkflow });
    submitMsg = `Applied prompt preset "${preset.name}".`;
  }

  async function saveSettingsPreset(): Promise<void> {
    if (!activeWs || !selectedWorkflow) return;
    const name = window.prompt('Settings preset name');
    if (!name || !name.trim()) return;

    const payload: Record<string, unknown> = {
      active_tab: activeWs.active_tab,
      workflow_name: selectedWorkflow.name,
      resolution_preset: activeWs.resolution_preset,
      flip_orientation: activeWs.flip_orientation,
      move_processed: activeWs.move_processed,
      input_dir: activeWs.input_dir,
      image_gen_source_mode: activeWs.image_gen_source_mode,
      params_by_workflow: activeWs.params_by_workflow,
    };

    try {
      await api.saveSettingsPreset({ name: name.trim(), payload });
      await refreshSettingsPresets();
      patchWorkspace({ settings_preset_name: name.trim() });
      submitMsg = `Saved settings preset "${name.trim()}".`;
    } catch (error) {
      submitMsg = error instanceof Error ? error.message : String(error);
    }
  }

  function applySettingsPreset(): void {
    if (!activeWs) return;
    const selected = settingsPresets.find((item) => item.name === activeWs.settings_preset_name);
    if (!selected) {
      submitMsg = 'Select a settings preset first.';
      return;
    }

    const payload = selected.payload || {};
    const patch: Record<string, unknown> = {};

    if (payload.active_tab === 'batch' || payload.active_tab === 'image_gen' || payload.active_tab === 'upscale' || payload.active_tab === 'upscale_images') {
      patch.active_tab = payload.active_tab;
    }
    if (typeof payload.workflow_name === 'string') patch.workflow_name = payload.workflow_name;
    if (typeof payload.resolution_preset === 'string') patch.resolution_preset = payload.resolution_preset;
    if (typeof payload.flip_orientation === 'boolean') patch.flip_orientation = payload.flip_orientation;
    if (typeof payload.move_processed === 'boolean') patch.move_processed = payload.move_processed;
    if (typeof payload.input_dir === 'string') patch.input_dir = payload.input_dir;
    if (payload.image_gen_source_mode === 't2i' || payload.image_gen_source_mode === 'i2i') {
      patch.image_gen_source_mode = payload.image_gen_source_mode;
    }
    if (payload.params_by_workflow && typeof payload.params_by_workflow === 'object') {
      patch.params_by_workflow = payload.params_by_workflow;
    }

    patchWorkspace(patch);
    submitMsg = `Applied settings preset "${selected.name}".`;
  }

  async function submit(): Promise<void> {
    if (!activeWs || !selectedWorkflow) {
      submitMsg = 'Choose a workflow first.';
      return;
    }

    if (inputRequired && !effectiveInputDir) {
      submitMsg = 'This workflow requires input files. Set Input Dir or use upload.';
      return;
    }

    const payload: Record<string, unknown> = {
      workflow_name: selectedWorkflow.name,
      job_name: activeWs.job_name.trim() || null,
      input_dir: selectedWorkflow.input_type === 'none' ? '' : effectiveInputDir,
      params: buildParams(selectedWorkflow, currentParams),
      resolution_preset: selectedWorkflow.supports_resolution ? activeWs.resolution_preset || null : null,
      flip_orientation: Boolean(activeWs.flip_orientation),
      move_processed: Boolean(activeWs.move_processed),
      split_by_input: !(activeTab === 'image_gen' && activeWs.image_gen_source_mode === 't2i'),
    };

    submitting = true;
    submitMsg = '';
    try {
      const result = await api.submitJob(payload, { timeoutMs: 45_000 });
      const jobCount = Number(result.job_count || (result.job_id ? 1 : 0));
      const promptCount = Number(result.prompt_count || 0);
      submitMsg = `Submitted ${jobCount} job(s), ${promptCount} prompt(s).`;
      await onSubmitted();
    } catch (error) {
      submitMsg = error instanceof Error ? error.message : String(error);
    } finally {
      submitting = false;
    }
  }

  function onKeyDown(event: KeyboardEvent): void {
    const target = event.target as HTMLElement | null;
    const inEditable =
      !!target &&
      (target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.getAttribute('contenteditable') === 'true');

    if (event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
      if (event.key === '1') {
        event.preventDefault();
        setTab('batch');
      } else if (event.key === '2') {
        event.preventDefault();
        setTab('image_gen');
      } else if (event.key === '3') {
        event.preventDefault();
        setTab('upscale');
      } else if (event.key === '4') {
        event.preventDefault();
        setTab('upscale_images');
      }
      return;
    }

    if (event.ctrlKey && event.key === 'Enter') {
      if (inEditable || target === document.body) {
        event.preventDefault();
        void submit();
      }
    }
  }
</script>

<section class="panel p-3" aria-label="Submit Panel">
  <div class="tabs" role="tablist" aria-label="Modes">
    <button id="modeBatch" class:active={activeTab === 'batch'} on:click={() => setTab('batch')}>Batch</button>
    <button id="modeImageGen" class:active={activeTab === 'image_gen'} on:click={() => setTab('image_gen')}>Image Gen</button>
    <button id="modeUpscale" class:active={activeTab === 'upscale'} on:click={() => setTab('upscale')}>Upscale Video</button>
    <button id="modeUpscaleImg" class:active={activeTab === 'upscale_images'} on:click={() => setTab('upscale_images')}>Upscale Image</button>
  </div>
  <div class="shortcut-hint">Shortcuts: <code>Alt+1..4</code> switch mode, <code>Ctrl+Enter</code> submit.</div>

  <div class="grid2">
    <div class="left">
      <div class="field-grid">
        <label for="workflowSelect">Workflow</label>
        <select
          id="workflowSelect"
          value={selectedWorkflow?.name || ''}
          on:change={(event) => setWorkflow((event.target as HTMLSelectElement).value)}
        >
          {#each filteredWorkflows as wf}
            <option value={wf.name}>{wf.display_name}</option>
          {/each}
        </select>

        <label for="resolutionSelect">Resolution</label>
        <ResolutionPicker
          id="resolutionSelect"
          value={activeWs?.resolution_preset || ''}
          presets={resolutionPresets}
          disabled={loadingMeta || !selectedWorkflow?.supports_resolution}
          on:change={(event) => patchWorkspace({ resolution_preset: event.detail })}
        />

        {#if activeTab === 'image_gen'}
          <label for="imageGenSource">Image Gen source</label>
          <select
            id="imageGenSource"
            value={activeWs?.image_gen_source_mode || 't2i'}
            on:change={(event) => patchWorkspace({ image_gen_source_mode: (event.target as HTMLSelectElement).value })}
          >
            <option value="t2i">T2I</option>
            <option value="i2i">I2I</option>
          </select>
        {/if}

        <label for="inputDir">Input directory</label>
        <input
          id="inputDir"
          type="text"
          value={activeWs?.input_dir || ''}
          placeholder="/home/cobra/ComfyUI/input"
          on:input={(event) => patchWorkspace({ input_dir: (event.target as HTMLInputElement).value })}
        />

        <label for="jobName">Job name</label>
        <input
          id="jobName"
          type="text"
          value={activeWs?.job_name || ''}
          placeholder="optional"
          on:input={(event) => patchWorkspace({ job_name: (event.target as HTMLInputElement).value })}
        />
      </div>

      <div class="checks">
        <label><input id="flipOrientation" type="checkbox" checked={Boolean(activeWs?.flip_orientation)} on:change={(event) => patchWorkspace({ flip_orientation: (event.target as HTMLInputElement).checked })} /> Flip orientation</label>
        <label><input id="moveProcessed" type="checkbox" checked={Boolean(activeWs?.move_processed)} on:change={(event) => patchWorkspace({ move_processed: (event.target as HTMLInputElement).checked })} /> Move processed to <code>_processed</code></label>
      </div>

      <div class="preset-row">
        <label for="promptPresetSelect">Prompt preset</label>
        <select
          id="promptPresetSelect"
          value={activeWs?.prompt_preset_name || ''}
          on:change={(event) => patchWorkspace({ prompt_preset_name: (event.target as HTMLSelectElement).value })}
        >
          <option value="">(none)</option>
          {#each promptPresets as preset}
            <option value={preset.name}>{preset.name}</option>
          {/each}
        </select>
        <button on:click={savePromptPreset}>Save</button>
        <button on:click={applyPromptPreset}>Apply</button>
      </div>

      <div class="preset-row">
        <label for="settingsPresetSelect">Settings preset</label>
        <select
          id="settingsPresetSelect"
          value={activeWs?.settings_preset_name || ''}
          on:change={(event) => patchWorkspace({ settings_preset_name: (event.target as HTMLSelectElement).value })}
        >
          <option value="">(none)</option>
          {#each settingsPresets as preset}
            <option value={preset.name}>{preset.name}</option>
          {/each}
        </select>
        <button on:click={saveSettingsPreset}>Save</button>
        <button on:click={applySettingsPreset}>Apply</button>
      </div>

      <div class="submit-row">
        <button id="submitBtn" class="primary" disabled={submitting} on:click={submit}>Submit</button>
        <button id="clearDropBtn" disabled={!thumbnailUrls.length} on:click={clearDropped}>Clear dropped set</button>
        <span id="submitMsg">{submitMsg}</span>
      </div>
    </div>

    <div class="right">
      <ParamFields
        id="paramFields"
        params={selectedWorkflow?.parameters || {}}
        values={currentParams}
        disabled={submitting}
        on:change={(event) => patchParam(event.detail.name, event.detail.value)}
      />

      <DropZone
        id="dropZone"
        inputId="fileInput"
        thumbsId="thumbs"
        visible={allowImageDrop}
        label="Drop image files for upload"
        thumbnails={thumbnailUrls}
        accept={IMAGE_ACCEPT}
        disabled={submitting}
        on:files={(event) => handleDrop(event.detail)}
      />
    </div>
  </div>
</section>

<style>
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 10px;
  }
  .tabs button {
    background: #111f34;
    border: 1px solid #2f4a72;
    color: #e7efff;
    border-radius: 8px;
    padding: 6px 10px;
    cursor: pointer;
  }
  .tabs button.active {
    background: #1b2f4d;
    border-color: #4f79b8;
  }

  .grid2 {
    display: grid;
    grid-template-columns: minmax(440px, 1.35fr) minmax(300px, 1fr);
    gap: 10px;
  }
  .shortcut-hint {
    color: #8ba6cb;
    font-size: 11px;
    margin-bottom: 8px;
  }
  .left,
  .right {
    display: grid;
    gap: 10px;
    align-content: start;
  }

  .field-grid {
    display: grid;
    grid-template-columns: 130px 1fr;
    gap: 8px;
    align-items: center;
  }

  input,
  select,
  button {
    background: #0a1322;
    border: 1px solid #2f4a72;
    color: #e7efff;
    border-radius: 8px;
    padding: 6px;
  }

  .checks {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    color: #c6d7f3;
    font-size: 13px;
  }

  .checks label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .preset-row {
    display: grid;
    grid-template-columns: 130px 1fr auto auto;
    gap: 8px;
    align-items: center;
  }

  .submit-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }

  .submit-row span {
    font-size: 12px;
    color: #9bb2d3;
  }

  .primary {
    background: #1d3354;
    border-color: #4f79b8;
  }

  button:disabled {
    opacity: 0.55;
    cursor: default;
  }

  @media (max-width: 1100px) {
    .grid2 {
      grid-template-columns: 1fr;
    }
    .field-grid,
    .preset-row {
      grid-template-columns: 1fr;
    }
  }
</style>
