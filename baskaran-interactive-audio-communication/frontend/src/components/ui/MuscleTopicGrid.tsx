'use client'

import { useState } from 'react'
import type { Language } from '@/types'
import { getMuscleLocale, type MuscleId } from '@/lib/muscleLocale'

const MUSCLE_IDS: MuscleId[] = [
  'pectoralis-major',
  'deltoid',
  'biceps-brachii',
  'triceps-brachii',
  'quadriceps-femoris',
]

/** Canonical anatomical names — kept in English for clarity across all locales. */
const MUSCLE_CANONICAL_NAMES: Record<MuscleId, string> = {
  'pectoralis-major': 'Pectoralis Major',
  deltoid: 'Deltoid',
  'biceps-brachii': 'Biceps Brachii',
  'triceps-brachii': 'Triceps Brachii',
  'quadriceps-femoris': 'Quadriceps Femoris',
}

interface MuscleTopicGridProps {
  /** Called when a quick-prompt chip is clicked, providing the language-specific prompt text. */
  onPromptSelect: (prompt: string) => void
  /** Currently selected UI/response language. Controls locale of all displayed strings. */
  language: Language
}

export function MuscleTopicGrid({ onPromptSelect, language }: MuscleTopicGridProps) {
  const [selectedMuscle, setSelectedMuscle] = useState<MuscleId | null>(null)

  const locale = getMuscleLocale(language)

  const handleCardClick = (muscleId: MuscleId) => {
    setSelectedMuscle((current) => (current === muscleId ? null : muscleId))
  }

  const selectedMuscleData = selectedMuscle ? locale.muscles[selectedMuscle] : null

  return (
    <div>
      {/* Section header */}
      <div style={{ marginBottom: 16 }}>
        <p
          className="nb-label"
          style={{ color: 'var(--c-blue)', marginBottom: 6 }}
        >
          {locale.ui.specializedTutor}
        </p>
        <p style={{ fontSize: 14, color: 'var(--c-ink-muted)', lineHeight: 1.55 }}>
          {locale.ui.description}
        </p>
      </div>

      {/* Muscle cards grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(172px, 1fr))',
          gap: 10,
        }}
      >
        {MUSCLE_IDS.map((muscleId) => {
          const active = selectedMuscle === muscleId
          const muscleLocale = locale.muscles[muscleId]
          return (
            <button
              key={muscleId}
              type="button"
              onClick={() => handleCardClick(muscleId)}
              aria-pressed={active}
              style={{
                textAlign: 'left',
                padding: '14px 16px',
                borderRadius: 14,
                border: `1.5px solid ${active ? 'var(--c-blue)' : 'var(--c-border)'}`,
                background: active ? 'var(--c-blue-soft)' : 'var(--c-card)',
                boxShadow: active ? 'none' : 'var(--shadow-card)',
                cursor: 'pointer',
                transition: 'all 0.18s ease',
                display: 'flex',
                flexDirection: 'column',
                gap: 5,
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--c-blue-border)'
                  ;(e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-card-md)'
                  ;(e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)'
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--c-border)'
                  ;(e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-card)'
                  ;(e.currentTarget as HTMLElement).style.transform = 'translateY(0)'
                }
              }}
            >
              {/* Active indicator dot */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: active ? 'var(--c-blue)' : 'var(--c-ink)',
                    lineHeight: 1.3,
                  }}
                >
                  {MUSCLE_CANONICAL_NAMES[muscleId]}
                </span>
                {active && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--c-blue)" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </div>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 500,
                  color: active ? 'var(--c-blue)' : 'var(--c-ink-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {muscleLocale.location}
              </span>
              <span
                style={{
                  fontSize: 11,
                  color: active ? 'var(--c-blue)' : 'var(--c-ink-faint)',
                  marginTop: 2,
                  lineHeight: 1.45,
                }}
              >
                {muscleLocale.topics}
              </span>
            </button>
          )
        })}
      </div>

      {/* Quick-prompt chips — shown when a muscle is selected */}
      {selectedMuscle && selectedMuscleData && (
        <div
          className="animate-fade-up"
          style={{ marginTop: 14 }}
        >
          <p
            className="nb-label"
            style={{ marginBottom: 8 }}
          >
            {locale.ui.exampleQuestionsFor} {MUSCLE_CANONICAL_NAMES[selectedMuscle]}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
            {selectedMuscleData.prompts.map((prompt, index) => (
              <button
                key={index}
                type="button"
                onClick={() => onPromptSelect(prompt)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  padding: '7px 13px',
                  borderRadius: 999,
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  background: 'var(--c-blue-soft)',
                  border: '1.5px solid var(--c-blue-border)',
                  color: 'var(--c-blue)',
                  whiteSpace: 'nowrap',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  ;(e.currentTarget as HTMLElement).style.background = 'var(--c-blue)'
                  ;(e.currentTarget as HTMLElement).style.color = '#fff'
                  ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--c-blue)'
                }}
                onMouseLeave={(e) => {
                  ;(e.currentTarget as HTMLElement).style.background = 'var(--c-blue-soft)'
                  ;(e.currentTarget as HTMLElement).style.color = 'var(--c-blue)'
                  ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--c-blue-border)'
                }}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M5 12h14" />
                  <path d="M12 5l7 7-7 7" />
                </svg>
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
