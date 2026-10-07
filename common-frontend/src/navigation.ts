export type Page = 'home' | 'visual' | 'quiz' | 'notes' | 'audio' | 'settings';
export const modules = [
  { id: 'visual', icon: '✳', label: 'Visual studio', subtitle: 'SEE IT. UNDERSTAND IT.', description: 'Bring complex concepts to life with AI generated biological infographics.', tint: '#EEDAD0', tag: 'Interactive visualization' },
  { id: 'quiz', icon: '◇', label: 'Adaptive practice', subtitle: 'A LITTLE PRACTICE. A LOT OF PROGRESS.', description: 'Challenge your understanding with quizzes that adapt to your learning.', tint: '#E1E7DA', tag: 'Assessment & recommendations' },
  { id: 'notes', icon: '▤', label: 'Image to notes', subtitle: 'FROM HANDWRITING TO CLARITY.', description: 'Turn handwritten pages into readable, multilingual study material.', tint: '#EAE2D3', tag: 'Enhancement & extraction' },
  { id: 'audio', icon: '≋', label: 'Audio tutor', subtitle: 'MAKE ROOM FOR CURIOSITY.', description: 'Ask questions and listen to explanations in the language you learn best.', tint: '#E1DFEB', tag: 'Conversational learning' },
] as const;
