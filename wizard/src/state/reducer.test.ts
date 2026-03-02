/**
 * Tests for the wizard state reducer — pure function, no DOM needed.
 */
import { describe, it, expect } from 'vitest';
import { wizardReducer, initialState, TOTAL_STEPS } from './reducer';
import type { WizardState, WizardAction } from './types';

function dispatch(state: WizardState, action: WizardAction): WizardState {
  return wizardReducer(state, action);
}

describe('wizardReducer', () => {
  describe('navigation', () => {
    it('should start at step 0', () => {
      expect(initialState.currentStep).toBe(0);
    });

    it('NEXT_STEP increments currentStep', () => {
      const state = dispatch(initialState, { type: 'NEXT_STEP' });
      expect(state.currentStep).toBe(1);
    });

    it('PREV_STEP decrements currentStep', () => {
      const atStep2 = { ...initialState, currentStep: 2 };
      const state = dispatch(atStep2, { type: 'PREV_STEP' });
      expect(state.currentStep).toBe(1);
    });

    it('NEXT_STEP does not exceed maximum step', () => {
      const atLastStep = { ...initialState, currentStep: TOTAL_STEPS - 1 };
      const state = dispatch(atLastStep, { type: 'NEXT_STEP' });
      expect(state.currentStep).toBe(TOTAL_STEPS - 1);
    });

    it('PREV_STEP does not go below 0', () => {
      const state = dispatch(initialState, { type: 'PREV_STEP' });
      expect(state.currentStep).toBe(0);
    });

    it('GO_TO_STEP sets exact step', () => {
      const state = dispatch(initialState, { type: 'GO_TO_STEP', step: 5 });
      expect(state.currentStep).toBe(5);
    });

    it('GO_TO_STEP clamps to valid range', () => {
      const tooHigh = dispatch(initialState, { type: 'GO_TO_STEP', step: 999 });
      expect(tooHigh.currentStep).toBe(TOTAL_STEPS - 1);

      const tooLow = dispatch(initialState, { type: 'GO_TO_STEP', step: -5 });
      expect(tooLow.currentStep).toBe(0);
    });
  });

  describe('agent name', () => {
    it('SET_AGENT_NAME updates the name', () => {
      const state = dispatch(initialState, { type: 'SET_AGENT_NAME', name: 'my-agent' });
      expect(state.agentName).toBe('my-agent');
    });

    it('SET_AGENT_NAME can set empty string', () => {
      const withName = { ...initialState, agentName: 'test' };
      const state = dispatch(withName, { type: 'SET_AGENT_NAME', name: '' });
      expect(state.agentName).toBe('');
    });
  });

  describe('platform', () => {
    it('SET_PLATFORM updates the platform', () => {
      const state = dispatch(initialState, { type: 'SET_PLATFORM', platform: 'zeroclaw' });
      expect(state.platform).toBe('zeroclaw');
    });

    it('SET_PLATFORM can change platform', () => {
      const withPlatform = { ...initialState, platform: 'zeroclaw' };
      const state = dispatch(withPlatform, { type: 'SET_PLATFORM', platform: 'nanoclaw' });
      expect(state.platform).toBe('nanoclaw');
    });
  });

  describe('hardware', () => {
    it('SET_HARDWARE stores hardware profile and recommendation', () => {
      const hw = {
        os: 'Windows',
        arch: 'x86_64',
        cpu: { brand: 'Intel i7', cores: 8, features: ['AVX2'] },
        ram: 32,
        gpus: [{ name: 'RTX 4070', vram: 12, api: 'CUDA' }],
      };
      const rec = { primary: 'Ollama', fallback: 'llama.cpp', reason: 'NVIDIA GPU' };
      const state = dispatch(initialState, { type: 'SET_HARDWARE', hardware: hw, recommendation: rec });
      expect(state.hardware).toEqual(hw);
      expect(state.hardwareRecommendation).toEqual(rec);
    });
  });

  describe('deployment method', () => {
    it('SET_DEPLOYMENT_METHOD updates method', () => {
      const state = dispatch(initialState, { type: 'SET_DEPLOYMENT_METHOD', method: 'ssh' });
      expect(state.deploymentMethod).toBe('ssh');
    });

    it('default deployment method is docker', () => {
      expect(initialState.deploymentMethod).toBe('docker');
    });
  });

  describe('LLM provider', () => {
    it('SET_LLM_PROVIDER updates provider', () => {
      const state = dispatch(initialState, { type: 'SET_LLM_PROVIDER', provider: 'local' });
      expect(state.llmProvider).toBe('local');
    });

    it('SET_RUNTIME updates runtime', () => {
      const state = dispatch(initialState, { type: 'SET_RUNTIME', runtime: 'ollama' });
      expect(state.runtime).toBe('ollama');
    });

    it('SET_CLOUD_PROVIDERS updates providers list', () => {
      const state = dispatch(initialState, { type: 'SET_CLOUD_PROVIDERS', providers: ['openai', 'anthropic'] });
      expect(state.cloudProviders).toEqual(['openai', 'anthropic']);
    });

    it('SET_API_KEY stores API key for a provider', () => {
      const state = dispatch(initialState, { type: 'SET_API_KEY', provider: 'openai', key: 'sk-test123' });
      expect(state.apiKeys.openai).toBe('sk-test123');
    });

    it('SET_API_KEY preserves existing keys', () => {
      const withKey = { ...initialState, apiKeys: { openai: 'sk-old' } };
      const state = dispatch(withKey, { type: 'SET_API_KEY', provider: 'anthropic', key: 'sk-ant' });
      expect(state.apiKeys.openai).toBe('sk-old');
      expect(state.apiKeys.anthropic).toBe('sk-ant');
    });
  });

  describe('models', () => {
    it('TOGGLE_MODEL adds a model', () => {
      const state = dispatch(initialState, { type: 'TOGGLE_MODEL', modelId: 'llama3.3:70b' });
      expect(state.selectedModels).toContain('llama3.3:70b');
    });

    it('TOGGLE_MODEL removes a model if already selected', () => {
      const withModel = { ...initialState, selectedModels: ['llama3.3:70b', 'mistral:7b'] };
      const state = dispatch(withModel, { type: 'TOGGLE_MODEL', modelId: 'llama3.3:70b' });
      expect(state.selectedModels).toEqual(['mistral:7b']);
    });

    it('TOGGLE_MODEL adds multiple distinct models', () => {
      let state = dispatch(initialState, { type: 'TOGGLE_MODEL', modelId: 'model-a' });
      state = dispatch(state, { type: 'TOGGLE_MODEL', modelId: 'model-b' });
      expect(state.selectedModels).toEqual(['model-a', 'model-b']);
    });
  });

  describe('strategy', () => {
    it('SET_STRATEGY_OPTIMIZATION updates preset', () => {
      const state = dispatch(initialState, { type: 'SET_STRATEGY_OPTIMIZATION', optimization: 'cost' });
      expect(state.strategy.optimization).toBe('cost');
    });

    it('SET_STRATEGY_RULE adds a new rule', () => {
      const state = dispatch(initialState, {
        type: 'SET_STRATEGY_RULE',
        taskCategory: 'coding',
        primaryModel: 'codestral:22b',
        fallbackModel: 'mistral:7b',
      });
      expect(state.strategy.rules).toHaveLength(1);
      expect(state.strategy.rules[0]).toEqual({
        taskCategory: 'coding',
        primaryModel: 'codestral:22b',
        fallbackModel: 'mistral:7b',
      });
    });

    it('SET_STRATEGY_RULE updates existing rule for same category', () => {
      const withRule = {
        ...initialState,
        strategy: {
          ...initialState.strategy,
          rules: [{ taskCategory: 'coding', primaryModel: 'old', fallbackModel: 'old' }],
        },
      };
      const state = dispatch(withRule, {
        type: 'SET_STRATEGY_RULE',
        taskCategory: 'coding',
        primaryModel: 'new',
        fallbackModel: 'new-fallback',
      });
      expect(state.strategy.rules).toHaveLength(1);
      expect(state.strategy.rules[0]!.primaryModel).toBe('new');
    });

    it('SET_STRATEGY_RULES replaces all rules', () => {
      const rules = [
        { taskCategory: 'coding', primaryModel: 'a', fallbackModel: 'b' },
        { taskCategory: 'reasoning', primaryModel: 'c', fallbackModel: 'd' },
      ];
      const state = dispatch(initialState, { type: 'SET_STRATEGY_RULES', rules });
      expect(state.strategy.rules).toEqual(rules);
    });
  });

  describe('security', () => {
    it('SET_SECURITY_ENABLED toggles security', () => {
      const state = dispatch(initialState, { type: 'SET_SECURITY_ENABLED', enabled: true });
      expect(state.securityEnabled).toBe(true);
    });

    it('TOGGLE_SECURITY_FEATURE adds feature', () => {
      const state = dispatch(initialState, { type: 'TOGGLE_SECURITY_FEATURE', featureId: 'pii-detection' });
      expect(state.securityFeatures).toContain('pii-detection');
    });

    it('TOGGLE_SECURITY_FEATURE removes feature if already present', () => {
      const withFeature = { ...initialState, securityFeatures: ['pii-detection', 'url-filtering'] };
      const state = dispatch(withFeature, { type: 'TOGGLE_SECURITY_FEATURE', featureId: 'pii-detection' });
      expect(state.securityFeatures).toEqual(['url-filtering']);
    });

    it('SET_SECURITY_CONFIG merges partial config', () => {
      const state = dispatch(initialState, {
        type: 'SET_SECURITY_CONFIG',
        config: {
          piiDetection: {
            types: { email: false, phone: true, ssn: true, creditCard: true },
            action: 'block',
            customPatterns: [],
          },
        },
      });
      expect(state.securityConfig.piiDetection.action).toBe('block');
      // Other sections should be preserved
      expect(state.securityConfig.urlFiltering.mode).toBe('blocklist');
    });

    it('SET_COMPLIANCE_CONFIG updates specific standard', () => {
      const state = dispatch(initialState, {
        type: 'SET_COMPLIANCE_CONFIG',
        standard: 'gdpr',
        config: { enabled: true, acknowledgedRules: ['gdpr-1'] },
      });
      expect(state.complianceConfig.gdpr.enabled).toBe(true);
      expect(state.complianceConfig.gdpr.acknowledgedRules).toEqual(['gdpr-1']);
      // Other standards unchanged
      expect(state.complianceConfig.hipaa.enabled).toBe(false);
    });
  });

  describe('gateway', () => {
    it('SET_GATEWAY merges partial config', () => {
      const state = dispatch(initialState, { type: 'SET_GATEWAY', config: { port: 8080, rateLimit: 60 } });
      expect(state.gateway.port).toBe(8080);
      expect(state.gateway.rateLimit).toBe(60);
      // Preserved
      expect(state.gateway.failover).toBe('local-first');
    });

    it('SET_GATEWAY_ROUTES sets routes array', () => {
      const routes = [{ pattern: '/api/*', target: 'local', priority: 1 }];
      const state = dispatch(initialState, { type: 'SET_GATEWAY_ROUTES', routes });
      expect(state.gateway.routes).toEqual(routes);
    });
  });

  describe('SSH credentials', () => {
    it('SET_SSH_CREDENTIALS merges partial creds', () => {
      const state = dispatch(initialState, {
        type: 'SET_SSH_CREDENTIALS',
        creds: { host: '10.0.0.1', username: 'deploy' },
      });
      expect(state.sshCredentials.host).toBe('10.0.0.1');
      expect(state.sshCredentials.username).toBe('deploy');
      // Port preserved
      expect(state.sshCredentials.port).toBe(22);
    });
  });

  describe('channels', () => {
    it('SET_CHANNEL creates channel config', () => {
      const state = dispatch(initialState, {
        type: 'SET_CHANNEL',
        channelId: 'telegram',
        config: { enabled: true, config: { botToken: 'abc' } },
      });
      expect(state.channels.telegram).toEqual({ enabled: true, config: { botToken: 'abc' } });
    });

    it('SET_CHANNEL merges with existing', () => {
      const withChannel = {
        ...initialState,
        channels: { telegram: { enabled: true, config: { botToken: 'abc' } } },
      };
      const state = dispatch(withChannel, {
        type: 'SET_CHANNEL',
        channelId: 'telegram',
        config: { enabled: false },
      });
      expect(state.channels.telegram.enabled).toBe(false);
      expect(state.channels.telegram.config).toEqual({ botToken: 'abc' });
    });
  });

  describe('storage', () => {
    it('SET_STORAGE merges partial config', () => {
      const state = dispatch(initialState, {
        type: 'SET_STORAGE',
        config: { engine: 'postgresql' },
      });
      expect(state.storage.engine).toBe('postgresql');
    });

    it('SET_STORAGE_INSTANCE merges instance DB config', () => {
      const state = dispatch(initialState, {
        type: 'SET_STORAGE_INSTANCE',
        config: { engine: 'postgresql' },
      });
      expect(state.storage.instanceDb.engine).toBe('postgresql');
    });

    it('SET_STORAGE_SHARED merges shared DB config', () => {
      const state = dispatch(initialState, {
        type: 'SET_STORAGE_SHARED',
        config: { enabled: true },
      });
      expect(state.storage.sharedDb.enabled).toBe(true);
    });
  });

  describe('port config', () => {
    it('SET_PORT_CONFIG merges partial port config', () => {
      const state = dispatch(initialState, {
        type: 'SET_PORT_CONFIG',
        config: { mode: 'manual', agentPort: 4000 },
      });
      expect(state.portConfig.mode).toBe('manual');
      expect(state.portConfig.agentPort).toBe(4000);
    });
  });

  describe('unknown action', () => {
    it('returns state unchanged for unknown action type', () => {
      const state = wizardReducer(initialState, { type: 'UNKNOWN' } as unknown as WizardAction);
      expect(state).toBe(initialState);
    });
  });

  describe('TOTAL_STEPS', () => {
    it('should be 12', () => {
      expect(TOTAL_STEPS).toBe(12);
    });
  });
});
