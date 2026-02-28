import { writable } from 'svelte/store';
import { api } from '$lib/api';
import type { JobListItem } from '$lib/types';

export const jobs = writable<JobListItem[]>([]);
export const jobsError = writable('');

const DEFAULT_INTERVAL_MS = 2500;
const MAX_BACKOFF_MS = 15000;
const REQUEST_TIMEOUT_MS = 12000;

let timer: ReturnType<typeof setTimeout> | null = null;
let running = false;
let failureCount = 0;
let intervalMs = DEFAULT_INTERVAL_MS;
let activeRequestId = 0;
let inFlightController: AbortController | null = null;
let visibilityBound = false;

function clearTimer(): void {
  if (timer !== null) {
    clearTimeout(timer);
    timer = null;
  }
}

function abortInFlight(): void {
  if (inFlightController) {
    inFlightController.abort();
    inFlightController = null;
  }
}

function pollDelay(): number {
  if (failureCount <= 0) return intervalMs;
  return Math.min(intervalMs * Math.pow(2, Math.min(failureCount, 6)), MAX_BACKOFF_MS);
}

function scheduleNext(delayMs: number): void {
  if (!running) return;
  clearTimer();
  if (typeof document !== 'undefined' && document.hidden) return;
  timer = setTimeout(() => {
    void pollOnce(false);
  }, Math.max(80, Number(delayMs || intervalMs)));
}

async function pollOnce(force: boolean): Promise<void> {
  if (!running && !force) return;

  const requestId = ++activeRequestId;
  abortInFlight();
  const controller = new AbortController();
  inFlightController = controller;

  try {
    const data = await api.jobs({
      signal: controller.signal,
      timeoutMs: REQUEST_TIMEOUT_MS,
    });

    if (requestId !== activeRequestId) return;
    jobs.set(data);
    jobsError.set('');
    failureCount = 0;
  } catch (e) {
    if (requestId !== activeRequestId) return;
    // If we intentionally stopped polling, swallow abort errors.
    if (!running && controller.signal.aborted) return;
    failureCount += 1;
    jobsError.set(e instanceof Error ? e.message : String(e));
  } finally {
    if (inFlightController === controller) {
      inFlightController = null;
    }
    if (running) {
      scheduleNext(pollDelay());
    }
  }
}

function onVisibilityChange(): void {
  if (!running) return;
  if (document.hidden) {
    clearTimer();
    abortInFlight();
    return;
  }
  scheduleNext(50);
}

export async function refreshJobs(): Promise<void> {
  await pollOnce(true);
}

export function startJobsPolling(nextIntervalMs = DEFAULT_INTERVAL_MS): void {
  stopJobsPolling();
  running = true;
  intervalMs = Math.max(500, Number(nextIntervalMs || DEFAULT_INTERVAL_MS));
  failureCount = 0;
  if (typeof document !== 'undefined' && !visibilityBound) {
    document.addEventListener('visibilitychange', onVisibilityChange);
    visibilityBound = true;
  }
  scheduleNext(10);
}

export function stopJobsPolling(): void {
  running = false;
  clearTimer();
  abortInFlight();
  if (typeof document !== 'undefined' && visibilityBound) {
    document.removeEventListener('visibilitychange', onVisibilityChange);
    visibilityBound = false;
  }
}
