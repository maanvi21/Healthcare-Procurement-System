import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Keeps a page's data current, and makes a failure visible.
 *
 * Every page used to fetch once in `useEffect(load, [])` and swallow errors with
 * `.catch(() => {})`. Two consequences, both of which showed up as "I keep having to
 * reload":
 *
 *   - Nothing ever refreshed. Ingest a document, decide an approval, let a risk score
 *     land — the open page kept showing whatever it fetched on mount. A manual reload
 *     was the only way to see anything new, on a platform whose whole point is that
 *     agents act on their own in the background.
 *   - A backend that was down looked exactly like an empty database. Both rendered
 *     "No documents yet.", so a reload was the only way to find out which it was.
 *
 * So this polls, refreshes when the tab regains focus, and surfaces the error instead
 * of hiding it. Polling pauses while the tab is hidden — a background tab does not need
 * to keep hitting six services, and the focus listener catches it up the moment the user
 * returns, which is the only time staleness is observable anyway.
 */

const DEFAULT_INTERVAL_MS = 5000;

const UNREACHABLE = "Can't reach the service. Is the backend running? (docker compose up -d)";

function describe(error) {
  const response = error?.response;
  if (!response) {
    // no response at all — nothing is listening, or the request never left
    return UNREACHABLE;
  }
  // The gateway answers even when the service behind it does not: it returns 502/503/504
  // when an upstream is down or timing out. That is the same "backend isn't running"
  // situation as no response at all, and "Request failed (504)" tells the reader nothing
  // actionable, so both map to the same message.
  if ([502, 503, 504].includes(response.status)) {
    return UNREACHABLE;
  }
  return response.data?.detail || `Request failed (${response.status})`;
}

export function useLiveData(load, { intervalMs = DEFAULT_INTERVAL_MS, deps = [] } = {}) {
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);

  // `load` is redefined on every render; keeping it in a ref means the polling effect
  // does not tear down and restart each time, which would reset the interval forever.
  const loadRef = useRef(load);
  loadRef.current = load;

  const refresh = useCallback(async () => {
    try {
      await loadRef.current();
      setError(null);
    } catch (err) {
      setError(describe(err));
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    // The first load always runs, even in a hidden tab. Gating it on visibility means a
    // page opened in a background tab (middle-click, or a restored session) stays empty
    // until it is focused — which looks exactly like the stale-data bug this hook exists
    // to fix. Only the recurring poll pauses while hidden.
    const load = () => {
      if (!cancelled) refresh();
    };
    const tick = () => {
      if (cancelled || document.visibilityState === "hidden") return;
      refresh();
    };

    load();
    const timer = setInterval(tick, intervalMs);
    window.addEventListener("focus", tick);
    document.addEventListener("visibilitychange", tick);

    return () => {
      cancelled = true;
      clearInterval(timer);
      window.removeEventListener("focus", tick);
      document.removeEventListener("visibilitychange", tick);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh, intervalMs, ...deps]);

  return { error, loaded, refresh };
}
