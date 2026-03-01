import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { cn } from '../../lib/cn';

const variants = {
  primary:
    'bg-accent text-white hover:bg-accent-hover shadow-sm shadow-accent/20',
  secondary:
    'bg-surface-3 text-text-primary hover:bg-surface-4 border border-border-base',
  outline:
    'bg-transparent text-text-primary border border-border-base hover:bg-surface-2 hover:border-border-active',
  ghost:
    'bg-transparent text-text-secondary hover:bg-surface-2 hover:text-text-primary',
  danger:
    'bg-error/10 text-error border border-error/20 hover:bg-error/20',
} as const;

const sizes = {
  sm: 'h-8 px-3 text-xs gap-1.5 rounded-md',
  md: 'h-9 px-4 text-sm gap-2 rounded-lg',
  lg: 'h-10 px-5 text-sm gap-2 rounded-lg',
  xl: 'h-12 px-6 text-base gap-2.5 rounded-xl',
} as const;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  icon?: ReactNode;
  iconRight?: ReactNode;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', icon, iconRight, loading, disabled, className, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          'inline-flex items-center justify-center font-medium transition-colors duration-150',
          'disabled:opacity-50 disabled:pointer-events-none',
          'cursor-pointer',
          variants[variant],
          sizes[size],
          className,
        )}
        {...props}
      >
        {loading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        ) : icon ? (
          <span className="shrink-0">{icon}</span>
        ) : null}
        {children}
        {iconRight && <span className="shrink-0">{iconRight}</span>}
      </button>
    );
  },
);
Button.displayName = 'Button';
