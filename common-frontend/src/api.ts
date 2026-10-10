import { auth } from './auth';
import { services, Service } from './config';
import { readResponse } from './transport.mjs';
export { ApiError } from './transport.mjs';
export async function api<T>(service: Service, path: string, body?: object | FormData, options: { signal?: AbortSignal; timeout?: number; blob?: boolean; method?: 'GET' | 'POST' | 'PUT' | 'DELETE' } = {}): Promise<T> {
  const { data, error } = auth ? await auth.auth.getSession() : { data: { session: null }, error: null };
  if (error) throw error;
  if (!data.session && path !== services[service].health) throw new Error('Sign in to use the learning tools.');
  const headers: Record<string, string> = {};
  if (data.session) headers.Authorization = `Bearer ${data.session.access_token}`;
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const controller = new AbortController();
  const abort = () => controller.abort();
  const subscription = data.session ? auth!.auth.onAuthStateChange((_event, next) => { if (next?.user.id !== data.session!.user.id) abort(); }).data.subscription : null;
  options.signal?.addEventListener('abort', abort, { once: true });
  if (options.signal?.aborted) abort();
  const timer = setTimeout(abort, options.timeout ?? 240000);
  try {
    const response = await fetch(services[service].url.replace(/\/$/, '') + path, {
      method: options.method || (body ? 'POST' : 'GET'), headers, body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined, signal: controller.signal,
    });
    return await readResponse(response, services[service].label, options.blob ? 'blob' : 'json') as T;
  } catch (error) {
    if (controller.signal.aborted) throw new Error(options.signal?.aborted ? 'Request cancelled.' : 'The service took too long. Please retry.');
    if (error instanceof TypeError) throw new Error(`${services[service].label} is unreachable. Check the backend and local proxy.`);
    throw error;
  } finally { clearTimeout(timer); subscription?.unsubscribe(); options.signal?.removeEventListener('abort', abort); }
}

// Adapter for the existing visual controls: fresh shared tokens on every request,
// abort on account change and bounded network requests, including 3D polling.
export async function authenticatedFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const { data, error } = auth ? await auth.auth.getSession() : { data: { session: null }, error: null };
  if (error) throw error;
  if (!data.session) throw new Error('Sign in to use the learning tools.');
  const controller = new AbortController();
  const abort = () => controller.abort();
  const { data: listener } = auth!.auth.onAuthStateChange((_event, next) => { if (next?.user.id !== data.session!.user.id) abort(); });
  options.signal?.addEventListener('abort', abort, { once: true });
  if (options.signal?.aborted) abort();
  const timer = setTimeout(abort, 240000);
  const headers = new Headers(options.headers); headers.set('Authorization', `Bearer ${data.session.access_token}`);
  try { return await fetch(url, { ...options, headers, signal: controller.signal }); }
  finally { clearTimeout(timer); listener.subscription.unsubscribe(); options.signal?.removeEventListener('abort', abort); }
}
