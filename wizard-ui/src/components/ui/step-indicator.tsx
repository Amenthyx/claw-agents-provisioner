import { motion } from 'framer-motion';
import { STEP_LABELS } from '../../lib/types';

interface StepIndicatorProps {
  currentStep: number;
}

export function StepIndicator({ currentStep }: StepIndicatorProps) {
  return (
    <div className="border-b border-cyber-border bg-cyber-bg/50">
      <div className="max-w-6xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {STEP_LABELS.map((label, index) => {
            const isComplete = index < currentStep;
            const isCurrent = index === currentStep;
            const isFuture = index > currentStep;

            return (
              <div key={label} className="flex items-center flex-1 last:flex-none">
                <div className="flex flex-col items-center gap-1.5">
                  <motion.div
                    className={`
                      w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold font-mono
                      transition-colors duration-300
                      ${isComplete
                        ? 'bg-neon-cyan text-cyber-bg'
                        : isCurrent
                          ? 'bg-neon-cyan/20 text-neon-cyan border-2 border-neon-cyan'
                          : 'bg-cyber-bg-surface text-text-muted border border-cyber-border'
                      }
                    `}
                    animate={isCurrent ? {
                      boxShadow: [
                        '0 0 4px #00ffcc20, 0 0 8px #00ffcc10',
                        '0 0 12px #00ffcc40, 0 0 24px #00ffcc20, 0 0 4px #00ffcc',
                        '0 0 4px #00ffcc20, 0 0 8px #00ffcc10',
                      ],
                    } : {}}
                    transition={isCurrent ? { duration: 2, repeat: Infinity, ease: 'easeInOut' } : {}}
                  >
                    {isComplete ? (
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                        <polyline points="20,6 9,17 4,12" />
                      </svg>
                    ) : (
                      index + 1
                    )}
                  </motion.div>
                  <span
                    className={`text-[10px] font-medium hidden sm:block font-mono ${
                      isCurrent ? 'text-neon-cyan' : isFuture ? 'text-text-muted' : 'text-text-secondary'
                    }`}
                  >
                    {label}
                  </span>
                </div>
                {index < STEP_LABELS.length - 1 && (
                  <div className="flex-1 h-px mx-2 relative overflow-hidden">
                    <div className="absolute inset-0 bg-cyber-border" />
                    <motion.div
                      className="absolute inset-y-0 left-0 bg-neon-cyan"
                      initial={false}
                      animate={{ width: isComplete ? '100%' : '0%' }}
                      transition={{ duration: 0.4, ease: 'easeOut' }}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
