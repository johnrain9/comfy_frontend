export type WorkflowCategory = 'video_gen' | 'image_gen' | 'video_upscale' | 'image_upscale';

export interface WorkflowParamDef {
  label: string;
  type: 'text' | 'int' | 'float' | 'bool';
  default: string | number | boolean;
  min: number | null;
  max: number | null;
}

export interface WorkflowDef {
  name: string;
  display_name: string;
  group: string;
  category: WorkflowCategory;
  description: string;
  input_type: 'none' | 'image' | 'video';
  input_extensions: string[];
  supports_resolution: boolean;
  parameters: Record<string, WorkflowParamDef>;
}

export interface ResolutionPreset {
  id: string;
  label: string;
  width: number;
  height: number;
}

export interface ResolutionPresetResponse {
  presets: ResolutionPreset[];
}

export interface HealthResponse {
  comfy: boolean;
  worker: string;
  pending: number;
  running: number;
}

export interface JobListItem {
  id: number;
  name: string;
  workflow_name: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_summary: string | null;
  pending_count: number;
  running_count: number;
  succeeded_count: number;
  failed_count: number;
  canceled_count: number;
  prompt_count: number;
}

export interface JobPromptRow {
  id: number;
  status: string;
  prompt_id: string | null;
  seed_used: number | null;
  input_file: string;
  output_paths: string;
  prompt_json: string;
  error_detail: string | null;
}

export interface JobDetail {
  job: Record<string, unknown>;
  prompts: JobPromptRow[];
}

export interface PromptPreset {
  name: string;
  mode: string;
  positive_prompt: string;
  negative_prompt: string;
  updated_at: string;
}

export interface SettingsPreset {
  name: string;
  payload: Record<string, unknown>;
  updated_at: string;
}

export interface AutoPromptItem {
  path: string;
  caption?: string;
  motion_prompt?: string;
  motion_prompts?: Record<string, string>;
}

export interface AutoPromptResponse {
  items: AutoPromptItem[];
  stage1_model: string;
  stage2_model: string;
  elapsed_seconds: number;
  workflow_context: Record<string, unknown>;
}

export interface InputDirDefaultResponse {
  default_path: string;
  exists: boolean;
}
