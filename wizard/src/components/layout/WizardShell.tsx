import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { StepHeader } from './StepHeader';
import { StepFooter } from './StepFooter';
import { StepTransition } from './StepTransition';
import { useWizard } from '../../state/context';

interface WizardShellProps {
  children: ReactNode;
}

export function WizardShell({ children }: WizardShellProps) {
  const { state } = useWizard();

  return (
    <div className="flex h-screen overflow-hidden bg-surface-0">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-8 py-8">
            <StepHeader />
            <StepTransition stepKey={state.currentStep}>
              {children}
            </StepTransition>
          </div>
        </main>
        <StepFooter />
      </div>
    </div>
  );
}
