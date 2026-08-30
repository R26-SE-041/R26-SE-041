/**
 * MarkdownContent — zero-dependency inline markdown renderer.
 *
 * Handles:
 *   **bold**, *italic*, `code`
 *   Bullet lists  (-, *, +, •, ●, ▪, ◦)
 *   Numbered lists (1. 2. …)
 *   Headings       (# ## ###)
 *
 * Works for Tamil, Sinhala, and English mixed text.
 * No external packages required.
 */

import React from 'react'

// ── Inline parser (bold / italic / code) ─────────────────────────────────────

function parseInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g
  let last = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index))

    if (match[2] !== undefined) {
      parts.push(
        <strong key={match.index} style={{ fontWeight: 700, color: 'inherit' }}>
          {match[2]}
        </strong>
      )
    } else if (match[3] !== undefined) {
      parts.push(<em key={match.index}>{match[3]}</em>)
    } else if (match[4] !== undefined) {
      parts.push(
        <code
          key={match.index}
          style={{
            background: 'rgba(0,0,0,0.06)',
            padding: '1px 5px',
            borderRadius: 4,
            fontSize: '0.85em',
            fontFamily: 'monospace',
          }}
        >
          {match[4]}
        </code>
      )
    }
    last = match.index + match[0].length
  }

  if (last < text.length) parts.push(text.slice(last))
  return parts
}

// ── Block renderer ────────────────────────────────────────────────────────────

interface MarkdownContentProps {
  content: string
  className?: string
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
  const lines = content.split('\n')
  const elements: React.ReactNode[] = []
  let bulletBuffer: string[] = []
  let numberedBuffer: string[] = []
  let key = 0

  const flushBullets = () => {
    if (bulletBuffer.length === 0) return
    elements.push(
      <ul key={key++} style={{ margin: '6px 0 6px 0', paddingLeft: 0, listStyle: 'none' }}>
        {bulletBuffer.map((item, i) => (
          <li key={i} style={{ display: 'flex', gap: 8, marginBottom: 5, alignItems: 'flex-start' }}>
            <span style={{ color: 'var(--c-blue, #1A73E8)', fontWeight: 700, flexShrink: 0, marginTop: 2 }}>•</span>
            <span style={{ lineHeight: 1.7 }}>{parseInline(item)}</span>
          </li>
        ))}
      </ul>
    )
    bulletBuffer = []
  }

  const flushNumbered = () => {
    if (numberedBuffer.length === 0) return
    elements.push(
      <ol key={key++} style={{ margin: '6px 0 6px 0', paddingLeft: 0, listStyle: 'none' }}>
        {numberedBuffer.map((item, i) => (
          <li key={i} style={{ display: 'flex', gap: 8, marginBottom: 5, alignItems: 'flex-start' }}>
            <span
              style={{
                color: 'var(--c-blue, #1A73E8)',
                fontWeight: 700,
                flexShrink: 0,
                minWidth: 20,
                marginTop: 2,
              }}
            >
              {i + 1}.
            </span>
            <span style={{ lineHeight: 1.7 }}>{parseInline(item)}</span>
          </li>
        ))}
      </ol>
    )
    numberedBuffer = []
  }

  for (const rawLine of lines) {
    const line = rawLine.trim()

    // Empty line → spacer
    if (line === '') {
      flushBullets()
      flushNumbered()
      elements.push(<div key={key++} style={{ height: 5 }} />)
      continue
    }

    // Heading (# ## ###)
    const headingMatch = line.match(/^#{1,3}\s+(.+)$/)
    if (headingMatch) {
      flushBullets()
      flushNumbered()
      elements.push(
        <p key={key++} style={{ fontWeight: 700, margin: '8px 0 4px', lineHeight: 1.5 }}>
          {parseInline(headingMatch[1])}
        </p>
      )
      continue
    }

    // Bullet list
    const bulletMatch = line.match(/^[-*+•●▪◦]\s+(.+)$/)
    if (bulletMatch) {
      flushNumbered()
      bulletBuffer.push(bulletMatch[1])
      continue
    }

    // Numbered list
    const numberedMatch = line.match(/^\d+[.)]\s+(.+)$/)
    if (numberedMatch) {
      flushBullets()
      numberedBuffer.push(numberedMatch[1])
      continue
    }

    // Regular paragraph
    flushBullets()
    flushNumbered()
    elements.push(
      <p key={key++} style={{ margin: '3px 0', lineHeight: 1.75 }}>
        {parseInline(line)}
      </p>
    )
  }

  flushBullets()
  flushNumbered()

  return (
    <div style={{ wordBreak: 'break-word' }} className={className}>
      {elements}
    </div>
  )
}
