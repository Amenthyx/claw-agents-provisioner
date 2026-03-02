/**
 * Tests for wizard validation logic — canProceed and getAssessmentJSON.
 */
import { describe, it, expect } from 'vitest';
import { canProceed, getAssessmentJSON } from './validation';
import { initialState } from './reducer';
import type { WizardState } from './types';

function stateAt(step: number, overrides: Partial<WizardState> = {}): WizardState {
  return { ...initialState, currentStep: step, ...overrides };
}

describe('canProceed', () => {
  describe('Step 0 — Welcome', () => {
    it('returns false when agent name is empty', () => {
      expect(canProceed(stateAt(0))).toBe(false);
    });

    it('returns false when agent name is only whitespace', () => {
      expect(canProceed(stateAt(0, { agentName: '   ' }))).toBe(false);
    });

    it('returns true when agent name is set', () => {
      expect(canProceed(stateAt(0, { agentName: 'my-agent' }))).toBe(true);
    });
  });

  describe('Step 1 — Hardware', () => {
    it('always returns true (hardware detection is automatic)', () => {
      expect(canProceed(stateAt(1))).toBe(true);
    });
  });

  describe('Step 2 — Platform', () => {
    it('returns false when no platform selected', () => {
      expect(canProceed(stateAt(2))).toBe(false);
    });

    it('returns true when platform is selected', () => {
      expect(canProceed(stateAt(2, { platform: 'zeroclaw' }))).toBe(true);
    });
  });

  describe('Step 3 — Deployment', () => {
    it('returns true for docker method', () => {
      expect(canProceed(stateAt(3, { deploymentMethod: 'docker' }))).toBe(true);
    });

    it('returns true for local method', () => {
      expect(canProceed(stateAt(3, { deploymentMethod: 'local' }))).toBe(true);
    });

    it('returns false for SSH when host is empty', () => {
      expect(canProceed(stateAt(3, {
        deploymentMethod: 'ssh',
        sshCredentials: { ...initialState.sshCredentials, host: '', username: 'deploy' },
      }))).toBe(false);
    });

    it('returns false for SSH when username is empty', () => {
      expect(canProceed(stateAt(3, {
        deploymentMethod: 'ssh',
        sshCredentials: { ...initialState.sshCredentials, host: '10.0.0.1', username: '' },
      }))).toBe(false);
    });

    it('returns true for SSH when host and username are set', () => {
      expect(canProceed(stateAt(3, {
        deploymentMethod: 'ssh',
        sshCredentials: { ...initialState.sshCredentials, host: '10.0.0.1', username: 'deploy' },
      }))).toBe(true);
    });

    it('returns false when deployment method is empty', () => {
      expect(canProceed(stateAt(3, { deploymentMethod: '' }))).toBe(false);
    });
  });

  describe('Step 4 — LLM Provider', () => {
    it('returns true for cloud provider (no runtime needed)', () => {
      expect(canProceed(stateAt(4, { llmProvider: 'cloud' }))).toBe(true);
    });

    it('returns false for local when no runtime selected', () => {
      expect(canProceed(stateAt(4, { llmProvider: 'local', runtime: '' }))).toBe(false);
    });

    it('returns true for local when runtime selected', () => {
      expect(canProceed(stateAt(4, { llmProvider: 'local', runtime: 'ollama' }))).toBe(true);
    });

    it('returns false for hybrid when no cloud providers or runtime', () => {
      expect(canProceed(stateAt(4, {
        llmProvider: 'hybrid',
        cloudProviders: [],
        runtime: '',
      }))).toBe(false);
    });

    it('returns false for hybrid when cloud providers set but no runtime', () => {
      expect(canProceed(stateAt(4, {
        llmProvider: 'hybrid',
        cloudProviders: ['openai'],
        runtime: '',
      }))).toBe(false);
    });

    it('returns true for hybrid when both cloud providers and runtime set', () => {
      expect(canProceed(stateAt(4, {
        llmProvider: 'hybrid',
        cloudProviders: ['openai'],
        runtime: 'ollama',
      }))).toBe(true);
    });
  });

  describe('Step 5 — Models', () => {
    it('returns true for cloud provider (no models needed)', () => {
      expect(canProceed(stateAt(5, { llmProvider: 'cloud' }))).toBe(true);
    });

    it('returns false for local when no models selected', () => {
      expect(canProceed(stateAt(5, { llmProvider: 'local', selectedModels: [] }))).toBe(false);
    });

    it('returns true for local when models selected', () => {
      expect(canProceed(stateAt(5, { llmProvider: 'local', selectedModels: ['mistral:7b'] }))).toBe(true);
    });
  });

  describe('Step 6 — Strategy/Gateway', () => {
    it('returns true when gateway port is valid', () => {
      expect(canProceed(stateAt(6, {
        gateway: { ...initialState.gateway, port: 9095 },
      }))).toBe(true);
    });

    it('returns false when gateway port is below 1024', () => {
      expect(canProceed(stateAt(6, {
        gateway: { ...initialState.gateway, port: 80 },
      }))).toBe(false);
    });

    it('returns false when gateway port is above 65535', () => {
      expect(canProceed(stateAt(6, {
        gateway: { ...initialState.gateway, port: 70000 },
      }))).toBe(false);
    });
  });

  describe('Step 7 — Security', () => {
    it('always returns true (security is optional)', () => {
      expect(canProceed(stateAt(7))).toBe(true);
    });
  });

  describe('Step 8 — Storage', () => {
    it('returns true with default SQLite config', () => {
      expect(canProceed(stateAt(8))).toBe(true);
    });

    it('returns false for PostgreSQL instance DB when host is missing', () => {
      expect(canProceed(stateAt(8, {
        storage: {
          ...initialState.storage,
          instanceDb: {
            ...initialState.storage.instanceDb,
            engine: 'postgresql',
            postgresql: { host: '', port: 5432, dbname: 'xclaw', user: 'xclaw', password: '' },
          },
        },
      }))).toBe(false);
    });

    it('returns true for PostgreSQL when all required fields set', () => {
      expect(canProceed(stateAt(8, {
        storage: {
          ...initialState.storage,
          instanceDb: {
            ...initialState.storage.instanceDb,
            engine: 'postgresql',
            postgresql: { host: 'localhost', port: 5432, dbname: 'xclaw', user: 'xclaw', password: '' },
          },
        },
      }))).toBe(true);
    });

    it('returns false when shared DB is PostgreSQL with missing fields', () => {
      expect(canProceed(stateAt(8, {
        storage: {
          ...initialState.storage,
          sharedDb: {
            ...initialState.storage.sharedDb,
            enabled: true,
            engine: 'postgresql',
            postgresql: { host: '', port: 5432, dbname: '', user: '', password: '' },
          },
        },
      }))).toBe(false);
    });
  });

  describe('Step 9 — Channels', () => {
    it('always returns true (channels are optional)', () => {
      expect(canProceed(stateAt(9))).toBe(true);
    });
  });

  describe('Step 10 — Review', () => {
    it('always returns true', () => {
      expect(canProceed(stateAt(10))).toBe(true);
    });
  });

  describe('Step 11 — Deploy', () => {
    it('returns false (no next step)', () => {
      expect(canProceed(stateAt(11))).toBe(false);
    });
  });

  describe('out of range step', () => {
    it('returns false for invalid step number', () => {
      expect(canProceed(stateAt(99))).toBe(false);
    });
  });
});

