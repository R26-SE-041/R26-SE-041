'use client'

import type { Language } from '@/types'

interface LanguageSelectorProps {
  value: Language
  onChange: (language: Language) => void
  disabled?: boolean
}

const LANGUAGES: Array<{ value: Language; label: string; native: string; flag: string }> = [
  { value: 'english', label: 'English', native: 'EN',    flag: '🇬🇧' },
  { value: 'tamil',   label: 'Tamil',   native: 'தமிழ்', flag: '🇮🇳' },
  { value: 'sinhala', label: 'Sinhala', native: 'සිං',   flag: '🇱🇰' },
]

export function LanguageSelector({ value, onChange, disabled }: LanguageSelectorProps) {
  return (
    <div className="flex flex-row gap-2 flex-wrap">
      {LANGUAGES.map((lang) => {
        const active = value === lang.value
        return (
          <button
            key={lang.value}
            onClick={() => !disabled && onChange(lang.value)}
            disabled={disabled}
            aria-pressed={active}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 14px',
              borderRadius: 50,
              fontSize: 13,
              fontWeight: active ? 600 : 500,
              cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.45 : 1,
              transition: 'all 0.15s ease',
              background: active ? 'var(--primary-soft)' : 'var(--surface-soft)',
              border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
              color: active ? 'var(--primary)' : 'var(--text-muted)',
              whiteSpace: 'nowrap',
            }}
          >
            <span>{lang.label}</span>
            {active && (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
          </button>
        )
      })}
    </div>
  )
}
