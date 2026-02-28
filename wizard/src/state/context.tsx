import { createContext, useContext, useReducer, useMemo, useCallback, type ReactNode } from 'react';
import type {
  WizardState, WizardAction, HardwareProfile, RuntimeRecommendation,
  GatewayConfig, SshCredentials, SecurityDetailConfig, ComplianceStandardConfig,
  RoutingRule, ChannelConfig, StorageConfig, PortConfig,
} from './types';
import { wizardReducer, initialState, TOTAL_STEPS } from './reducer';
import { canProceed, getAssessmentJSON } from './validation';
import { STEPS } from '../data/steps';

interface WizardContextValue {
  state: WizardState;
  dispatch: React.Dispatch<WizardAction>;
  nextStep: () => void;
  prevStep: () => void;
  goToStep: (step: number) => void;
  setAgentName: (name: string) => void;
  setHardware: (hw: HardwareProfile, rec: RuntimeRecommendation) => void;
  setPlatform: (id: string) => void;
  setDeploymentMethod: (method: string) => void;
  setLlmProvider: (provider: string) => void;
  setRuntime: (runtime: string) => void;
  toggleModel: (modelId: string) => void;
  setSecurityEnabled: (enabled: boolean) => void;
  toggleSecurityFeature: (featureId: string) => void;
  setSecurityConfig: (config: Partial<SecurityDetailConfig>) => void;
  setComplianceConfig: (standard: string, config: Partial<ComplianceStandardConfig>) => void;
  setCloudProviders: (providers: string[]) => void;
  setApiKey: (provider: string, key: string) => void;
  setGateway: (config: Partial<GatewayConfig>) => void;
  setGatewayRoutes: (routes: RoutingRule[]) => void;
  setSshCredentials: (creds: Partial<SshCredentials>) => void;
  setChannel: (channelId: string, config: Partial<ChannelConfig>) => void;
  setStorage: (config: Partial<StorageConfig>) => void;
  setStorageInstance: (config: Partial<StorageConfig['instanceDb']>) => void;
  setStorageShared: (config: Partial<StorageConfig['sharedDb']>) => void;
  setPortConfig: (config: Partial<PortConfig>) => void;
  canProceedNow: boolean;
  totalSteps: number;
  stepLabel: string;
  progress: number;
  assessmentJSON: Record<string, unknown>;
}

const WizardContext = createContext<WizardContextValue | null>(null);

