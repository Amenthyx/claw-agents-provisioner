import { ArrowLeft, ArrowRight } from 'lucide-react';
import { useWizard } from '../../state/context';
import { Button } from '../ui/Button';

export function StepFooter() {
  const { state, nextStep, prevStep, canProceedNow, totalSteps } = useWizard();

  if (state.currentStep === 0 || state.currentStep === totalSteps - 1) return null;

  return (
    <div className="shrink-0 border-t border-border-base bg-surface-0 px-8 py-4">
      <div className="mx-auto flex max-w-3xl items-center justify-between">
        <Button
          variant="ghost"
          onClick={prevStep}
          icon={<ArrowLeft size={16} />}
        >
          Back
        </Button>
        <Button
          onClick={nextStep}
          disabled={!canProceedNow}
          iconRight={<ArrowRight size={16} />}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
