import { cn } from '../../lib/cn';

interface ProgressProps {
  value: number;
  max?: number;
  className?: string;
  showLabel?: boolean;
}

export function Progress({ value, max = 100, className, showLabel = false }: ProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div className={cn('w-full', className)}>
      {showLabel && (
        <div className="flex justify-between text-xs text-text-secondary mb-1 font-mono">
          <span>Progress</span>
          <span className="text-neon-cyan">{Math.round(percentage)}%</span>
        </div>
      )}
      <div className="w-full h-2 bg-cyber-bg-surface rounded-full overflow-hidden border border-cyber-border">
        <div
          className="h-full bg-gradient-to-r from-neon-cyan to-neon-cyan-dim rounded-full transition-all duration-500 ease-out relative"
          style={{ width: `${percentage}%` }}
        >
          {percentage > 0 && percentage < 100 && (
            <div className="absolute right-0 top-0 bottom-0 w-2 bg-neon-cyan rounded-full animate-pulse shadow-neon-sm" />
          )}
        </div>
      </div>
    </div>
  );
}
