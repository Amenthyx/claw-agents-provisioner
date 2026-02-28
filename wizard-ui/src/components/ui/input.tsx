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
          <label className="text-sm font-medium text-[#a0a0a0]">{label}</label>
        )}
        <input
          ref={ref}
          className={cn(
            'w-full rounded-lg border bg-[#1a1a2e] px-4 py-2.5 text-sm text-[#e0e0e0] placeholder-[#555]',
            'focus:outline-none focus:ring-2 focus:ring-[#00d4aa] focus:border-transparent',
            'transition-all duration-200',
            error ? 'border-[#ff4757]' : 'border-[#2a2a4e]',
            className
          )}
          {...props}
        />
        {error && <p className="text-xs text-[#ff4757]">{error}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';
