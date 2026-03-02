/* ── Hardware ──────────────────────────────────────────────── */

/* eslint-disable @typescript-eslint/no-explicit-any */
export interface HardwareProfile {
  os: any;
  arch: any;
  cpu: {
    brand: any;
    cores: number;
    features: any[];
  };
  ram: number;
  gpus: Array<{
    name: any;
    vram: number;
    api: any;
  }>;
}

export interface RuntimeRecommendation {
  primary: any;
  fallback: any;
  reason: any;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/* ── Platform ─────────────────────────────────────────────── */

export interface Platform {
  id: string;
  name: string;
  language: string;
  memory: string;
  port: number;
  description: string;
  features: string[];
  minRam: number;
  minCores: number;
  gpuRequired: boolean;
  tier: 'lightweight' | 'standard' | 'heavy';
}

/* ── Models ───────────────────────────────────────────────── */

export interface ModelInfo {
  id: string;
  name: string;
  parameters: string;
  diskSize: string;
  vramRequired: number;
  category: 'general' | 'coding' | 'reasoning';
}

/* ── Security ─────────────────────────────────────────────── */

export interface SecurityOption {
  id: string;
  name: string;
  description: string;
  category: 'filtering' | 'compliance';
  icon: string;
}

/* ── Security Detail Config ──────────────────────────────── */

export interface UrlFilteringConfig {
  mode: 'blocklist' | 'allowlist';
  patterns: string[];
}

export interface ContentRulesConfig {
  blockedKeywords: string[];
  allowedKeywords: string[];
  forbiddenCategories: string[];
  responseInjectionProtection: boolean;
}

export type PiiAction = 'redact' | 'mask' | 'block' | 'log';

export interface PiiDetectionConfig {
  types: Record<string, boolean>;
  action: PiiAction;
  customPatterns: string[];
}

export interface NetworkRulesConfig {
  allowedPorts: number[];
  forbiddenIpRanges: string[];
  allowedApiHosts: string[];
  requireTls: boolean;
  tlsMinVersion: '1.2' | '1.3';
}

export interface SecurityDetailConfig {
  urlFiltering: UrlFilteringConfig;
  contentRules: ContentRulesConfig;
  piiDetection: PiiDetectionConfig;
  networkRules: NetworkRulesConfig;
}

/* ── Compliance ──────────────────────────────────────────── */

export interface ComplianceStandardConfig {
  enabled: boolean;
  acknowledgedRules: string[];
}

export type ComplianceConfig = Record<string, ComplianceStandardConfig>;

/* ── LLM Providers ────────────────────────────────────────── */

export interface CloudProvider {
  id: string;
  name: string;
  model: string;
  color: string;
}

export interface LocalRuntime {
  id: string;
  name: string;
  port: number;
  description: string;
}

/* ── Gateway ──────────────────────────────────────────────── */

export interface RoutingRule {
  pattern: string;
  target: string;
  priority: number;
  rateLimitOverride?: number;
}

export interface GatewayConfig {
  port: number;
  rateLimit: number;
  failover: string;
  routing: string;
  routes: RoutingRule[];
  customLocalEndpoint?: string;
}

/* ── SSH ──────────────────────────────────────────────────── */

export interface SshCredentials {
  host: string;
  port: number;
  username: string;
  authMethod: 'password' | 'key';
  password: string;
  privateKey: string;
}

/* ── Channels ────────────────────────────────────────────── */

export interface ChannelConfig {
  enabled: boolean;
  config: Record<string, string>;
}

/* ── Storage ─────────────────────────────────────────────── */

export type StorageEngine = 'sqlite' | 'postgresql';

export interface StorageConfig {
  engine: StorageEngine;
  instanceDb: {
    engine: StorageEngine;
    sqlite: { path: string };
    postgresql: { host: string; port: number; dbname: string; user: string; password: string };
  };
  sharedDb: {
    enabled: boolean;
    engine: StorageEngine;
    sqlite: { path: string };
    postgresql: { host: string; port: number; dbname: string; user: string; password: string };
  };
}

/* ── LLM Strategy ───────────────────────────────────────── */

export type OptimizationPreset = 'cost' | 'speed' | 'quality' | 'balanced';

export interface StrategyRule {
  taskCategory: string;
  primaryModel: string;
  fallbackModel: string;
}

export interface LlmStrategy {
  optimization: OptimizationPreset;
  rules: StrategyRule[];
}

/* ── Port Config ─────────────────────────────────────────── */

export interface PortConfig {
  mode: 'auto' | 'manual';
  agentPort?: number;
  gatewayPort?: number;
  optimizerPort?: number;
  watchdogPort?: number;
}

/* ── Wizard State ─────────────────────────────────────────── */

export interface WizardState {
  currentStep: number;
  agentName: string;
  hardware: HardwareProfile | null;
  hardwareRecommendation: RuntimeRecommendation | null;
  platform: string;
  deploymentMethod: string;
  llmProvider: string;
  runtime: string;
  selectedModels: string[];
  strategy: LlmStrategy;
  securityEnabled: boolean;
  securityFeatures: string[];
  securityConfig: SecurityDetailConfig;
  complianceConfig: ComplianceConfig;
  cloudProviders: string[];
  apiKeys: Record<string, string>;
  gateway: GatewayConfig;
  sshCredentials: SshCredentials;
  channels: Record<string, ChannelConfig>;
  storage: StorageConfig;
  portConfig: PortConfig;
}

/* ── Actions ──────────────────────────────────────────────── */

export type WizardAction =
  | { type: 'NEXT_STEP' }
  | { type: 'PREV_STEP' }
  | { type: 'GO_TO_STEP'; step: number }
  | { type: 'SET_AGENT_NAME'; name: string }
  | { type: 'SET_HARDWARE'; hardware: HardwareProfile; recommendation: RuntimeRecommendation }
  | { type: 'SET_PLATFORM'; platform: string }
  | { type: 'SET_DEPLOYMENT_METHOD'; method: string }
  | { type: 'SET_LLM_PROVIDER'; provider: string }
  | { type: 'SET_RUNTIME'; runtime: string }
  | { type: 'TOGGLE_MODEL'; modelId: string }
  | { type: 'SET_STRATEGY_OPTIMIZATION'; optimization: OptimizationPreset }
  | { type: 'SET_STRATEGY_RULE'; taskCategory: string; primaryModel: string; fallbackModel: string }
  | { type: 'SET_STRATEGY_RULES'; rules: StrategyRule[] }
  | { type: 'SET_SECURITY_ENABLED'; enabled: boolean }
  | { type: 'TOGGLE_SECURITY_FEATURE'; featureId: string }
  | { type: 'SET_SECURITY_CONFIG'; config: Partial<SecurityDetailConfig> }
  | { type: 'SET_COMPLIANCE_CONFIG'; standard: string; config: Partial<ComplianceStandardConfig> }
  | { type: 'SET_CLOUD_PROVIDERS'; providers: string[] }
  | { type: 'SET_API_KEY'; provider: string; key: string }
  | { type: 'SET_GATEWAY'; config: Partial<GatewayConfig> }
  | { type: 'SET_GATEWAY_ROUTES'; routes: RoutingRule[] }
  | { type: 'SET_SSH_CREDENTIALS'; creds: Partial<SshCredentials> }
  | { type: 'SET_CHANNEL'; channelId: string; config: Partial<ChannelConfig> }
  | { type: 'SET_STORAGE'; config: Partial<StorageConfig> }
  | { type: 'SET_STORAGE_INSTANCE'; config: Partial<StorageConfig['instanceDb']> }
  | { type: 'SET_STORAGE_SHARED'; config: Partial<StorageConfig['sharedDb']> }
  | { type: 'SET_PORT_CONFIG'; config: Partial<PortConfig> };

/* ── Step Definition ──────────────────────────────────────── */

export interface StepDef {
  id: string;
  label: string;
  icon: string;
  description: string;
}
