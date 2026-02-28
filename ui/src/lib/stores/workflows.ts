import { writable } from 'svelte/store';
import { api } from '$lib/api';
import type { WorkflowDef } from '$lib/types';

export const workflows = writable<WorkflowDef[]>([]);
export const workflowMap = writable<Record<string, WorkflowDef>>({});
export const workflowError = writable('');

export async function refreshWorkflows(): Promise<void> {
  try {
    const list = await api.workflows();
    workflows.set(list);
    workflowMap.set(Object.fromEntries(list.map((w) => [w.name, w])));
    workflowError.set('');
  } catch (e) {
    workflowError.set(e instanceof Error ? e.message : String(e));
  }
}
