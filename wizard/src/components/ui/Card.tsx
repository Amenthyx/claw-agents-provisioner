import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';
import { cn } from '../../lib/cn';

/* ── Base Card ────────────────────────────────────────────── */

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('rounded-xl border border-border-base bg-surface-1 p-5', className)}
    {...props}
  >
    {children}
  </div>
));
Card.displayName = 'Card';

/* ── Selection Card ───────────────────────────────────────── */

interface SelectionCardProps extends HTMLAttributes<HTMLDivElement> {
  selected?: boolean;
  disabled?: boolean;
  children: ReactNode;
}

export const SelectionCard = forwardRef<HTMLDivElement, SelectionCardProps>(
  ({ selected, disabled, className, children, onClick, ...props }, ref) => (
    <div
      ref={ref}
      role="button"
      tabIndex={disabled ? -1 : 0}
      onClick={disabled ? undefined : onClick}
      onKeyDown={(e) => {
        if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick?.(e as unknown as React.MouseEvent<HTMLDivElement>);
        }
      }}
      className={cn(
        'rounded-xl border bg-surface-1 p-5 transition-all duration-150',
        'hover:bg-surface-2',
        selected
          ? 'border-accent bg-accent/[0.03] ring-1 ring-accent/30'
          : 'border-border-base',
        disabled && 'opacity-50 pointer-events-none',
        !disabled && 'cursor-pointer',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  ),
);
SelectionCard.displayName = 'SelectionCard';

/* ── Stat Card ────────────────────────────────────────────── */

interface StatCardProps {
  icon: ReactNode;
  label: string;
  value: string;
  className?: string;
}

export function StatCard({ icon, label, value, className }: StatCardProps) {
  return (
    <div className={cn('rounded-xl border border-border-base bg-surface-1 p-4', className)}>
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-3 text-text-muted">
          {icon}
        </div>
        <div>
          <p className="text-xs text-text-muted">{label}</p>
          <p className="text-sm font-medium text-text-primary">{value}</p>
        </div>
      </div>
    </div>
  );
}
