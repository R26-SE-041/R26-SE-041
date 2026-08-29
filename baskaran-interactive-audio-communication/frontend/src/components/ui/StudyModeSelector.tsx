'use client'

export type StudyMode = 'document' | 'muscle'

interface StudyModeSelectorProps {
  value: StudyMode
  onChange: (mode: StudyMode) => void
  disabled?: boolean
}

const MODES: Array<{ value: StudyMode; label: string; icon: React.ReactNode }> = [
  {
    value: 'document',
    label: 'Document Study',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
  {
    value: 'muscle',
    label: 'Muscle Tutor',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M18 20V10" />
        <path d="M12 20V4" />
        <path d="M6 20v-6" />
      </svg>
    ),
  },
]

export function StudyModeSelector({ value, onChange, disabled }: StudyModeSelectorProps) {
  return (
    <div
      role="group"
      aria-label="Study mode"
      style={{
        display: 'inline-flex',
        borderRadius: 14,
        padding: 4,
        background: 'var(--c-inset)',
        border: '1.5px solid var(--c-border)',
        gap: 2,
      }}
    >
      {MODES.map((mode) => {
        const active = value === mode.value
        return (
          <button
            key={mode.value}
            type="button"
            onClick={() => !disabled && onChange(mode.value)}
            disabled={disabled}
            aria-pressed={active}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '9px 18px',
              borderRadius: 10,
              fontSize: 13,
              fontWeight: active ? 600 : 500,
              cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.5 : 1,
              transition: 'all 0.18s ease',
              background: active ? 'var(--c-card)' : 'transparent',
              border: `1.5px solid ${active ? 'var(--c-blue-border)' : 'transparent'}`,
              color: active ? 'var(--c-blue)' : 'var(--c-ink-muted)',
              boxShadow: active ? 'var(--shadow-card)' : 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {mode.icon}
            {mode.label}
          </button>
        )
      })}
    </div>
  )
}
