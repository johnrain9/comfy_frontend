import type {
  HealthResponse,
  AutoPromptResponse,
  InputDirDefaultResponse,
  JobDetail,
  JobListItem,
  PromptPreset,
  ResolutionPresetResponse,
  SettingsPreset,
  WorkflowDef,
} from '$lib/types';

type RequestOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function ensureArray<T>(value: unknown, context: string): T[] {
  if (!Array.isArray(value)) {
    throw new Error(`Invalid API response for ${context}: expected array`);
  }
  return value as T[];
}

function ensureRecord(value: unknown, context: string): Record<string, unknown> {
  if (!isRecord(value)) {
    throw new Error(`Invalid API response for ${context}: expected object`);
  }
  return value;
}

function formatApiError(status: number, statusText: string, body: unknown): Error {
  const detail =
    isRecord(body) && body.detail !== undefined
      ? String(body.detail)
      : typeof body === 'string' && body.trim()
      ? body.trim()
      : `${status} ${statusText}`;
  return new Error(detail);
}

async function jfetch<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
): Promise<T> {
  const timeoutMs = Number(options.timeoutMs || 15_000);
  const controller = new AbortController();
  const upstream = options.signal ?? init.signal;
  let upstreamAbortHandler: (() => void) | null = null;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  if (upstream) {
    if (upstream.aborted) {
      controller.abort((upstream as AbortSignal & { reason?: unknown }).reason);
    } else {
      upstreamAbortHandler = () => controller.abort((upstream as AbortSignal & { reason?: unknown }).reason);
      upstream.addEventListener('abort', upstreamAbortHandler, { once: true });
    }
  }

  if (Number.isFinite(timeoutMs) && timeoutMs > 0) {
    timeoutId = setTimeout(() => controller.abort(new Error('timeout')), timeoutMs);
  }

  try {
    const res = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(init.headers || {}),
      },
    });

    const txt = await res.text();
    let body: unknown = {};
    try {
      body = txt ? JSON.parse(txt) : {};
    } catch {
      body = txt;
    }

    if (!res.ok) {
      throw formatApiError(res.status, res.statusText, body);
    }
    return body as T;
  } catch (err) {
    if (controller.signal.aborted) {
      if (upstream && upstream.aborted) {
        throw err;
      }
      throw new Error(`Request timed out after ${timeoutMs}ms`);
    }
    throw err instanceof Error ? err : new Error(String(err));
  } finally {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
    }
    if (upstream && upstreamAbortHandler) {
      upstream.removeEventListener('abort', upstreamAbortHandler);
    }
  }
}

