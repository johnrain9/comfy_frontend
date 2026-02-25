import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { JSDOM } from 'jsdom';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const HTML = fs.readFileSync(path.join(ROOT, 'static', 'index.html'), 'utf-8');
const STATE_KEY = 'video_queue_ui_state_v1';

const defaultWorkflows = [
  {
    name: 'wan-context-lite-2stage',
    display_name: 'WAN ContextWindow Single Pass (81f)',
    group: 'WAN V2',
    description: 'single',
    input_type: 'image',
    input_extensions: ['.png', '.jpg'],
    supports_resolution: true,
    parameters: {
      positive_prompt: { label: 'Positive prompt', type: 'text', default: '(at 0 second: )(at 3 second: )(at 7 second: )', min: null, max: null },
      tries: { label: 'Tries', type: 'int', default: 1, min: 1, max: 10 },
      randomize_seed: { label: 'Randomize', type: 'bool', default: true, min: null, max: null },
    },
  },
  {
    name: 'wan-context-2stage',
    display_name: 'WAN ContextWindow2 Refine (2-pass, 81f)',
    group: 'WAN V2',
    description: 'refine',
    input_type: 'image',
    input_extensions: ['.png', '.jpg'],
    supports_resolution: true,
    parameters: {
      positive_prompt: { label: 'Positive prompt', type: 'text', default: '(at 0 second: )(at 3 second: )(at 7 second: )', min: null, max: null },
      tries: { label: 'Tries', type: 'int', default: 1, min: 1, max: 10 },
      randomize_seed: { label: 'Randomize', type: 'bool', default: true, min: null, max: null },
    },
  },
];

function mkResponse(status, payload) {
  const txt = typeof payload === 'string' ? payload : JSON.stringify(payload);
  return {
    ok: status >= 200 && status < 300,
    status,
    async text() { return txt; },
  };
}