export function WizardProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(wizardReducer, initialState);

  const nextStep = useCallback(() => dispatch({ type: 'NEXT_STEP' }), []);
  const prevStep = useCallback(() => dispatch({ type: 'PREV_STEP' }), []);
  const goToStep = useCallback((step: number) => dispatch({ type: 'GO_TO_STEP', step }), []);
  const setAgentName = useCallback((name: string) => dispatch({ type: 'SET_AGENT_NAME', name }), []);
  const setHardware = useCallback(
    (hw: HardwareProfile, rec: RuntimeRecommendation) =>
      dispatch({ type: 'SET_HARDWARE', hardware: hw, recommendation: rec }),
    [],
  );
  const setPlatform = useCallback((id: string) => dispatch({ type: 'SET_PLATFORM', platform: id }), []);
  const setDeploymentMethod = useCallback((method: string) => dispatch({ type: 'SET_DEPLOYMENT_METHOD', method }), []);
  const setLlmProvider = useCallback((provider: string) => dispatch({ type: 'SET_LLM_PROVIDER', provider }), []);
  const setRuntime = useCallback((runtime: string) => dispatch({ type: 'SET_RUNTIME', runtime }), []);
  const toggleModel = useCallback((modelId: string) => dispatch({ type: 'TOGGLE_MODEL', modelId }), []);
  const setSecurityEnabled = useCallback((enabled: boolean) => dispatch({ type: 'SET_SECURITY_ENABLED', enabled }), []);
  const toggleSecurityFeature = useCallback(
    (featureId: string) => dispatch({ type: 'TOGGLE_SECURITY_FEATURE', featureId }),
    [],
  );
  const setSecurityConfig = useCallback(
    (config: Partial<SecurityDetailConfig>) => dispatch({ type: 'SET_SECURITY_CONFIG', config }),
    [],
  );
  const setComplianceConfig = useCallback(
    (standard: string, config: Partial<ComplianceStandardConfig>) =>
      dispatch({ type: 'SET_COMPLIANCE_CONFIG', standard, config }),
    [],
  );
  const setCloudProviders = useCallback(
    (providers: string[]) => dispatch({ type: 'SET_CLOUD_PROVIDERS', providers }),
    [],
  );
  const setApiKey = useCallback(
    (provider: string, key: string) => dispatch({ type: 'SET_API_KEY', provider, key }),
    [],
  );
  const setGateway = useCallback(
    (config: Partial<GatewayConfig>) => dispatch({ type: 'SET_GATEWAY', config }),
    [],
  );
  const setGatewayRoutes = useCallback(
    (routes: RoutingRule[]) => dispatch({ type: 'SET_GATEWAY_ROUTES', routes }),
    [],
  );
  const setSshCredentials = useCallback(
    (creds: Partial<SshCredentials>) => dispatch({ type: 'SET_SSH_CREDENTIALS', creds }),
    [],
  );
  const setChannel = useCallback(
    (channelId: string, config: Partial<ChannelConfig>) =>
      dispatch({ type: 'SET_CHANNEL', channelId, config }),
    [],
  );
  const setStorage = useCallback(
    (config: Partial<StorageConfig>) => dispatch({ type: 'SET_STORAGE', config }),
    [],
  );
  const setStorageInstance = useCallback(
    (config: Partial<StorageConfig['instanceDb']>) => dispatch({ type: 'SET_STORAGE_INSTANCE', config }),
    [],
  );
  const setStorageShared = useCallback(
    (config: Partial<StorageConfig['sharedDb']>) => dispatch({ type: 'SET_STORAGE_SHARED', config }),
    [],
  );
  const setPortConfig = useCallback(
    (config: Partial<PortConfig>) => dispatch({ type: 'SET_PORT_CONFIG', config }),
    [],
  );

  const value = useMemo<WizardContextValue>(() => {
    const step = STEPS[state.currentStep];
    return {
      state,
      dispatch,
      nextStep,
      prevStep,
      goToStep,
      setAgentName,
      setHardware,
      setPlatform,
      setDeploymentMethod,
      setLlmProvider,
      setRuntime,
      toggleModel,
      setSecurityEnabled,
      toggleSecurityFeature,
      setSecurityConfig,
      setComplianceConfig,
      setCloudProviders,
      setApiKey,
      setGateway,
      setGatewayRoutes,
      setSshCredentials,
      setChannel,
      setStorage,
      setStorageInstance,
      setStorageShared,
      setPortConfig,
      canProceedNow: canProceed(state),
      totalSteps: TOTAL_STEPS,
      stepLabel: step?.label ?? '',
      progress: ((state.currentStep + 1) / TOTAL_STEPS) * 100,
      assessmentJSON: getAssessmentJSON(state),
    };
  }, [state, nextStep, prevStep, goToStep, setAgentName, setHardware, setPlatform, setDeploymentMethod, setLlmProvider, setRuntime, toggleModel, setSecurityEnabled, toggleSecurityFeature, setSecurityConfig, setComplianceConfig, setCloudProviders, setApiKey, setGateway, setGatewayRoutes, setSshCredentials, setChannel, setStorage, setStorageInstance, setStorageShared, setPortConfig]);

  return <WizardContext.Provider value={value}>{children}</WizardContext.Provider>;
}

export function useWizard(): WizardContextValue {
  const ctx = useContext(WizardContext);
  if (!ctx) throw new Error('useWizard must be used within WizardProvider');
  return ctx;
}
