import type { WizardState, WizardAction, SecurityDetailConfig, StorageConfig } from './types';

export const TOTAL_STEPS = 12;

const defaultSecurityConfig: SecurityDetailConfig = {
  urlFiltering: {
    mode: 'blocklist',
    patterns: [],
  },
  contentRules: {
    blockedKeywords: [],
    allowedKeywords: [],
    forbiddenCategories: [],
    responseInjectionProtection: true,
  },
  piiDetection: {
    types: {
      email: true,
      phone: true,
      ssn: true,
      creditCard: true,
      address: false,
      ipAddress: false,
      name: false,
    },
    action: 'redact',
    customPatterns: [],
  },
  networkRules: {
    allowedPorts: [80, 443, 8080, 11434],
    forbiddenIpRanges: [],
    allowedApiHosts: [],
    requireTls: true,
    tlsMinVersion: '1.2',
  },
};

export const initialState: WizardState = {
  currentStep: 0,
  agentName: '',
  hardware: null,
  hardwareRecommendation: null,
  platform: '',
  deploymentMethod: 'docker',
  llmProvider: 'cloud',
  runtime: '',
  selectedModels: [],
  securityEnabled: false,
  securityFeatures: [],
  securityConfig: defaultSecurityConfig,
  complianceConfig: {
    gdpr: { enabled: false, acknowledgedRules: [] },
    hipaa: { enabled: false, acknowledgedRules: [] },
    'pci-dss': { enabled: false, acknowledgedRules: [] },
    soc2: { enabled: false, acknowledgedRules: [] },
  },
  cloudProviders: [],
  apiKeys: {},
  gateway: {
    port: 9095,
    rateLimit: 120,
    failover: 'local-first',
    routing: 'auto',
    routes: [],
    customLocalEndpoint: '',
  },
  sshCredentials: {
    host: '',
    port: 22,
    username: '',
    authMethod: 'password',
    password: '',
    privateKey: '',
  },
  channels: {},
  storage: {
    engine: 'sqlite',
    instanceDb: {
      engine: 'sqlite',
      sqlite: { path: './data/instance.db' },
      postgresql: { host: 'localhost', port: 5432, dbname: 'xclaw', user: 'xclaw', password: '' },
    },
    sharedDb: {
      enabled: false,
      engine: 'sqlite',
      sqlite: { path: './data/shared/shared.db' },
      postgresql: { host: 'localhost', port: 5432, dbname: 'xclaw_shared', user: 'xclaw', password: '' },
    },
  },
  portConfig: { mode: 'auto' },
};

export function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'NEXT_STEP':
      return { ...state, currentStep: Math.min(state.currentStep + 1, TOTAL_STEPS - 1) };
    case 'PREV_STEP':
      return { ...state, currentStep: Math.max(state.currentStep - 1, 0) };
    case 'GO_TO_STEP':
      return { ...state, currentStep: Math.max(0, Math.min(action.step, TOTAL_STEPS - 1)) };
    case 'SET_AGENT_NAME':
      return { ...state, agentName: action.name };
    case 'SET_HARDWARE':
      return { ...state, hardware: action.hardware, hardwareRecommendation: action.recommendation };
    case 'SET_PLATFORM':
      return { ...state, platform: action.platform };
    case 'SET_DEPLOYMENT_METHOD':
      return { ...state, deploymentMethod: action.method };
    case 'SET_LLM_PROVIDER':
      return { ...state, llmProvider: action.provider };
    case 'SET_RUNTIME':
      return { ...state, runtime: action.runtime };
    case 'TOGGLE_MODEL':
      return {
        ...state,
        selectedModels: state.selectedModels.includes(action.modelId)
          ? state.selectedModels.filter((id) => id !== action.modelId)
          : [...state.selectedModels, action.modelId],
      };
    case 'SET_SECURITY_ENABLED':
      return { ...state, securityEnabled: action.enabled };
    case 'TOGGLE_SECURITY_FEATURE':
      return {
        ...state,
        securityFeatures: state.securityFeatures.includes(action.featureId)
          ? state.securityFeatures.filter((id) => id !== action.featureId)
          : [...state.securityFeatures, action.featureId],
      };
    case 'SET_SECURITY_CONFIG':
      return {
        ...state,
        securityConfig: {
          ...state.securityConfig,
          ...action.config,
        },
      };
    case 'SET_COMPLIANCE_CONFIG': {
      const existing = state.complianceConfig[action.standard] ?? { enabled: false, acknowledgedRules: [] };
      return {
        ...state,
        complianceConfig: {
          ...state.complianceConfig,
          [action.standard]: {
            enabled: action.config.enabled ?? existing.enabled,
            acknowledgedRules: action.config.acknowledgedRules ?? existing.acknowledgedRules,
          },
        },
      };
    }
    case 'SET_CLOUD_PROVIDERS':
      return { ...state, cloudProviders: action.providers };
    case 'SET_API_KEY':
      return { ...state, apiKeys: { ...state.apiKeys, [action.provider]: action.key } };
    case 'SET_GATEWAY':
      return { ...state, gateway: { ...state.gateway, ...action.config } };
    case 'SET_GATEWAY_ROUTES':
      return { ...state, gateway: { ...state.gateway, routes: action.routes } };
    case 'SET_SSH_CREDENTIALS':
      return { ...state, sshCredentials: { ...state.sshCredentials, ...action.creds } };
    case 'SET_CHANNEL': {
      const existing = state.channels[action.channelId] ?? { enabled: false, config: {} };
      return {
        ...state,
        channels: {
          ...state.channels,
          [action.channelId]: { ...existing, ...action.config },
        },
      };
    }
    case 'SET_STORAGE':
      return { ...state, storage: { ...state.storage, ...action.config } as StorageConfig };
    case 'SET_STORAGE_INSTANCE':
      return {
        ...state,
        storage: { ...state.storage, instanceDb: { ...state.storage.instanceDb, ...action.config } },
      };
    case 'SET_STORAGE_SHARED':
      return {
        ...state,
        storage: { ...state.storage, sharedDb: { ...state.storage.sharedDb, ...action.config } },
      };
    case 'SET_PORT_CONFIG':
      return { ...state, portConfig: { ...state.portConfig, ...action.config } };
    default:
      return state;
  }
}
