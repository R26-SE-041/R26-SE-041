'use client'

import { clsx } from 'clsx'
import type { Language } from '@/types'

interface LanguageSelectorProps {
  value: Language
  onChange: (language: Language) => void
  disabled?: boolean
}

const LANGUAGES: Array<{ value: Language; label: string; native: string }> = [
  { value: 'english', label: 'English', native: 'Full English' },
  { value: 'tamil', label: 'Tamil', native: 'தமிழ்' },
  { value: 'sinhala', label: 'Sinhala', native: 'සිංහල' },
]

export function LanguageSelector({ value, onChange, disabled = false }: LanguageSelectorProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Response language">
      {LANGUAGES.map((language) => {
        const selected = value === language.value
        return (
          <button
            key={language.value}
            id={`lang-${language.value}`}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(language.value)}
            className={clsx(
              'relative flex min-h-24 flex-col items-start justify-center rounded-2xl border px-5 text-left transition-all',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:pointer-events-none disabled:opacity-50',
              selected
                ? 'border-brand-400/70 bg-brand-500/15 shadow-brand'
                : 'border-white/10 bg-white/[0.025] hover:border-white/20 hover:bg-white/[0.05]',
            )}
          >
            {selected && <span className="absolute right-4 top-4 h-2 w-2 rounded-full bg-brand-300" />}
            <span className="text-sm font-semibold text-white/90">{language.label}</span>
            <span className="mt-1 text-sm text-white/45">{language.native}</span>
          </button>
        )
      })}
    </div>
  )
}