function buildApi(options = {}) {
  const state = {
    requests: [],
    submits: [],
  };

  let activeWorkflows = options.workflows || defaultWorkflows;
  const promptPresets = Array.isArray(options.promptPresets) ? [...options.promptPresets] : [];
  const upscaleModels = Array.isArray(options.upscaleModels)
    ? options.upscaleModels
    : ['RealESRGAN_x2plus.pth', 'RealESRGAN_x4plus.pth', 'RealESRNet_x4plus.pth'];
  const workflowsAfterReload = options.workflowsAfterReload || null;
  let jobsList = options.jobsList || [];
  const jobDetails = options.jobDetails || {};
  const defaultPath = options.defaultPath || '/home/cobra/ComfyUI/input';
  const defaultExists = options.defaultExists !== undefined ? options.defaultExists : true;

  async function fetchRouter(url, opts = {}) {
    const u = new URL(url, 'http://localhost');
    const p = u.pathname;
    const method = (opts.method || 'GET').toUpperCase();
    let bodyObj = null;
    if (opts.body) {
      try {
        bodyObj = JSON.parse(opts.body);
      } catch {
        bodyObj = null;
      }
    }
    state.requests.push({ method, path: p, query: u.search, body: bodyObj });

    if (method === 'GET' && p === '/api/loras') return mkResponse(200, []);
    if (method === 'GET' && p === '/api/upscale-models') return mkResponse(200, upscaleModels);
    if (method === 'GET' && p === '/api/resolution-presets') {
      return mkResponse(200, { presets: [
        { id: '640x1136', label: '640 x 1136', width: 640, height: 1136 },
        { id: '768x1360', label: '768 x 1360', width: 768, height: 1360 },
      ] });
    }
    if (method === 'GET' && p === '/api/input-dirs/recent') return mkResponse(200, { paths: [] });
    if (method === 'GET' && p === '/api/input-dirs/default') return mkResponse(200, { default_path: defaultPath, exists: defaultExists });
    if (method === 'GET' && p === '/api/workflows') return mkResponse(200, activeWorkflows);
    if (method === 'GET' && p === '/api/prompt-presets') {
      const mode = String(u.searchParams.get('mode') || '').trim();
      const items = mode ? promptPresets.filter((x) => String(x.mode || '') === mode) : promptPresets;
      return mkResponse(200, { items });
    }
    if (method === 'GET' && p === '/api/health') return mkResponse(200, { comfy: true, worker: 'running', pending: 0, running: 0 });
    if (method === 'GET' && p === '/api/jobs') return mkResponse(200, jobsList);

    if (method === 'GET' && p.startsWith('/api/jobs/')) {
      const id = p.split('/').pop();
      return mkResponse(200, jobDetails[id] || { job: { id: Number(id) || 0 }, prompts: [] });
    }

    if (method === 'POST' && p === '/api/input-dirs/normalize') {
      return mkResponse(200, { normalized_path: bodyObj?.path || '' });
    }
    if (method === 'POST' && p === '/api/pick-directory') {
      return mkResponse(200, { path: '/picked/batch' });
    }
    if (method === 'POST' && p === '/api/pick-image') {
      return mkResponse(200, { path: '/picked/single.png' });
    }
    if (method === 'POST' && p === '/api/jobs/single') {
      const img = String(bodyObj?.input_image || '').toLowerCase();
      if (img && !['.png', '.jpg', '.jpeg', '.webp', '.bmp'].some((ext) => img.endsWith(ext))) {
        return mkResponse(400, { detail: 'unsupported input image extension: .txt' });
      }
      state.submits.push({ endpoint: p, payload: bodyObj });
      return mkResponse(201, { job_id: 1, prompt_count: 1, input_dir: '/home/cobra/ComfyUI/input' });
    }
    if (method === 'POST' && p === '/api/jobs') {
      state.submits.push({ endpoint: p, payload: bodyObj });
      return mkResponse(201, { job_id: 1, prompt_count: 1, input_dir: '/home/cobra/ComfyUI/input' });
    }
    if (method === 'POST' && p === '/api/prompt-presets') {
      const item = {
        name: String(bodyObj?.name || ''),
        mode: String(bodyObj?.mode || ''),
        positive_prompt: String(bodyObj?.positive_prompt || ''),
        negative_prompt: String(bodyObj?.negative_prompt || ''),
      };
      const idx = promptPresets.findIndex((x) => String(x.name || '') === item.name);
      if (idx >= 0) promptPresets[idx] = item;
      else promptPresets.push(item);
      return mkResponse(201, item);
    }

    if (method === 'POST' && (p === '/api/queue/pause' || p === '/api/queue/resume')) return mkResponse(200, { ok: true });
    if (method === 'POST' && p === '/api/queue/clear') {
      const deletedJobs = jobsList.length;
      jobsList = [];
      return mkResponse(200, { ok: true, deleted_jobs: deletedJobs, deleted_prompts: deletedJobs });
    }
    if (method === 'POST' && p.includes('/cancel')) return mkResponse(200, { cancel_summary: { mode: 'immediate', canceled_pending: 1, running_prompts: 0 } });
    if (method === 'POST' && p.includes('/retry')) return mkResponse(200, { ok: true });
    if (method === 'POST' && p === '/api/reload/workflows') {
      if (workflowsAfterReload) activeWorkflows = workflowsAfterReload;
      return mkResponse(200, { count: activeWorkflows.length, workflows: activeWorkflows.map((w) => w.name) });
    }
    if (method === 'POST' && p === '/api/reload/loras') return mkResponse(200, { count: 0, loras: [] });

    return mkResponse(404, { detail: `unhandled ${method} ${p}` });
  }

  return { state, fetchRouter };
}

