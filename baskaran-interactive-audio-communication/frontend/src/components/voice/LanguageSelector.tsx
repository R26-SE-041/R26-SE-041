'use client'

import { clsx } from 'clsx'
import type { Language } from '@/types'

interface LanguageSelectorProps {
  value: Language
  onChange: (lang: Language) => void
  disabled?: boolean
}

const LANGUAGES = [
  { value: 'english' as Language, label: 'English', native: 'Full English',         flag: '🇬🇧' },
  { value: 'tamil'   as Language, label: 'Tamil',   native: 'தமிழ்',                flag: '🇮🇳' },
  { value: 'sinhala' as Language, label: 'Sinhala', native: 'සිංහල',               flag: '🇱🇰' },
  { value: 'mixed'   as Language, label: 'Mixed',   native: 'Thanglish / Singlish', flag: '🌐' },
]

export function LanguageSelector({ value, onChange, disabled = false }: LanguageSelectorProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" role="group" aria-label="Language mode">
      {LANGUAGES.map((lang) => {
        const active = value === lang.value
        return (
          <button
            key={lang.value}
            id={`lang-${lang.value}`}
            type="button"
            disabled={disabled}
            onClick={() => !disabled && onChange(lang.value)}
            aria-pressed={active}
            className={clsx(
              'relative flex flex-col items-center justify-center gap-1.5 py-4 px-2 rounded-2xl border transition-all duration-200 select-none',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-900',
              'disabled:opacity-40 disabled:pointer-events-none',
              active ? 'lang-btn-active' : 'lang-btn'
            )}
          >
            {/* Active dot */}
            {active && (
              <span className="absolute top-2.5 right-2.5 w-1.5 h-1.5 rounded-full bg-brand-400" />
            )}

            {/* Flag */}
            <span
              className={clsx('text-2xl transition-transform duration-150', active ? 'scale-110' : 'group-hover:scale-105')}
              role="img"
              aria-label={lang.label}
            >
              {lang.flag}
            </span>

            {/* Name */}
            <span className={clsx('text-sm font-semibold leading-tight', active ? 'text-white' : 'text-white/70')}>
              {lang.label}
            </span>

            {/* Native script */}
            <span className="text-[10px] text-white/35 leading-tight truncate w-full text-center px-1">
              {lang.native}
            </span>
          </button>
        )
      })}
    </div>
  )
}