describe('getAssessmentJSON', () => {
  it('returns basic fields from state', () => {
    const state = stateAt(0, {
      agentName: 'test-agent',
      platform: 'zeroclaw',
      deploymentMethod: 'docker',
      llmProvider: 'cloud',
    });
    const json = getAssessmentJSON(state);
    expect(json.agent_name).toBe('test-agent');
    expect(json.platform).toBe('zeroclaw');
    expect(json.deployment_method).toBe('docker');
    expect(json.llm_provider).toBe('cloud');
  });

  it('masks API keys in output', () => {
    const state = stateAt(0, {
      apiKeys: { openai: 'sk-test-1234567890' },
    });
    const json = getAssessmentJSON(state);
    const maskedKeys = json.api_keys as Record<string, string>;
    expect(maskedKeys.openai).toMatch(/^sk-t/);
    expect(maskedKeys.openai).toContain('\u2022'); // bullet char for masking
  });

  it('includes SSH credentials when deployment is SSH', () => {
    const state = stateAt(0, {
      deploymentMethod: 'ssh',
      sshCredentials: {
        ...initialState.sshCredentials,
        host: '10.0.0.1',
        username: 'deploy',
      },
    });
    const json = getAssessmentJSON(state);
    const ssh = json.ssh_credentials as Record<string, unknown>;
    expect(ssh).toBeDefined();
    expect(ssh.host).toBe('10.0.0.1');
    expect(ssh.username).toBe('deploy');
  });

  it('excludes SSH credentials when deployment is not SSH', () => {
    const state = stateAt(0, { deploymentMethod: 'docker' });
    const json = getAssessmentJSON(state);
    expect(json.ssh_credentials).toBeUndefined();
  });

  it('includes security config when enabled', () => {
    const state = stateAt(0, {
      securityEnabled: true,
      securityFeatures: ['pii-detection'],
    });
    const json = getAssessmentJSON(state);
    const security = json.security as Record<string, unknown>;
    expect(security.enabled).toBe(true);
    expect(security.features).toEqual(['pii-detection']);
    expect(security.config).toBeDefined();
  });

  it('excludes security config details when disabled', () => {
    const state = stateAt(0, { securityEnabled: false });
    const json = getAssessmentJSON(state);
    const security = json.security as Record<string, unknown>;
    expect(security.enabled).toBe(false);
    expect(security.config).toBeUndefined();
  });

  it('includes enabled channels', () => {
    const state = stateAt(0, {
      channels: {
        telegram: { enabled: true, config: { botToken: 'abc' } },
        discord: { enabled: false, config: {} },
      },
    });
    const json = getAssessmentJSON(state);
    const channels = json.channels as Record<string, Record<string, string>>;
    expect(channels).toBeDefined();
    expect(channels.telegram).toBeDefined();
    expect(channels.discord).toBeUndefined();
  });

  it('excludes channels when none enabled', () => {
    const state = stateAt(0, { channels: {} });
    const json = getAssessmentJSON(state);
    expect(json.channels).toBeUndefined();
  });

  it('includes storage configuration', () => {
    const json = getAssessmentJSON(initialState);
    const storage = json.storage as Record<string, unknown>;
    expect(storage).toBeDefined();
    expect(storage.engine).toBe('sqlite');
  });

  it('includes gateway configuration', () => {
    const json = getAssessmentJSON(initialState);
    const gateway = json.gateway as Record<string, unknown>;
    expect(gateway).toBeDefined();
    expect(gateway.port).toBe(9095);
  });
});
