/** Expo inlines this public value at build time. Server secrets stay on backend. */
export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