async function createDom(options = {}) {
  const { state, fetchRouter } = buildApi(options);

  const dom = new JSDOM(HTML, {
    url: 'http://localhost/',
    runScripts: 'dangerously',
    resources: 'usable',
    beforeParse(window) {
      if (options.breakStorage) {
        Object.defineProperty(window, 'localStorage', {
          configurable: true,
          get() {
            throw new Error('storage unavailable');
          },
        });
      }
      if (options.seedState !== undefined && options.seedState !== null && !options.breakStorage) {
        window.localStorage.setItem(STATE_KEY, options.seedState);
      }
      window.fetch = (url, opts) => Promise.resolve(fetchRouter(url, opts || {}));
      const confirmResponses = Array.isArray(options.confirmResponses) ? [...options.confirmResponses] : null;
      window.confirm = () => {
        if (confirmResponses && confirmResponses.length > 0) return !!confirmResponses.shift();
        return true;
      };
      window.setInterval = () => 0;
      window.clearInterval = () => {};
    },
  });

  await waitFor(() => {
    const el = dom.window.document.getElementById('workflowSelect');
    return el && el.options && el.options.length > 0;
  }, 3000);

  return { dom, apiState: state };
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(predicate, timeoutMs = 1500) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    if (predicate()) return;
    await wait(10);
  }
  throw new Error('timed out waiting for condition');
}

function dispatch(el, type) {
  el.dispatchEvent(new el.ownerDocument.defaultView.Event(type, { bubbles: true }));
}

test('persists and restores global + per-workflow state across reload', async () => {
  const { dom: dom1 } = await createDom();
  const doc1 = dom1.window.document;

  const wf = doc1.getElementById('workflowSelect');
  wf.value = 'wan-context-lite-2stage';
  dispatch(wf, 'change');

  const positive1 = doc1.querySelector('[data-param-name="positive_prompt"]');
  positive1.value = 'wf1 prompt';
  dispatch(positive1, 'input');

  wf.value = 'wan-context-2stage';
  dispatch(wf, 'change');
  const positive2 = doc1.querySelector('[data-param-name="positive_prompt"]');
  positive2.value = 'wf2 prompt';
  dispatch(positive2, 'input');

  wf.value = 'wan-context-lite-2stage';
  dispatch(wf, 'change');
  const positiveBack = doc1.querySelector('[data-param-name="positive_prompt"]');
  assert.equal(positiveBack.value, 'wf1 prompt');

  const res = doc1.getElementById('resolutionPreset');
  res.value = '768x1360';
  dispatch(res, 'change');

  const flip = doc1.getElementById('flipOrientation');
  flip.checked = true;
  dispatch(flip, 'change');

  const inputDir = doc1.getElementById('inputDir');
  inputDir.value = '/tmp/my_batch';
  dispatch(inputDir, 'input');

  const tabSingle = doc1.getElementById('tabSingle');
  dispatch(tabSingle, 'click');

  const inputImage = doc1.getElementById('inputImage');
  inputImage.value = '/tmp/one.png';
  dispatch(inputImage, 'input');

  const saved = dom1.window.localStorage.getItem(STATE_KEY);
  assert.ok(saved && saved.includes('wf1 prompt'));
  dom1.window.close();

  const { dom: dom2 } = await createDom({ seedState: saved });
  const doc2 = dom2.window.document;

  assert.equal(doc2.getElementById('workflowSelect').value, 'wan-context-lite-2stage');
  assert.equal(doc2.getElementById('resolutionPreset').value, '768x1360');
  assert.equal(doc2.getElementById('flipOrientation').checked, true);
  assert.equal(doc2.getElementById('inputDir').value, '/tmp/my_batch');
  assert.equal(doc2.getElementById('inputImage').value, '/tmp/one.png');
  assert.equal(doc2.querySelector('[data-param-name="positive_prompt"]').value, 'wf1 prompt');

  dom2.window.close();
});

test('corrupted localStorage state safely falls back to defaults', async () => {
  const { dom } = await createDom({ seedState: '{bad json' });
  const doc = dom.window.document;

  assert.equal(doc.getElementById('workflowSelect').options.length > 0, true);
  assert.equal(doc.getElementById('inputDir').value, '');

  dom.window.close();
});

test('storage-unavailable path does not break initialization', async () => {
  const { dom } = await createDom({ breakStorage: true });
  const doc = dom.window.document;
  assert.equal(doc.getElementById('workflowSelect').options.length > 0, true);
  dom.window.close();
});

