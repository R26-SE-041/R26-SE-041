import { Platform } from 'react-native';

// Shared by the shell, learning tools and browser adapters.
export const colors = {
  bg: '#FAF9F5', surface: '#FFFFFF', soft: '#F0EEE6', sidebar: '#F5F4EE',
  ink: '#141413', muted: '#69675F', accent: '#C96442', accentHover: '#AE5134',
  accentSoft: '#F4E8E0', line: '#E4E2D9', sage: '#52634D', successSoft: '#EDF1E9',
  danger: '#A33D32', dangerSoft: '#F8EAE6', canvas: '#F5F3EC',
};
export const fonts = {
  body: Platform.select({ web: '"Segoe UI", Arial, sans-serif', default: 'System' }),
  heading: Platform.select({ web: 'Georgia, "Times New Roman", serif', ios: 'Georgia', default: 'serif' }),
};
export const webTransition = Platform.select({ web: { transition: 'background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease' } as object });

export function webData(dataSet: Record<string, string | undefined>) {
  return Platform.OS === 'web' ? { dataSet } : {};
}
