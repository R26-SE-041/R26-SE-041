import type { Upload } from '../../FilePicker';
import type { Turn } from './types';
export function voiceForm(upload: Upload, language: string, sessionId?: string): FormData;
export function historyForm(turn: Turn, audio?: Blob): FormData;
