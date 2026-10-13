/** Expo inlines this public value at build time. Server secrets stay on backend. */
const configuredApi = process.env.EXPO_PUBLIC_API_URL?.trim()
const localBrowser = typeof window !== 'undefined' && ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)
// A public UI-only deployment must never send requests to a visitor's localhost.
export const API_URL = (configuredApi || (localBrowser ? 'http://localhost:8000' : '')).replace(/\/$/, '')
export const BACKEND_CONFIGURED = Boolean(configuredApi || localBrowser)
export const AUTH_REQUIRED = Boolean(configuredApi && !localBrowser)

export function requireBackend(): void {
  if (!BACKEND_CONFIGURED) throw new Error('Backend connection is pending. Please try again after the backend is connected.')
}
