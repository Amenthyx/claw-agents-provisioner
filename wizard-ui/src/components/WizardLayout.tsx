import { type ReactNode } from 'react';
import { ChevronLeft, ChevronRight, Rocket } from 'lucide-react';
import { Button } from './ui/button';
import { StepIndicator } from './ui/step-indicator';

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
  const isReviewStep = currentStep === 7;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-cyber-border bg-cyber-bg/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-cyan to-neon-cyan-dim flex items-center justify-center shadow-neon-md">
              <span className="text-cyber-bg font-bold text-sm">X</span>
            </div>
            <span className="text-lg font-bold text-text-primary">
              <span className="text-glow-cyan">XClaw</span>{' '}
              <span className="text-text-secondary font-normal text-sm">Provisioner</span>
            </span>
          </div>
          <div className="text-sm text-text-secondary font-mono">
            [STEP {String(currentStep + 1).padStart(2, '0')}/{String(totalSteps).padStart(2, '0')}]
          </div>
        </div>
        {/* Gradient line */}
        <div className="h-px bg-gradient-to-r from-transparent via-neon-cyan/40 to-transparent" />
      </header>

      {/* Step Indicator */}
      <StepIndicator currentStep={currentStep} />

      {/* Content */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-8">
        {children}
      </main>

      {/* Navigation Footer */}
      {!isDeployStep && (
        <footer className="border-t border-cyber-border bg-cyber-bg/90 backdrop-blur-sm sticky bottom-0">
          {/* Gradient line */}
          <div className="h-px bg-gradient-to-r from-transparent via-neon-cyan/40 to-transparent" />
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

            {isReviewStep ? (
              <Button
                size="lg"
                onClick={onNext}
                disabled={!canProceed || isLastStep}
                className="bg-gradient-to-r from-neon-cyan to-neon-magenta text-cyber-bg font-semibold hover:shadow-neon-lg active:scale-[0.97]"
              >
                <Rocket className="w-4 h-4" />
                Deploy
              </Button>
            ) : (
              <Button
                variant="primary"
                size="lg"
                onClick={onNext}
                disabled={!canProceed || isLastStep}
              >
                Continue
                <ChevronRight className="w-4 h-4" />
              </Button>
            )}
          </div>
        </footer>
      )}
    </div>
  );
}