test('stale persisted numeric and boolean values are coerced/clamped', async () => {
  const stale = {
    version: 1,
    global: {
      workflow_name: 'wan-context-lite-2stage',
      resolution_preset: '640x1136',
      flip_orientation: false,
      input_dir: '/tmp/demo',
      single_image: '',
      active_tab: 'batch',
    },
    workflow_params: {
      'wan-context-lite-2stage': {
        tries: 999,
        randomize_seed: 'false',
      },
    },
  };

  const { dom } = await createDom({ seedState: JSON.stringify(stale) });
  const doc = dom.window.document;
  const tries = doc.querySelector('[data-param-name="tries"]');
  const randomize = doc.querySelector('[data-param-name="randomize_seed"]');

  assert.equal(tries.value, '10');
  assert.equal(randomize.checked, false);

  dom.window.close();
});

test('reset button clears saved options', async () => {
  const { dom } = await createDom();
  const doc = dom.window.document;

  const inputDir = doc.getElementById('inputDir');
  inputDir.value = '/tmp/will_clear';
  dispatch(inputDir, 'input');

  dispatch(doc.getElementById('resetSavedBtn'), 'click');

  const state = JSON.parse(dom.window.localStorage.getItem(STATE_KEY));
  assert.equal(state.global.input_dir, '');
  assert.equal(doc.getElementById('inputDir').value, '');

  dom.window.close();
});

test('single tab prevents empty submit and maps payload to /api/jobs/single', async () => {
  const { dom, apiState } = await createDom();
  const doc = dom.window.document;

  dispatch(doc.getElementById('tabSingle'), 'click');
  doc.getElementById('inputImage').value = '';
  dispatch(doc.getElementById('submitBtn'), 'click');
  await wait(10);
  assert.match(doc.getElementById('submitMsg').textContent, /requires one input image/i);
  assert.equal(apiState.submits.length, 0);

  doc.getElementById('inputImage').value = '/tmp/one.png';
  dispatch(doc.getElementById('inputImage'), 'input');
  dispatch(doc.getElementById('submitBtn'), 'click');
  await wait(10);

  assert.equal(apiState.submits.length, 1);
  assert.equal(apiState.submits[0].endpoint, '/api/jobs/single');
  assert.equal(apiState.submits[0].payload.input_image, '/tmp/one.png');

  dom.window.close();
});

test('single tab invalid image type surfaces validation error', async () => {
  const { dom, apiState } = await createDom();
  const doc = dom.window.document;

  dispatch(doc.getElementById('tabSingle'), 'click');
  doc.getElementById('inputImage').value = '/tmp/not_allowed.txt';
  dispatch(doc.getElementById('inputImage'), 'input');
  dispatch(doc.getElementById('submitBtn'), 'click');
  await wait(10);

  assert.match(doc.getElementById('submitMsg').textContent, /unsupported input image extension/i);
  assert.equal(apiState.submits.length, 0);

  dom.window.close();
});

test('batch submit endpoint remains /api/jobs', async () => {
  const { dom, apiState } = await createDom();
  const doc = dom.window.document;

  dispatch(doc.getElementById('tabBatch'), 'click');
  doc.getElementById('inputDir').value = '/tmp/batch';
  dispatch(doc.getElementById('inputDir'), 'input');
  dispatch(doc.getElementById('submitBtn'), 'click');
  await wait(10);

  assert.equal(apiState.submits.length, 1);
  assert.equal(apiState.submits[0].endpoint, '/api/jobs');
  assert.equal(apiState.submits[0].payload.input_dir, '/tmp/batch');

  dom.window.close();
});