export const api = {
  workflows: async (options: RequestOptions = {}) => {
    const out = await jfetch<unknown>('/api/workflows', {}, options);
    return ensureArray<WorkflowDef>(out, '/api/workflows');
  },
  resolutionPresets: async (options: RequestOptions = {}) => {
    const out = await jfetch<unknown>('/api/resolution-presets', {}, options);
    const body = ensureRecord(out, '/api/resolution-presets');
    if (!Array.isArray(body.presets)) {
      throw new Error('Invalid API response for /api/resolution-presets: expected presets[]');
    }
    return {
      presets: body.presets as ResolutionPresetResponse['presets'],
    };
  },
  defaultInputDir: async (options: RequestOptions = {}) => {
    const out = await jfetch<unknown>('/api/input-dirs/default', {}, options);
    const body = ensureRecord(out, '/api/input-dirs/default');
    if (typeof body.default_path !== 'string' || typeof body.exists !== 'boolean') {
      throw new Error('Invalid API response for /api/input-dirs/default');
    }
    return {
      default_path: body.default_path,
      exists: body.exists,
    } as InputDirDefaultResponse;
  },
  normalizeInputDir: async (path: string, options: RequestOptions = {}) => {
    const out = await jfetch<unknown>(
      '/api/input-dirs/normalize',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      },
      options,
    );
    const body = ensureRecord(out, '/api/input-dirs/normalize');
    if (typeof body.normalized_path !== 'string') {
      throw new Error('Invalid API response for /api/input-dirs/normalize');
    }
    return body as { normalized_path: string };
  },
  health: async (options: RequestOptions = {}) => {
    const out = await jfetch<unknown>('/api/health', {}, options);
    const body = ensureRecord(out, '/api/health');
    if (!('comfy' in body) || !('worker' in body) || !('pending' in body) || !('running' in body)) {
      throw new Error('Invalid API response for /api/health: missing required keys');
    }
    return {
      comfy: Boolean(body.comfy),
      worker: String(body.worker ?? ''),
      pending: Number(body.pending ?? 0),
      running: Number(body.running ?? 0),
    } as HealthResponse;
  },
  jobs: async (options: RequestOptions = {}) => {
    const out = await jfetch<unknown>('/api/jobs', {}, options);
    return ensureArray<JobListItem>(out, '/api/jobs');
  },
  jobDetail: async (id: number, options: RequestOptions = {}) => {
    const out = await jfetch<unknown>(`/api/jobs/${id}`, {}, options);
    const body = ensureRecord(out, `/api/jobs/${id}`);
    if (!Array.isArray(body.prompts)) {
      throw new Error(`Invalid API response for /api/jobs/${id}: missing prompts[]`);
    }
    return {
      job: ensureRecord(body.job, `/api/jobs/${id}.job`),
      prompts: body.prompts as JobDetail['prompts'],
    };
  },
  jobLog: async (id: number, options: RequestOptions = {}) => {
    const timeoutMs = Number(options.timeoutMs || 15_000);
    const controller = new AbortController();
    const upstream = options.signal;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let upstreamAbortHandler: (() => void) | null = null;

    if (upstream) {
      if (upstream.aborted) controller.abort();
      else {
        upstreamAbortHandler = () => controller.abort();
        upstream.addEventListener('abort', upstreamAbortHandler, { once: true });
      }
    }
    timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(`/api/jobs/${id}/log`, { signal: controller.signal });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.text();
    } finally {
      if (timeoutId !== null) clearTimeout(timeoutId);
      if (upstream && upstreamAbortHandler) upstream.removeEventListener('abort', upstreamAbortHandler);
    }
  },
  submitJob: (payload: Record<string, unknown>, options: RequestOptions = {}) =>
    jfetch<Record<string, unknown>>(
      '/api/jobs',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      options,
    ),
  pause: (options: RequestOptions = {}) => jfetch('/api/queue/pause', { method: 'POST' }, options),
  resume: (options: RequestOptions = {}) => jfetch('/api/queue/resume', { method: 'POST' }, options),
  clearQueue: (options: RequestOptions = {}) => jfetch('/api/queue/clear', { method: 'POST' }, options),
  cancelJob: (id: number, options: RequestOptions = {}) => jfetch(`/api/jobs/${id}/cancel`, { method: 'POST' }, options),
  retryJob: (id: number, options: RequestOptions = {}) => jfetch(`/api/jobs/${id}/retry`, { method: 'POST' }, options),
  reloadWorkflows: (options: RequestOptions = {}) => jfetch('/api/reload/workflows', { method: 'POST' }, options),
  reloadLoras: (options: RequestOptions = {}) => jfetch('/api/reload/loras', { method: 'POST' }, options),
  promptPresets: async (mode: string, options: RequestOptions = {}) => {
    const out = await jfetch<unknown>(`/api/prompt-presets?mode=${encodeURIComponent(mode)}`, {}, options);
    const body = ensureRecord(out, '/api/prompt-presets');
    if (!Array.isArray(body.items)) throw new Error('Invalid API response for /api/prompt-presets: items[]');
    return body as { items: PromptPreset[] };
  },
  savePromptPreset: (
    payload: { name: string; mode: string; positive_prompt: string; negative_prompt: string },
    options: RequestOptions = {},
  ) =>
    jfetch<PromptPreset>(
      '/api/prompt-presets',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      options,
    ),
  settingsPresets: async (options: RequestOptions = {}) => {
    const out = await jfetch<unknown>('/api/settings-presets', {}, options);
    const body = ensureRecord(out, '/api/settings-presets');
    if (!Array.isArray(body.items)) throw new Error('Invalid API response for /api/settings-presets: items[]');
    return body as { items: SettingsPreset[] };
  },
  saveSettingsPreset: (payload: { name: string; payload: Record<string, unknown> }, options: RequestOptions = {}) =>
    jfetch<SettingsPreset>(
      '/api/settings-presets',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      options,
    ),
  uploadInputImage: async (file: File, subdir: string, options: RequestOptions = {}) => {
    const buf = await file.arrayBuffer();
    return jfetch<{ path: string; dir: string }>(
      '/api/upload/input-image',
      {
        method: 'POST',
        headers: {
          'x-filename': file.name,
          'x-subdir': subdir,
        },
        body: buf,
      },
      options,
    );
  },
  autoPromptCapability: (lmstudioUrl?: string, options: RequestOptions = {}) =>
    jfetch<Record<string, unknown>>(
      `/api/auto-prompt/capability${lmstudioUrl ? `?lmstudio_url=${encodeURIComponent(lmstudioUrl)}` : ''}`,
      {},
      options,
    ),
  autoPrompt: (
    payload: {
      image_paths: string[];
      workflow_name: string;
      stage: 'caption' | 'motion' | 'both';
      captions?: Record<string, string>;
      system_prompt_override?: string | null;
      lmstudio_url?: string | null;
    },
    options: RequestOptions = {},
  ) =>
    jfetch<AutoPromptResponse>(
      '/api/auto-prompt',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      options,
    ),
};
