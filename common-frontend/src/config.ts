export const services = {
  sketch: { label: 'Sketch agent', url: process.env.EXPO_PUBLIC_SKETCH_AGENT_URL || 'http://localhost:8787/sketch', health: '/health' },
  visual: { label: 'Visual studio', url: process.env.EXPO_PUBLIC_VISUAL_API_URL || 'http://localhost:8787/visual', health: '/health' },
  quiz: { label: 'Adaptive practice', url: process.env.EXPO_PUBLIC_QUIZ_API_URL || 'http://localhost:8787/quiz', health: '/health' },
  notes: { label: 'Image to notes', url: process.env.EXPO_PUBLIC_NOTES_API_URL || 'http://localhost:8787/notes', health: '/api/health' },
  audio: { label: 'Audio tutor', url: process.env.EXPO_PUBLIC_AUDIO_API_URL || 'http://localhost:8787/audio', health: '/health' },
  prompt: { label: 'Prompt agent', url: process.env.EXPO_PUBLIC_PROMPT_API_URL || 'http://localhost:8787/prompt', health: '/health' },
  image: { label: 'Image agent', url: process.env.EXPO_PUBLIC_IMAGE_API_URL || 'http://localhost:8787/image', health: '/health' },
  interactive: { label: 'Interactive agent', url: process.env.EXPO_PUBLIC_INTERACTIVE_API_URL || 'http://localhost:8787/interactive', health: '/health' },
  evaluation: { label: 'Evaluation agent', url: process.env.EXPO_PUBLIC_EVALUATION_API_URL || 'http://localhost:8787/evaluation', health: '/health' },
  threed: { label: '3D agent', url: process.env.EXPO_PUBLIC_THREED_API_URL || 'http://localhost:8787/threed', health: '/health' },
};
export type Service = keyof typeof services;
