const API_BASE = '/api/wizard';
const DASHBOARD_API = '/api/dashboard';

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json() as Promise<T>;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export const api = {
  // ── Wizard Endpoints ────────────────────────────────────
  getHardware: () => fetchJson<any>(`${API_BASE}/hardware`),

  getPlatforms: () => fetchJson<any>(`${API_BASE}/platforms`),

  getModels: () => fetchJson<any>(`${API_BASE}/models`),

  getRuntimes: () => fetchJson<any>(`${API_BASE}/runtimes`),

  getStatus: () => fetchJson<any>(`${API_BASE}/status`),

  validate: (config: Record<string, unknown>) =>
    fetchJson<{ valid: boolean; errors?: string[] }>(`${API_BASE}/validate`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  deploy: (config: Record<string, unknown>) =>
    fetchJson<{ success: boolean; message: string }>(`${API_BASE}/deploy`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  getDeployStream: () => new EventSource(`${API_BASE}/deploy/stream`),

  // ── Security Rules Detail ───────────────────────────────
  getSecurityRulesDetail: () =>
    fetchJson<any>(`${API_BASE}/security-rules/detail`),

  saveSecurityRules: (config: Record<string, unknown>) =>
    fetchJson<any>(`${API_BASE}/security-rules`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  // ── Compliance ──────────────────────────────────────────
  saveCompliance: (config: Record<string, unknown>) =>
    fetchJson<any>(`${API_BASE}/compliance`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  // ── Channel Test ────────────────────────────────────────
  testChannel: (channelId: string, config: Record<string, string>) =>
    fetchJson<{ success: boolean; message?: string }>(`${API_BASE}/channels/test`, {
      method: 'POST',
      body: JSON.stringify({ channel: channelId, config }),
    }),

  // ── Storage ───────────────────────────────────────────
  getStorageConfig: () => fetchJson<any>(`${API_BASE}/storage`),

  saveStorageConfig: (config: Record<string, unknown>) =>
    fetchJson<any>(`${API_BASE}/storage`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  testStorageConnection: (config: Record<string, unknown>) =>
    fetchJson<{ success: boolean; message: string; latency_ms?: number }>(`${API_BASE}/storage/test`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  checkPostgresReadiness: (config: {
    host?: string; port?: number; dbname?: string; user?: string; password?: string;
  }) => {
    const params = new URLSearchParams();
    if (config.host) params.set('host', config.host);
    if (config.port) params.set('port', String(config.port));
    if (config.dbname) params.set('dbname', config.dbname);
    if (config.user) params.set('user', config.user);
    if (config.password) params.set('password', config.password);
    return fetchJson<{
      driver_installed: boolean;
      server_reachable: boolean;
      connection_ok: boolean;
      connection_message: string;
      docker_available: boolean;
      ready: boolean;
    }>(`${API_BASE}/storage/check-postgres?${params.toString()}`);
  },

  setupPostgres: (mode: 'docker' | 'local', config: Record<string, unknown>) =>
    fetchJson<{ success: boolean; message: string; host?: string; port?: number }>(`${API_BASE}/storage/setup-postgres`, {
      method: 'POST',
      body: JSON.stringify({ mode, config }),
    }),

  createPostgresDatabase: (config: Record<string, unknown>) =>
    fetchJson<{ success: boolean; message: string }>(`${API_BASE}/storage/create-database`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  // ── Dashboard Endpoints ─────────────────────────────────
  dashboard: {
    getStatus: () => fetchJson<any>(`${DASHBOARD_API}/status`),

    getAgents: () => fetchJson<any>(`${DASHBOARD_API}/agents`),

    agentAction: (agentId: string, action: 'start' | 'stop' | 'restart') =>
      fetchJson<any>(`${DASHBOARD_API}/agents/${agentId}/${action}`, { method: 'POST' }),

    getStrategy: () => fetchJson<any>(`${DASHBOARD_API}/strategy`),

    getSecurity: () => fetchJson<any>(`${DASHBOARD_API}/security`),

    getConfig: () => fetchJson<any>(`${DASHBOARD_API}/config`),

    getHardware: () => fetchJson<any>(`${DASHBOARD_API}/hardware`),

    getCosts: () => fetchJson<any>(`${DASHBOARD_API}/costs`),

    // ── Metrics ──────────────────────────────────────────
    getMetrics: () => fetchJson<any>(`${DASHBOARD_API}/metrics`),

    // ── Logs ─────────────────────────────────────────────
    getLogs: () => fetchJson<any>(`${DASHBOARD_API}/logs`),

    // ── Triggers ─────────────────────────────────────────
    getTriggers: () => fetchJson<any>(`${DASHBOARD_API}/triggers`),

    saveTriggers: (data: Record<string, unknown>) =>
      fetchJson<any>(`${DASHBOARD_API}/triggers`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    testTrigger: (trigger: Record<string, unknown>) =>
      fetchJson<any>(`${DASHBOARD_API}/triggers/test`, {
        method: 'POST',
        body: JSON.stringify(trigger),
      }),

    // ── Instances / Cluster ──────────────────────────────
    getInstances: () => fetchJson<any>(`${DASHBOARD_API}/instances`),

    saveInstance: (data: Record<string, unknown>) =>
      fetchJson<any>(`${DASHBOARD_API}/instances`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    deleteInstance: (id: string) =>
      fetchJson<any>(`${DASHBOARD_API}/instances/${id}/delete`, { method: 'POST' }),

    getInstanceStatus: (id: string) =>
      fetchJson<any>(`${DASHBOARD_API}/instances/${id}/status`),

    // ── Channels ─────────────────────────────────────────
    getChannelsStatus: () =>
      fetchJson<any>(`${DASHBOARD_API}/channels/status`, { method: 'POST', body: '{}' }),

    saveChannelsConfig: (data: Record<string, unknown>) =>
      fetchJson<any>(`${DASHBOARD_API}/channels/config`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    // ── Security Toggle ──────────────────────────────────
    toggleSecurityRule: (ruleId: string, enabled: boolean) =>
      fetchJson<any>(`${DASHBOARD_API}/security/toggle`, {
        method: 'POST',
        body: JSON.stringify({ rule_id: ruleId, enabled }),
      }),

    // ── Data Management ──────────────────────────────────
    getDataOverview: () => fetchJson<any>(`${DASHBOARD_API}/data`),

    getDataTables: (db: string = 'instance') =>
      fetchJson<any>(`${DASHBOARD_API}/data/tables?db=${db}`),

    queryData: (params: Record<string, unknown>) =>
      fetchJson<any>(`${DASHBOARD_API}/data/query`, {
        method: 'POST',
        body: JSON.stringify(params),
      }),

    getDataHealth: () => fetchJson<any>(`${DASHBOARD_API}/data/health`),

    getRbac: () => fetchJson<any>(`${DASHBOARD_API}/data/rbac`),

    saveRbac: (data: Record<string, unknown>) =>
      fetchJson<any>(`${DASHBOARD_API}/data/rbac`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    exportDatabase: async (db: string = 'instance'): Promise<Blob> => {
      const res = await fetch(`${DASHBOARD_API}/data/export?db=${db}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      return res.blob();
    },

    // ── Claws (create/manage) ────────────────────────────
    getClaws: () => fetchJson<any>(`${DASHBOARD_API}/claws`),

    createClaw: (config: Record<string, unknown>) =>
      fetchJson<any>(`${DASHBOARD_API}/claws`, {
        method: 'POST',
        body: JSON.stringify(config),
      }),

    deleteClaw: (id: string) =>
      fetchJson<any>(`${DASHBOARD_API}/claws/${id}/delete`, { method: 'POST' }),
  },
};
/* eslint-enable @typescript-eslint/no-explicit-any */