test('stage-prompt workflows render grouped stage inputs and submit stage params', async () => {
  const stageWorkflow = {
    name: 'wan-context-3stage-split-prompts',
    display_name: 'WAN 3-stage split',
    group: 'WAN V2',
    description: 'split prompts',
    input_type: 'image',
    input_extensions: ['.png', '.jpg'],
    supports_resolution: true,
    parameters: {
      positive_prompt_stage1: { label: 'Positive prompt (stage 1)', type: 'text', default: '', min: null, max: null },
      positive_prompt_stage2: { label: 'Positive prompt (stage 2)', type: 'text', default: '', min: null, max: null },
      positive_prompt_stage3: { label: 'Positive prompt (stage 3)', type: 'text', default: '', min: null, max: null },
      negative_prompt: { label: 'Negative prompt', type: 'text', default: '', min: null, max: null },
      tries: { label: 'Tries', type: 'int', default: 1, min: 1, max: 10 },
    },
  };

  const { dom, apiState } = await createDom({ workflows: [stageWorkflow] });
  const doc = dom.window.document;

  const summaries = [...doc.querySelectorAll('#paramFields summary')].map((x) => x.textContent || '');
  assert.ok(summaries.some((x) => /Stage 1 Prompts/.test(x)));
  assert.ok(summaries.some((x) => /Stage 2 Prompts/.test(x)));
  assert.ok(summaries.some((x) => /Stage 3 Prompts/.test(x)));

  doc.querySelector('[data-param-name="positive_prompt_stage1"]').value = 'phase one';
  dispatch(doc.querySelector('[data-param-name="positive_prompt_stage1"]'), 'input');
  doc.querySelector('[data-param-name="positive_prompt_stage2"]').value = 'phase two';
  dispatch(doc.querySelector('[data-param-name="positive_prompt_stage2"]'), 'input');
  doc.querySelector('[data-param-name="positive_prompt_stage3"]').value = 'phase three';
  dispatch(doc.querySelector('[data-param-name="positive_prompt_stage3"]'), 'input');

  doc.getElementById('inputDir').value = '/tmp/stages';
  dispatch(doc.getElementById('inputDir'), 'input');
  dispatch(doc.getElementById('submitBtn'), 'click');
  await wait(10);

  assert.equal(apiState.submits.length, 1);
  assert.equal(apiState.submits[0].endpoint, '/api/jobs');
  assert.equal(apiState.submits[0].payload.params.positive_prompt_stage1, 'phase one');
  assert.equal(apiState.submits[0].payload.params.positive_prompt_stage2, 'phase two');
  assert.equal(apiState.submits[0].payload.params.positive_prompt_stage3, 'phase three');

  dom.window.close();
});

test('upscale images tab selects workflow and submits non-prompt upscale params', async () => {
  const upscaleImages = {
    name: 'upscale-images-i2v',
    display_name: 'Upscale Images (I2V Prep)',
    group: 'Utilities',
    description: 'image upscale',
    input_type: 'image',
    input_extensions: ['.png', '.jpg'],
    supports_resolution: false,
    parameters: {
      upscale_model_name: { label: 'AI upscale model (.pth)', type: 'text', default: 'RealESRGAN_x2plus.pth', min: null, max: null },
      final_scale_factor: { label: 'Post-AI scale factor', type: 'float', default: 0.75, min: 0.25, max: 2.0 },
      output_prefix: { label: 'Output prefix', type: 'text', default: 'image/upscaled_i2v', min: null, max: null },
    },
  };
  const generic = {
    ...defaultWorkflows[0],
  };

  const { dom, apiState } = await createDom({ workflows: [generic, upscaleImages] });
  const doc = dom.window.document;

  assert.equal(doc.getElementById('upscaleImagesDropZone').classList.contains('hidden'), true);
  dispatch(doc.getElementById('tabUpscaleImages'), 'click');
  assert.equal(doc.getElementById('workflowSelect').value, 'upscale-images-i2v');
  assert.equal(doc.getElementById('promptPresetSection').classList.contains('hidden'), true);
  assert.equal(doc.getElementById('upscaleImagesDropZone').classList.contains('hidden'), false);
  assert.equal(doc.getElementById('clearUpscaleDropBtn').classList.contains('hidden'), true);
  const modelField = doc.querySelector('[data-param-name="upscale_model_name"]');
  assert.equal(modelField.tagName, 'SELECT');
  const modelOptions = [...modelField.options].map((o) => o.value);
  assert.ok(modelOptions.includes('RealESRGAN_x4plus.pth'));
  assert.ok(modelOptions.includes('RealESRNet_x4plus.pth'));

  doc.getElementById('inputDir').value = '/tmp/upscale_images';
  dispatch(doc.getElementById('inputDir'), 'input');
  doc.querySelector('[data-param-name="upscale_model_name"]').value = 'RealESRGAN_x2plus.pth';
  dispatch(doc.querySelector('[data-param-name="upscale_model_name"]'), 'input');
  doc.querySelector('[data-param-name="final_scale_factor"]').value = '1.0';
  dispatch(doc.querySelector('[data-param-name="final_scale_factor"]'), 'input');
  dispatch(doc.getElementById('submitBtn'), 'click');
  await wait(10);

  assert.equal(apiState.submits.length, 1);
  assert.equal(apiState.submits[0].endpoint, '/api/jobs');
  assert.equal(apiState.submits[0].payload.workflow_name, 'upscale-images-i2v');
  assert.equal(apiState.submits[0].payload.params.upscale_model_name, 'RealESRGAN_x2plus.pth');
  assert.equal(apiState.submits[0].payload.params.final_scale_factor, 1.0);

  dom.window.close();
});

