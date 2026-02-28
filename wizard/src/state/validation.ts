import type { WizardState } from './types';

export function canProceed(state: WizardState): boolean {
  switch (state.currentStep) {
    case 0: return state.agentName.trim().length > 0;
    case 1: return true;
    case 2: return state.platform !== '';
    case 3: {
      if (state.deploymentMethod === 'ssh') {
        return state.sshCredentials.host !== '' && state.sshCredentials.username !== '';
      }
      return state.deploymentMethod !== '';
    }
    case 4: {
      if (state.llmProvider === 'hybrid') {
        return state.cloudProviders.length > 0 && state.runtime !== '';
      }
      if (state.llmProvider === 'local') return state.runtime !== '';
      return true;
    }
    case 5: {
      if (state.llmProvider === 'cloud') return true;
      return state.selectedModels.length > 0;
    }
    case 6: return true; // Security — optional
    case 7: {
      // Storage — SQLite always valid; PostgreSQL requires host + dbname + user
      const inst = state.storage.instanceDb;
      if (inst.engine === 'postgresql') {
        if (!inst.postgresql.host || !inst.postgresql.dbname || !inst.postgresql.user) return false;
      }
      if (state.storage.sharedDb.enabled && state.storage.sharedDb.engine === 'postgresql') {
        const sh = state.storage.sharedDb.postgresql;
        if (!sh.host || !sh.dbname || !sh.user) return false;
      }
      return true;
    }
    case 8: return state.gateway.port >= 1024 && state.gateway.port <= 65535;
    case 9: return true; // Channels — optional (can skip)
    case 10: return true; // Review
    case 11: return false; // Deploy (no next)
    default: return false;
  }
}

export function getAssessmentJSON(state: WizardState): Record<string, unknown> {
  const maskedKeys: Record<string, string> = {};
  for (const [k, v] of Object.entries(state.apiKeys)) {
    maskedKeys[k] = v ? `${v.slice(0, 4)}${'•'.repeat(Math.max(0, v.length - 4))}` : '';
  }

  const enabledChannels: Record<string, Record<string, string>> = {};
  for (const [id, ch] of Object.entries(state.channels)) {
    if (ch.enabled) {
      enabledChannels[id] = ch.config;
    }
  }

  // Build storage config for assessment
  const storageAssessment: Record<string, unknown> = {
    engine: state.storage.engine,
    instance_db: {
      engine: state.storage.instanceDb.engine,
      ...(state.storage.instanceDb.engine === 'sqlite'
        ? { path: state.storage.instanceDb.sqlite.path }
        : {
            host: state.storage.instanceDb.postgresql.host,
            port: state.storage.instanceDb.postgresql.port,
            dbname: state.storage.instanceDb.postgresql.dbname,
            user: state.storage.instanceDb.postgresql.user,
          }),
    },
    shared_db: {
      enabled: state.storage.sharedDb.enabled,
      ...(state.storage.sharedDb.enabled
        ? {
            engine: state.storage.sharedDb.engine,
            ...(state.storage.sharedDb.engine === 'sqlite'
              ? { path: state.storage.sharedDb.sqlite.path }
              : {
                  host: state.storage.sharedDb.postgresql.host,
                  port: state.storage.sharedDb.postgresql.port,
                  dbname: state.storage.sharedDb.postgresql.dbname,
                  user: state.storage.sharedDb.postgresql.user,
                }),
          }
        : {}),
    },
  };

  return {
    agent_name: state.agentName,
    platform: state.platform || undefined,
    deployment_method: state.deploymentMethod,
    llm_provider: state.llmProvider,
    runtime: state.runtime || undefined,
    selected_models: state.selectedModels.length > 0 ? state.selectedModels : undefined,
    security: {
      enabled: state.securityEnabled,
      features: state.securityFeatures,
      config: state.securityEnabled ? state.securityConfig : undefined,
      compliance: state.securityEnabled ? state.complianceConfig : undefined,
    },
    cloud_providers: state.cloudProviders.length > 0 ? state.cloudProviders : undefined,
    api_keys: Object.keys(maskedKeys).length > 0 ? maskedKeys : undefined,
    gateway: {
      ...state.gateway,
      routes: state.gateway.routes.length > 0 ? state.gateway.routes : undefined,
    },
    storage: storageAssessment,
    port_config: state.portConfig,
    channels: Object.keys(enabledChannels).length > 0 ? enabledChannels : undefined,
    ssh_credentials:
      state.deploymentMethod === 'ssh'
        ? {
            host: state.sshCredentials.host,
            port: state.sshCredentials.port,
            username: state.sshCredentials.username,
            auth_method: state.sshCredentials.authMethod,
          }
        : undefined,
  };
}
