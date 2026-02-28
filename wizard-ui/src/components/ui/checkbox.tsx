import { type InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../lib/cn';
import { Check } from 'lucide-react';

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  description?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, description, checked, onChange, ...props }, ref) => {
    return (
      <label
        className={cn(
          'flex items-start gap-3 cursor-pointer group',
          className
        )}
      >
        <div className="relative mt-0.5">
          <input
            ref={ref}
            type="checkbox"
            className="sr-only peer"
            checked={checked}
            onChange={onChange}
            {...props}
          />
          <div
            className={cn(
              'w-5 h-5 rounded border-2 flex items-center justify-center transition-all duration-200',
              checked
                ? 'bg-[#00d4aa] border-[#00d4aa]'
                : 'bg-transparent border-[#2a2a4e] group-hover:border-[#00d4aa]/50'
            )}
          >
            {checked && <Check className="w-3 h-3 text-[#0a0a0f]" strokeWidth={3} />}
          </div>
        </div>
        {(label || description) && (
          <div className="flex flex-col">
            {label && (
              <span className="text-sm font-medium text-[#e0e0e0]">{label}</span>
            )}
            {description && (
              <span className="text-xs text-[#a0a0a0] mt-0.5">{description}</span>
            )}
          </div>
        )}
      </label>
    );
  }
);

Checkbox.displayName = 'Checkbox';
