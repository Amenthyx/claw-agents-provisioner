import { useState, useCallback } from 'react';
import type { WizardState } from '../lib/types';

const TOTAL_STEPS = 9;

const initialState: WizardState = {
  currentStep: 0,
  platform: '',
  deploymentMethod: 'docker',
  llmProvider: 'cloud',
  runtime: '',
  selectedModels: [],
  securityEnabled: false,
  securityFeatures: [],
  companyName: '',
  industry: '',
  useCase: [],
  budget: 0,
  sensitivity: 'standard',
  apiKeys: {},
  cloudProviders: [],
};

export function useWizardState() {
  const [state, setState] = useState<WizardState>(initialState);

  const nextStep = useCallback(() => {
    setState((prev) => ({
      ...prev,
      currentStep: Math.min(prev.currentStep + 1, TOTAL_STEPS - 1),
    }));
  }, []);

  const prevStep = useCallback(() => {
    setState((prev) => ({
      ...prev,
      currentStep: Math.max(prev.currentStep - 1, 0),
    }));
  }, []);

  const goToStep = useCallback((step: number) => {
    setState((prev) => ({
      ...prev,
      currentStep: Math.max(0, Math.min(step, TOTAL_STEPS - 1)),
    }));
  }, []);

  const updateState = useCallback((updates: Partial<WizardState>) => {
    setState((prev) => ({ ...prev, ...updates }));
  }, []);

  const canProceed = useCallback((): boolean => {
    switch (state.currentStep) {
      case 0: // Welcome
        return true;
      case 1: // Platform
        return state.platform !== '';
      case 2: // Deployment
        return state.deploymentMethod !== undefined;
      case 3: // LLM
        if (state.llmProvider === 'hybrid') {
          return state.cloudProviders.length > 0 && state.runtime !== '';
        }
        if (state.llmProvider === 'local') {
          return state.runtime !== '';
        }
        return state.llmProvider !== undefined;
      case 4: // Hardware
        return true; // Auto-detected
      case 5: // Models
        return state.llmProvider === 'cloud' || state.selectedModels.length > 0;
      case 6: // Security
        return true; // Optional
      case 7: // Review
        return true;
      case 8: // Deploy
        return false; // No next step
      default:
        return false;
    }
  }, [state]);

  const getAssessmentJSON = useCallback(() => {
    return {
      platform: state.platform,
      deployment: {
        method: state.deploymentMethod,
      },
      llm: {
        provider: state.llmProvider,
        runtime: state.runtime || undefined,
        models: state.selectedModels.length > 0 ? state.selectedModels : undefined,
        cloudProviders: state.cloudProviders.length > 0 ? state.cloudProviders : undefined,
        apiKeys: Object.keys(state.apiKeys).length > 0
          ? Object.fromEntries(
              Object.entries(state.apiKeys).map(([k, v]) => [k, v ? '***configured***' : undefined])
            )
          : undefined,
      },
      security: {
        enabled: state.securityEnabled,
        features: state.securityFeatures,
      },
      organization: {
        company: state.companyName || undefined,
        industry: state.industry || undefined,
        useCase: state.useCase.length > 0 ? state.useCase : undefined,
        budget: state.budget > 0 ? state.budget : undefined,
        sensitivity: state.sensitivity,
      },
    };
  }, [state]);

  return {
    state,
    setState,
    updateState,
    nextStep,
    prevStep,
    goToStep,
    canProceed,
    getAssessmentJSON,
    totalSteps: TOTAL_STEPS,
  };
}
