import { clsx } from 'clsx'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  label?: string
}

export function LoadingSpinner({ size = 'md', className, label }: LoadingSpinnerProps) {
  const sizes = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' }

  return (
    <div className={clsx('flex flex-col items-center gap-3', className)} role="status">
      <div className={clsx('relative', sizes[size])}>
        <div className="absolute inset-0 rounded-full border-2" style={{ borderColor: 'var(--c-blue-border)' }} />
        <div className="absolute inset-0 rounded-full border-2 border-transparent animate-spin"
          style={{ borderTopColor: 'var(--c-blue)' }} />
      </div>
      {label && <span className="text-sm" style={{ color: 'var(--c-ink-muted)' }}>{label}</span>}
    </div>
  )
}
