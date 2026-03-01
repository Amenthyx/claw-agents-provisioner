import { Check } from 'lucide-react';
import { cn } from '../../lib/cn';

interface CheckboxProps {
  checked: boolean;
  onChange: (val: boolean) => void;
  label?: string;
  description?: string;
  disabled?: boolean;
}

export function Checkbox({ checked, onChange, label, description, disabled }: CheckboxProps) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'flex items-start gap-3 text-left',
        disabled && 'opacity-50 pointer-events-none',
        'cursor-pointer',
      )}
    >
      <div
        className={cn(
          'mt-0.5 flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded border transition-all duration-150',
          checked
            ? 'border-accent bg-accent text-white'
            : 'border-border-base bg-surface-2',
        )}
      >
        {checked && <Check size={12} strokeWidth={3} />}
      </div>
      {(label || description) && (
        <div>
          {label && <p className="text-sm font-medium text-text-primary">{label}</p>}
          {description && <p className="text-xs text-text-muted mt-0.5">{description}</p>}
        </div>
      )}
    </button>
  );
}
