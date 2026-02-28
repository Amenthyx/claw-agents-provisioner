import { type ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './ui/button';
import { STEP_LABELS } from '../lib/types';

interface WizardLayoutProps {
  currentStep: number;
  totalSteps: number;
  canProceed: boolean;
  onNext: () => void;
  onPrev: () => void;
  onGoToStep: (step: number) => void;
  children: ReactNode;
}

export function WizardLayout({
  currentStep,
  totalSteps,
  canProceed,
  onNext,
  onPrev,
  children,
}: WizardLayoutProps) {
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === totalSteps - 1;
  const isDeployStep = currentStep === 8;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-[#2a2a4e] bg-[#0a0a0f]/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00d4aa] to-[#00f5c4] flex items-center justify-center">
              <span className="text-[#0a0a0f] font-bold text-sm">X</span>
            </div>
            <span className="text-lg font-bold text-[#e0e0e0]">
              XClaw <span className="text-[#a0a0a0] font-normal text-sm">Provisioner</span>
            </span>
          </div>
          <div className="text-sm text-[#a0a0a0]">
            Step {currentStep + 1} of {totalSteps}
          </div>
        </div>
      </header>

      {/* Step Indicator */}
      <div className="border-b border-[#2a2a4e] bg-[#0a0a0f]/50">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {STEP_LABELS.map((label, index) => {
              const isComplete = index < currentStep;
              const isCurrent = index === currentStep;
              const isFuture = index > currentStep;

              return (
                <div key={label} className="flex items-center flex-1 last:flex-none">
                  <div className="flex flex-col items-center gap-1.5">
                    <div
                      className={`
                        w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold
                        transition-all duration-300
                        ${isComplete
                          ? 'bg-[#00d4aa] text-[#0a0a0f]'
                          : isCurrent
                            ? 'bg-[#00d4aa]/20 text-[#00d4aa] border-2 border-[#00d4aa]'
                            : 'bg-[#1a1a2e] text-[#555] border border-[#2a2a4e]'
                        }
                      `}
                    >
                      {isComplete ? (
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                          <polyline points="20,6 9,17 4,12" />
                        </svg>
                      ) : (
                        index + 1
                      )}
                    </div>
                    <span
                      className={`text-[10px] font-medium hidden sm:block ${
                        isCurrent ? 'text-[#00d4aa]' : isFuture ? 'text-[#555]' : 'text-[#a0a0a0]'
                      }`}
                    >
                      {label}
                    </span>
                  </div>
                  {index < STEP_LABELS.length - 1 && (
                    <div
                      className={`flex-1 h-px mx-2 transition-colors duration-300 ${
                        isComplete ? 'bg-[#00d4aa]' : 'bg-[#2a2a4e]'
                      }`}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-8">
        {children}
      </main>

      {/* Navigation Footer */}
      {!isDeployStep && (
        <footer className="border-t border-[#2a2a4e] bg-[#0a0a0f]/90 backdrop-blur-sm sticky bottom-0">
          <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
            <Button
              variant="ghost"
              onClick={onPrev}
              disabled={isFirstStep}
              className={isFirstStep ? 'invisible' : ''}
            >
              <ChevronLeft className="w-4 h-4" />
              Back
            </Button>

            <Button
              variant="primary"
              size="lg"
              onClick={onNext}
              disabled={!canProceed || isLastStep}
            >
              {currentStep === 7 ? 'Deploy' : 'Continue'}
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </footer>
      )}
    </div>
  );
}
