import { type InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../lib/cn';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label className="text-sm font-medium text-text-secondary">{label}</label>
        )}
        <input
          ref={ref}
          className={cn(
            'w-full rounded-lg border bg-cyber-bg-surface px-4 py-2.5 text-sm text-text-primary placeholder-text-muted font-mono',
            'focus:outline-none focus:ring-2 focus:ring-neon-cyan focus:border-transparent focus:shadow-neon-sm',
            'transition-all duration-200',
            error ? 'border-status-error' : 'border-cyber-border',
            className
          )}
          {...props}
        />
        {error && <p className="text-xs text-status-error">{error}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';
