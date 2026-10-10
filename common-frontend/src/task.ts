import { useCallback, useEffect, useRef, useState } from 'react';
export function useTask() {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const mounted = useRef(true), controller = useRef<AbortController | null>(null);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; controller.current?.abort(); }; }, []);
  const run = useCallback(async (work: (signal: AbortSignal) => Promise<void>) => {
    if (controller.current) return;
    const current = new AbortController(); controller.current = current;
    setBusy(true); setError('');
    try { await work(current.signal); }
    catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : 'Something went wrong. Please retry.'); }
    finally { controller.current = null; if (mounted.current) setBusy(false); }
  }, []);
  return { busy, error, run, clearError: () => setError('') };
}
export async function delay(ms: number, signal: AbortSignal) {
  if (signal.aborted) throw new Error('Request cancelled.');
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
    function abort() { clearTimeout(timer); signal.removeEventListener('abort', abort); reject(new Error('Request cancelled.')); }
    signal.addEventListener('abort', abort, { once: true });
  });
}
