import { useWizard } from '../../state/context';
import { STEPS } from '../../data/steps';

export function StepHeader() {
  const { state, totalSteps } = useWizard();
  const step = STEPS[state.currentStep];
  if (!step || state.currentStep === 0) return null;

  return (
    <div className="mb-6">
      <p className="text-xs font-medium uppercase tracking-widest text-accent mb-1.5">
        Step {state.currentStep} of {totalSteps - 1}
      </p>
      <h2 className="text-xl font-semibold text-text-primary">{step.label}</h2>
      <p className="text-sm text-text-secondary mt-1">{step.description}</p>
    </div>
  );
}
