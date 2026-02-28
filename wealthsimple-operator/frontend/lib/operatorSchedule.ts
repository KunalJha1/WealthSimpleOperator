export const SCHEDULE_INTERVAL_MS = 3 * 60 * 1000;
export const FIRST_RELEASE_DELAY_MS = 60 * 1000;

const NEXT_SCAN_STORAGE_KEY = "operator_next_auto_scan_at_v1";
const TIMER_BOOTSTRAP_SESSION_KEY = "operator_timer_bootstrapped_v1";

function parseStoredTimestamp(value: string | null): number | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return null;
  return parsed;
}

export function persistNextRunAt(timestampMs: number): void {
  window.localStorage.setItem(NEXT_SCAN_STORAGE_KEY, String(timestampMs));
}

export function advanceNextRunAt(fromNowMs = Date.now()): number {
  const next = fromNowMs + SCHEDULE_INTERVAL_MS;
  persistNextRunAt(next);
  return next;
}

export function getOrInitNextRunAt(): number {
  const isBootstrapped = window.sessionStorage.getItem(TIMER_BOOTSTRAP_SESSION_KEY) === "1";
  const stored = parseStoredTimestamp(window.localStorage.getItem(NEXT_SCAN_STORAGE_KEY));

  if (!isBootstrapped) {
    const next = Date.now() + FIRST_RELEASE_DELAY_MS;
    window.sessionStorage.setItem(TIMER_BOOTSTRAP_SESSION_KEY, "1");
    persistNextRunAt(next);
    return next;
  }

  if (stored != null) {
    return stored;
  }

  const next = Date.now() + FIRST_RELEASE_DELAY_MS;
  persistNextRunAt(next);
  return next;
}

export function clearScheduleSessionBootstrap(): void {
  window.sessionStorage.removeItem(TIMER_BOOTSTRAP_SESSION_KEY);
}
