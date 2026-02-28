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
          <label className="text-sm font-medium text-[#a0a0a0]">{label}</label>
        )}
        <select
          ref={ref}
          className={cn(
            'w-full rounded-lg border border-[#2a2a4e] bg-[#1a1a2e] px-4 py-2.5 text-sm text-[#e0e0e0]',
            'focus:outline-none focus:ring-2 focus:ring-[#00d4aa] focus:border-transparent',
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
