import { cn } from '../../lib/cn';

interface ToggleProps {
  enabled: boolean;
  onChange: (val: boolean) => void;
  label?: string;
  description?: string;
  disabled?: boolean;
}

export function Toggle({ enabled, onChange, label, description, disabled }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      disabled={disabled}
      onClick={() => onChange(!enabled)}
      className={cn(
        'flex items-center gap-3 text-left',
        disabled && 'opacity-50 pointer-events-none',
        'cursor-pointer',
      )}
    >
      <div
        className={cn(
          'relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150',
          enabled ? 'bg-accent' : 'bg-surface-4',
        )}
      >
        <div
          className={cn(
            'absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-150',
            enabled ? 'translate-x-[22px]' : 'translate-x-0.5',
          )}
        />
      </div>
      {(label || description) && (
        <div>
          {label && <p className="text-sm font-medium text-text-primary">{label}</p>}
          {description && <p className="text-xs text-text-muted">{description}</p>}
        </div>
      )}
    </button>
  );
}
