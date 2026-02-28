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
        <div className="flex justify-between text-xs text-[#a0a0a0] mb-1">
          <span>Progress</span>
          <span>{Math.round(percentage)}%</span>
        </div>
      )}
      <div className="w-full h-2 bg-[#1a1a2e] rounded-full overflow-hidden border border-[#2a2a4e]">
        <div
          className="h-full bg-gradient-to-r from-[#00d4aa] to-[#00f5c4] rounded-full transition-all duration-500 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
