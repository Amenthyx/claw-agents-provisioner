import { useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { WizardLayout } from './components/WizardLayout';
import { StepWelcome } from './components/steps/StepWelcome';
import { StepPlatform } from './components/steps/StepPlatform';
import { StepDeployment } from './components/steps/StepDeployment';
import { StepLLM } from './components/steps/StepLLM';
import { StepHardware } from './components/steps/StepHardware';
import { StepModels } from './components/steps/StepModels';
import { StepSecurity } from './components/steps/StepSecurity';
import { StepGateway } from './components/steps/StepGateway';
import { StepReview } from './components/steps/StepReview';
import { StepDeploy } from './components/steps/StepDeploy';
import { useWizardState } from './hooks/useWizardState';
import { pageVariants, pageTransition } from './lib/motion';

function App() {
  const {
    state,
    updateState,
    nextStep,
    prevStep,
    goToStep,
    canProceed,
    getAssessmentJSON,
    totalSteps,
  } = useWizardState();

  const handleToggleModel = useCallback(
    (modelName: string) => {
      updateState({
        selectedModels: state.selectedModels.includes(modelName)
          ? state.selectedModels.filter((m) => m !== modelName)
          : [...state.selectedModels, modelName],
      });
    },
    [state.selectedModels, updateState]
  );

  const handleToggleSecurityFeature = useCallback(
    (featureId: string) => {
      updateState({
        securityFeatures: state.securityFeatures.includes(featureId)
          ? state.securityFeatures.filter((f) => f !== featureId)
          : [...state.securityFeatures, featureId],
      });
    },
    [state.securityFeatures, updateState]
  );

  const handleDeploy = useCallback(() => {
    goToStep(9);
  }, [goToStep]);

  const renderStep = () => {
    switch (state.currentStep) {
      case 0:
        return <StepWelcome onNext={nextStep} />;

      case 1:
        return (
          <StepPlatform
            selected={state.platform}
            onSelect={(id) => updateState({ platform: id })}
          />
        );

      case 2:
        return (
          <StepDeployment
            selected={state.deploymentMethod}
            onSelect={(method) => updateState({ deploymentMethod: method })}
          />
        );

      case 3:
        return (
          <StepLLM
            selected={state.llmProvider}
            onSelect={(provider) => updateState({ llmProvider: provider })}
            runtime={state.runtime}
            onRuntimeChange={(runtime) => updateState({ runtime })}
            cloudProviders={state.cloudProviders}
            onCloudProvidersChange={(cloudProviders) => updateState({ cloudProviders })}
            apiKeys={state.apiKeys}
            onApiKeysChange={(apiKeys) => updateState({ apiKeys })}
          />
        );

      case 4:
        return <StepHardware />;

      case 5:
        return (
          <StepModels
            llmProvider={state.llmProvider}
            selectedModels={state.selectedModels}
            onToggleModel={handleToggleModel}
            availableVram={10}
          />
        );

      case 6:
        return (
          <StepSecurity
            enabled={state.securityEnabled}
            onToggleEnabled={() =>
              updateState({ securityEnabled: !state.securityEnabled })
            }
            features={state.securityFeatures}
            onToggleFeature={handleToggleSecurityFeature}
          />
        );

      case 7:
        return (
          <StepGateway
            config={state.gateway}
            onChange={(gateway) => updateState({ gateway })}
            selectedPlatform={state.platform}
          />
        );

      case 8:
        return (
          <StepReview
            state={state}
            assessmentJSON={getAssessmentJSON()}
            onGoToStep={goToStep}
            onDeploy={handleDeploy}
          />
        );

      case 9:
        return (
          <StepDeploy
            assessmentJSON={getAssessmentJSON()}
            platform={state.platform}
            gatewayPort={state.gateway.port}
          />
        );

      default:
        return null;
    }
  };

  return (
    <WizardLayout
      currentStep={state.currentStep}
      totalSteps={totalSteps}
      canProceed={canProceed()}
      onNext={nextStep}
      onPrev={prevStep}
      onGoToStep={goToStep}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={state.currentStep}
          variants={pageVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={pageTransition}
        >
          {renderStep()}
        </motion.div>
      </AnimatePresence>
    </WizardLayout>
  );
}

export default App;