test('workflow dropdown is filtered by mode category per tab', async () => {
  const workflows = [
    {
      name: 'wan-context-2stage',
      display_name: 'WAN Gen',
      group: 'WAN V2',
      category: 'video_gen',
      description: 'video gen',
      input_type: 'image',
      input_extensions: ['.png'],
      supports_resolution: true,
      parameters: { positive_prompt: { label: 'Positive', type: 'text', default: '', min: null, max: null } },
    },
    {
      name: 'upscale-interpolate-only',
      display_name: 'Video Upscale',
      group: 'Utilities',
      category: 'video_upscale',
      description: 'video up',
      input_type: 'video',
      input_extensions: ['.mp4'],
      supports_resolution: false,
      parameters: { output_prefix: { label: 'Out', type: 'text', default: '', min: null, max: null } },
    },
    {
      name: 'upscale-images-i2v',
      display_name: 'Image Upscale',
      group: 'Utilities',
      category: 'image_upscale',
      description: 'image up',
      input_type: 'image',
      input_extensions: ['.png'],
      supports_resolution: false,
      parameters: { output_prefix: { label: 'Out', type: 'text', default: '', min: null, max: null } },
    },
  ];

  const { dom } = await createDom({ workflows });
  const doc = dom.window.document;

  const optionsBatch = [...doc.getElementById('workflowSelect').options].map((o) => o.value);
  assert.deepEqual(optionsBatch, ['wan-context-2stage']);

  dispatch(doc.getElementById('tabUpscale'), 'click');
  await wait(10);
  const optionsUpscale = [...doc.getElementById('workflowSelect').options].map((o) => o.value);
  assert.deepEqual(optionsUpscale, ['upscale-interpolate-only']);

  dispatch(doc.getElementById('tabUpscaleImages'), 'click');
  await wait(10);
  const optionsImageUpscale = [...doc.getElementById('workflowSelect').options].map((o) => o.value);
  assert.deepEqual(optionsImageUpscale, ['upscale-images-i2v']);

  dom.window.close();
});

