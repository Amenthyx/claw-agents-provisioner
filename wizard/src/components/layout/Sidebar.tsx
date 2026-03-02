import {
  Sparkles, Cpu, Layers, Container, Brain,
  Boxes, Route, Shield, Database, MessageSquare, ClipboardCheck, Rocket,
  Check,
} from 'lucide-react';
import { cn } from '../../lib/cn';
import { useWizard } from '../../state/context';
import { STEPS } from '../../data/steps';
import { Progress } from '../ui/Progress';

const ICONS = [Sparkles, Cpu, Layers, Container, Brain, Boxes, Route, Shield, Database, MessageSquare, ClipboardCheck, Rocket];

export function Sidebar() {
  const { state, goToStep, progress } = useWizard();

  return (
    <aside className="flex w-[260px] shrink-0 flex-col border-r border-border-base bg-surface-0">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 pt-6 pb-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-white">
          <Sparkles size={16} />
        </div>
        <span className="text-base font-semibold tracking-tight text-text-primary">XClaw</span>
      </div>

      {/* Step List */}
      <nav className="flex-1 overflow-y-auto px-3 py-2">
        <ul className="space-y-0.5">
          {STEPS.map((step, i) => {
            const Icon = ICONS[i] ?? Sparkles;
            const isCurrent = i === state.currentStep;
            const isCompleted = i < state.currentStep;
            const isClickable = i <= state.currentStep;

            return (
              <li key={step.id}>
                <button
                  type="button"
                  onClick={() => isClickable && goToStep(i)}
                  disabled={!isClickable}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors duration-150',
                    'cursor-pointer',
                    isCurrent && 'bg-accent/10 text-accent font-medium',
                    isCompleted && !isCurrent && 'text-text-secondary hover:bg-surface-2',
                    !isClickable && 'text-text-muted opacity-50 cursor-default',
                    isClickable && !isCurrent && 'hover:bg-surface-2',
                  )}
                >
                  <span
                    className={cn(
                      'flex h-7 w-7 shrink-0 items-center justify-center rounded-md',
                      isCurrent && 'bg-accent/15 text-accent',
                      isCompleted && !isCurrent && 'bg-success/10 text-success',
                      !isCurrent && !isCompleted && 'bg-surface-3 text-text-muted',
                    )}
                  >
                    {isCompleted && !isCurrent ? <Check size={14} /> : <Icon size={14} />}
                  </span>
                  <span className="truncate">{step.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Progress */}
      <div className="border-t border-border-base px-5 py-4">
        <div className="flex items-center justify-between text-xs text-text-muted mb-2">
          <span>Progress</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <Progress value={progress} size="sm" />
      </div>
    </aside>
  );
}
