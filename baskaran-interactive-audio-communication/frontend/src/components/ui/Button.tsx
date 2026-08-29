import { type ButtonHTMLAttributes, forwardRef } from 'react'
import { clsx } from 'clsx'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading, children, className, disabled, ...props }, ref) => {
    const base =
      'inline-flex items-center justify-center font-bold rounded-[13px] transition-all duration-150 ' +
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ' +
      'disabled:opacity-45 disabled:cursor-not-allowed select-none ' +
      'active:not(:disabled):opacity-[0.78] active:not(:disabled):scale-[0.99]'

    const variants: Record<string, string> = {
      primary:   'text-white border-none',
      secondary: 'border',
      ghost:     'border',
      danger:    'border',
    }

    const variantStyles: Record<string, React.CSSProperties> = {
      primary:   { background: 'var(--primary)', color: '#ffffff', border: 'none' },
      secondary: { background: 'var(--surface-soft)', border: '1px solid var(--border)', color: 'var(--text)' },
      ghost:     { background: 'var(--surface-soft)', border: '1px solid var(--border)', color: 'var(--text-muted)' },
      danger:    { background: 'var(--danger-soft)',  border: '1px solid var(--danger-border)', color: 'var(--danger)' },
    }

    const sizes: Record<string, string> = {
      sm: 'min-h-[36px] px-[14px] text-[13px] gap-[6px]',
      md: 'min-h-[46px] px-[18px] text-[14px] gap-[8px]',
      lg: 'min-h-[52px] px-[22px] text-[15px] gap-[8px]',
    }

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={clsx(base, variants[variant], sizes[size], className)}
        style={variantStyles[variant]}
        {...props}
      >
        {loading && (
          <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
            <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="4" className="opacity-75" strokeLinecap="round" />
          </svg>
        )}
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'