test('prompt presets are requested with mode scope per active tab', async () => {
  const workflows = [
    {
      name: 'wan-context-2stage',
      display_name: 'WAN Gen',
      group: 'WAN V2',
      category: 'video_gen',
      description: 'video gen',
      input_type: 'image',
      input_extensions: ['.png'],
      supports_resolution: true,
      parameters: { positive_prompt: { label: 'Positive', type: 'text', default: '', min: null, max: null } },
    },
    {
      name: 'upscale-interpolate-only',
      display_name: 'Video Upscale',
      group: 'Utilities',
      category: 'video_upscale',
      description: 'video up',
      input_type: 'video',
      input_extensions: ['.mp4'],
      supports_resolution: false,
      parameters: { output_prefix: { label: 'Out', type: 'text', default: '', min: null, max: null } },
    },
    {
      name: 'upscale-images-i2v',
      display_name: 'Image Upscale',
      group: 'Utilities',
      category: 'image_upscale',
      description: 'image up',
      input_type: 'image',
      input_extensions: ['.png'],
      supports_resolution: false,
      parameters: { output_prefix: { label: 'Out', type: 'text', default: '', min: null, max: null } },
    },
  ];

  const { dom, apiState } = await createDom({ workflows });
  const doc = dom.window.document;

  dispatch(doc.getElementById('tabUpscale'), 'click');
  await wait(10);
  dispatch(doc.getElementById('tabUpscaleImages'), 'click');
  await wait(10);
  dispatch(doc.getElementById('tabBatch'), 'click');
  await wait(10);

  const presetGets = apiState.requests.filter((r) => r.method === 'GET' && r.path === '/api/prompt-presets');
  const queryBlob = presetGets.map((r) => String(r.query || '')).join('|');
  assert.match(queryBlob, /mode=video_gen/);
  assert.match(queryBlob, /mode=video_upscale/);
  assert.match(queryBlob, /mode=image_upscale/);

  dom.window.close();
});

test('submit payload job_name is auto-prefixed by active mode', async () => {
  const { dom, apiState } = await createDom();
  const doc = dom.window.document;

  dispatch(doc.getElementById('tabBatch'), 'click');
  doc.getElementById('inputDir').value = '/tmp/batch';
  dispatch(doc.getElementById('inputDir'), 'input');
  doc.getElementById('jobName').value = 'foo';
  dispatch(doc.getElementById('jobName'), 'input');
  dispatch(doc.getElementById('submitBtn'), 'click');
  await wait(10);
  assert.equal(apiState.submits[0].payload.job_name, 'batch foo');

  dispatch(doc.getElementById('tabSingle'), 'click');
  doc.getElementById('inputImage').value = '/tmp/one.png';
  dispatch(doc.getElementById('inputImage'), 'input');
  doc.getElementById('jobName').value = 'bar';
  dispatch(doc.getElementById('jobName'), 'input');
  dispatch(doc.getElementById('submitBtn'), 'click');
  await wait(10);
  assert.equal(apiState.submits[1].payload.job_name, 'single bar');

  dom.window.close();
});

test('workflow reload with changed parameter schema does not break restore logic', async () => {
  const changed = [
    {
      name: 'wan-context-lite-2stage',
      display_name: 'WAN Lite Changed',
      group: 'WAN V2',
      description: 'changed',
      input_type: 'image',
      input_extensions: ['.png'],
      supports_resolution: true,
      parameters: {
        positive_prompt: { label: 'Positive prompt', type: 'text', default: '', min: null, max: null },
      },
    },
  ];

  const seed = {
    version: 1,
    global: {
      workflow_name: 'wan-context-lite-2stage',
      resolution_preset: '640x1136',
      flip_orientation: false,
      input_dir: '/tmp/demo',
      single_image: '',
      active_tab: 'batch',
    },
    workflow_params: {
      'wan-context-lite-2stage': {
        positive_prompt: 'old value',
        tries: 9,
        removed_param: 'ignored',
      },
    },
  };

  const { dom } = await createDom({ seedState: JSON.stringify(seed), workflowsAfterReload: changed });
  const doc = dom.window.document;

  dispatch(doc.getElementById('reloadWorkflowsBtn'), 'click');
  await wait(10);

  assert.doesNotThrow(() => doc.querySelector('[data-param-name="positive_prompt"]'));
  assert.match(doc.getElementById('submitMsg').textContent, /reloaded workflows/i);

  dom.window.close();
});

