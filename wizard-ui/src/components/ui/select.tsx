import { type SelectHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../lib/cn';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: Array<{ value: string; label: string }>;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, options, ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label className="text-sm font-medium text-text-secondary">{label}</label>
        )}
        <select
          ref={ref}
          className={cn(
            'w-full rounded-lg border border-cyber-border bg-cyber-bg-surface px-4 py-2.5 text-sm text-text-primary font-mono',
            'focus:outline-none focus:ring-2 focus:ring-neon-cyan focus:border-transparent focus:shadow-neon-sm',
            'transition-all duration-200 cursor-pointer appearance-none',
            className
          )}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    );
  }
);

Select.displayName = 'Select';
