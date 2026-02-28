import { writable } from 'svelte/store';

export interface WorkspaceState {
  id: string;
  name: string;
  active_tab: 'batch' | 'image_gen' | 'upscale' | 'upscale_images';
  workflow_name: string;
  resolution_preset: string;
  flip_orientation: boolean;
  move_processed: boolean;
  input_dir: string;
  job_name: string;
  image_gen_source_mode: 't2i' | 'i2i';
  prompt_mode: 'manual' | 'per-image manual' | 'per-image auto';
  params_by_workflow: Record<string, Record<string, unknown>>;
  per_file_params: Record<string, Record<string, unknown>>;
  dropped_input_dir: string;
  dropped_input_paths: string[];
  prompt_preset_name: string;
  settings_preset_name: string;
}

export interface WorkspaceStoreState {
  active_workspace_id: string;
  workspaces: WorkspaceState[];
}

export const STORAGE_KEY = 'video_queue_ui_v2_state';

function mkWorkspace(n: number): WorkspaceState {
  return {
    id: `ws-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: `Workspace ${n}`,
    active_tab: 'batch',
    workflow_name: '',
    resolution_preset: '768x1360',
    flip_orientation: false,
    move_processed: false,
    input_dir: '',
    job_name: '',
    image_gen_source_mode: 't2i',
    prompt_mode: 'manual',
    params_by_workflow: {},
    per_file_params: {},
    dropped_input_dir: '',
    dropped_input_paths: [],
    prompt_preset_name: '',
    settings_preset_name: '',
  };
}

function normalizeWorkspace(raw: Partial<WorkspaceState> | null | undefined, n: number): WorkspaceState {
  const base = mkWorkspace(n);
  const src = raw ?? {};
  return {
    ...base,
    ...src,
    id: typeof src.id === 'string' && src.id.trim() ? src.id : base.id,
    name: typeof src.name === 'string' && src.name.trim() ? src.name : base.name,
    active_tab:
      src.active_tab === 'batch' ||
      src.active_tab === 'image_gen' ||
      src.active_tab === 'upscale' ||
      src.active_tab === 'upscale_images'
        ? src.active_tab
        : base.active_tab,
    image_gen_source_mode: src.image_gen_source_mode === 'i2i' ? 'i2i' : 't2i',
    prompt_mode:
      src.prompt_mode === 'per-image manual' || src.prompt_mode === 'per-image auto'
        ? src.prompt_mode
        : 'manual',
    params_by_workflow:
      src.params_by_workflow && typeof src.params_by_workflow === 'object'
        ? src.params_by_workflow
        : base.params_by_workflow,
    per_file_params:
      src.per_file_params && typeof src.per_file_params === 'object'
        ? src.per_file_params
        : base.per_file_params,
    dropped_input_paths: Array.isArray(src.dropped_input_paths)
      ? src.dropped_input_paths.map((v) => String(v))
      : base.dropped_input_paths,
    prompt_preset_name: typeof src.prompt_preset_name === 'string' ? src.prompt_preset_name : base.prompt_preset_name,
    settings_preset_name:
      typeof src.settings_preset_name === 'string' ? src.settings_preset_name : base.settings_preset_name,
  };
}

function loadState(): WorkspaceStoreState {
  if (typeof window === 'undefined') return { active_workspace_id: '', workspaces: [mkWorkspace(1)] };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      const ws = mkWorkspace(1);
      return { active_workspace_id: ws.id, workspaces: [ws] };
    }
    const p = JSON.parse(raw) as Partial<WorkspaceStoreState>;
    const normalized = Array.isArray(p?.workspaces) ? p.workspaces.map((w, idx) => normalizeWorkspace(w, idx + 1)) : [];
    if (!normalized.length) throw new Error('bad');
    const activeId =
      typeof p?.active_workspace_id === 'string' && normalized.some((w) => w.id === p.active_workspace_id)
        ? p.active_workspace_id
        : normalized[0].id;
    return { active_workspace_id: activeId, workspaces: normalized };
  } catch {
    const ws = mkWorkspace(1);
    return { active_workspace_id: ws.id, workspaces: [ws] };
  }
}

export const workspaceState = writable<WorkspaceStoreState>(loadState());

workspaceState.subscribe((s) => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    // ignore storage failures
  }
});

export function createWorkspace(): void {
  workspaceState.update((s) => {
    const ws = mkWorkspace(s.workspaces.length + 1);
    return { active_workspace_id: ws.id, workspaces: [...s.workspaces, ws] };
  });
}

export function renameWorkspace(id: string, name: string): void {
  workspaceState.update((s) => ({
    ...s,
    workspaces: s.workspaces.map((w) => (w.id === id ? { ...w, name: name.trim() || w.name } : w)),
  }));
}

export function closeWorkspace(id: string): void {
  workspaceState.update((s) => {
    if (s.workspaces.length <= 1) return s;
    const next = s.workspaces.filter((w) => w.id !== id);
    const active = s.active_workspace_id === id ? next[Math.max(0, next.length - 1)].id : s.active_workspace_id;
    return { active_workspace_id: active, workspaces: next };
  });
}

export function setActiveWorkspace(id: string): void {
  workspaceState.update((s) => ({ ...s, active_workspace_id: id }));
}

export function updateWorkspace(id: string, patch: Partial<WorkspaceState>): void {
  workspaceState.update((s) => ({
    ...s,
    workspaces: s.workspaces.map((w) => (w.id === id ? { ...w, ...patch } : w)),
  }));
}