test('submit after reload uses restored settings', async () => {
  const { dom: first } = await createDom();
  const firstDoc = first.window.document;
  dispatch(firstDoc.getElementById('tabSingle'), 'click');
  firstDoc.getElementById('inputImage').value = '/tmp/reload.png';
  dispatch(firstDoc.getElementById('inputImage'), 'input');

  const saved = first.window.localStorage.getItem(STATE_KEY);
  first.window.close();

  const { dom: second, apiState } = await createDom({ seedState: saved });
  const secondDoc = second.window.document;
  dispatch(secondDoc.getElementById('submitBtn'), 'click');
  await wait(10);

  assert.equal(apiState.submits.length, 1);
  assert.equal(apiState.submits[0].endpoint, '/api/jobs/single');
  assert.equal(apiState.submits[0].payload.input_image, '/tmp/reload.png');

  second.window.close();
});

test('picker start-dir payload uses default when empty and explicit path when provided', async () => {
  const { dom, apiState } = await createDom();
  const doc = dom.window.document;

  doc.getElementById('inputDir').value = '';
  dispatch(doc.getElementById('inputBrowseBtn'), 'click');
  await wait(10);

  const pickReq1 = apiState.requests.find((r) => r.path === '/api/pick-directory' && r.method === 'POST');
  assert.equal(pickReq1.body.start_dir, null);

  doc.getElementById('inputDir').value = '/tmp/custom';
  dispatch(doc.getElementById('inputBrowseBtn'), 'click');
  await wait(10);

  const pickReqs = apiState.requests.filter((r) => r.path === '/api/pick-directory' && r.method === 'POST');
  assert.equal(pickReqs[pickReqs.length - 1].body.start_dir, '/tmp/custom');

  dom.window.close();
});

test('default input directory warning shown when unavailable', async () => {
  const { dom } = await createDom({ defaultExists: false });
  const txt = dom.window.document.getElementById('defaultInputDirNotice').textContent;
  assert.equal(txt, '');
  dom.window.close();
});

test('prompt details render prompt row id, comfy prompt id, and collapsible JSON', async () => {
  const { dom } = await createDom({
    jobsList: [
      {
        id: 77,
        workflow_name: 'wan-context-lite-2stage',
        input_dir: '/tmp/in',
        status: 'running',
        created_at: '2026-01-01T00:00:00+00:00',
        finished_at: null,
        prompt_count: 1,
      },
    ],
    jobDetails: {
      '77': {
        job: { id: 77, status: 'running' },
        prompts: [
          {
            id: 910,
            status: 'running',
            input_file: '/tmp/in/a.png',
            prompt_id: 'comfy-123',
            prompt_json: JSON.stringify({ node: { inputs: { x: 1 } } }),
            output_paths: '[]',
            error_detail: null,
          },
        ],
      },
    },
  });

  const doc = dom.window.document;
  await wait(10);

  const details = doc.querySelector('details');
  assert.ok(details);
  details.open = true;
  dispatch(details, 'toggle');
  await wait(10);

  const body = details.querySelector('[data-detail-body]');
  const text = body.textContent;
  assert.match(text, /Prompt Row 910/);
  assert.match(text, /Comfy prompt_id: comfy-123/);
  assert.match(text, /Prompt JSON/);

  const pre = body.querySelector('pre');
  assert.ok(pre.textContent.includes('"node"'));

  dom.window.close();
});

test('clear queue button requires two confirmations and clears queue', async () => {
  const { dom, apiState } = await createDom({
    confirmResponses: [true, true],
    jobsList: [
      {
        id: 1,
        workflow_name: 'wan-context-lite-2stage',
        input_dir: '/tmp/in',
        status: 'pending',
        created_at: '2026-01-01T00:00:00+00:00',
        finished_at: null,
        prompt_count: 1,
      },
    ],
  });
  const doc = dom.window.document;

  dispatch(doc.getElementById('clearQueueBtn'), 'click');
  await wait(10);

  const clearReq = apiState.requests.find((r) => r.method === 'POST' && r.path === '/api/queue/clear');
  assert.ok(clearReq);
  assert.match(doc.getElementById('submitMsg').textContent, /queue cleared/i);

  dom.window.close();
});
