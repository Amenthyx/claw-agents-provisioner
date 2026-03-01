import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

const variants = {
  default: 'bg-surface-3 text-text-secondary border-border-base',
  success: 'bg-success/10 text-success border-success/20',
  warning: 'bg-warning/10 text-warning border-warning/20',
  error: 'bg-error/10 text-error border-error/20',
  accent: 'bg-accent/10 text-accent border-accent/20',
  secondary: 'bg-surface-3 text-text-secondary border-border-subtle',
  muted: 'bg-surface-2 text-text-muted border-border-subtle',
} as const;

interface BadgeProps {
  variant?: keyof typeof variants;
  children: ReactNode;
  dot?: string;
  className?: string;
}

export function Badge({ variant = 'default', children, dot, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        variants[variant],
        className,
      )}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full" style={{ background: dot }} />}
      {children}
    </span>
  );
}
