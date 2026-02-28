export interface Platform {
  id: string;
  name: string;
  language: string;
  memory: string;
  port: number;
  description: string;
  icon: string;
  features: string[];
}

export interface HardwareProfile {
  os: { name: string; version: string; arch: string };
  cpu: { brand: string; cores: number; features: string[] };
  ram_gb: number;
  gpus: Array<{ vendor: string; name: string; vram_gb: number; api: string }>;
  gpu_summary: { has_gpu: boolean; primary_vendor: string; max_vram_gb: number };
}

export interface RuntimeRecommendation {
  primary: { id: string; name: string; port: number };
  fallback: { id: string; name: string; port: number };
  reason: string;
}

export interface ModelInfo {
  name: string;
  parameters: string;
  size_gb: number;
  vram_gb: number;
}

export interface WizardState {
  currentStep: number;
  platform: string;
  deploymentMethod: 'docker' | 'vagrant';
  llmProvider: 'cloud' | 'local';
  runtime: string;
  selectedModels: string[];
  securityEnabled: boolean;
  securityFeatures: string[];
  companyName: string;
  industry: string;
  useCase: string[];
  budget: number;
  sensitivity: string;
}

export interface DeployEvent {
  step: string;
  progress: number;
  status?: 'running' | 'complete' | 'error';
  message?: string;
}

export const STEP_LABELS = [
  'Welcome',
  'Platform',
  'Deployment',
  'LLM',
  'Hardware',
  'Models',
  'Security',
  'Review',
  'Deploy',
] as const;

export const PLATFORMS: Platform[] = [
  {
    id: 'zeroclaw',
    name: 'ZeroClaw',
    language: 'Python',
    memory: '512MB',
    port: 5000,
    description: 'Lightweight zero-config agent for quick deployments. Minimal resource footprint with essential agent capabilities.',
    icon: 'zap',
    features: ['Zero configuration', 'Fast startup', 'REST API', 'Lightweight'],
  },
  {
    id: 'nanoclaw',
    name: 'NanoClaw',
    language: 'Python',
    memory: '1GB',
    port: 5100,
    description: 'Small but capable agent with extended tooling. Balanced between resource usage and functionality.',
    icon: 'cpu',
    features: ['Tool integration', 'Memory system', 'Plugin support', 'Async tasks'],
  },
  {
    id: 'picoclaw',
    name: 'PicoClaw',
    language: 'Python',
    memory: '256MB',
    port: 5200,
    description: 'Ultra-minimal agent for edge deployments and IoT scenarios. Smallest possible footprint.',
    icon: 'minimize-2',
    features: ['Edge-ready', 'Ultra-light', 'MQTT support', 'Embedded mode'],
  },
  {
    id: 'openclaw',
    name: 'OpenClaw',
    language: 'Python',
    memory: '2GB',
    port: 5300,
    description: 'Full-featured open agent platform with advanced reasoning, multi-model support, and enterprise integrations.',
    icon: 'globe',
    features: ['Multi-model', 'RAG pipeline', 'Enterprise APIs', 'Advanced reasoning'],
  },
  {
    id: 'parlant',
    name: 'Parlant',
    language: 'Python',
    memory: '2GB',
    port: 5400,
    description: 'Conversational agent platform with dialogue management, persona system, and multi-turn reasoning.',
    icon: 'message-circle',
    features: ['Dialogue engine', 'Persona system', 'Context tracking', 'Multi-turn'],
  },
];

export const MODELS: ModelInfo[] = [
  { name: 'Llama 3.1 8B', parameters: '8B', size_gb: 4.7, vram_gb: 6 },
  { name: 'Llama 3.1 70B', parameters: '70B', size_gb: 40, vram_gb: 48 },
  { name: 'Mistral 7B', parameters: '7B', size_gb: 4.1, vram_gb: 6 },
  { name: 'Mixtral 8x7B', parameters: '46.7B', size_gb: 26, vram_gb: 32 },
  { name: 'Phi-3 Mini', parameters: '3.8B', size_gb: 2.3, vram_gb: 4 },
  { name: 'Qwen2 7B', parameters: '7B', size_gb: 4.4, vram_gb: 6 },
  { name: 'CodeLlama 13B', parameters: '13B', size_gb: 7.4, vram_gb: 10 },
  { name: 'DeepSeek Coder V2', parameters: '16B', size_gb: 8.9, vram_gb: 12 },
];

export const SECURITY_OPTIONS = [
  { id: 'url-filtering', label: 'URL Filtering', description: 'Block malicious or unauthorized URLs' },
  { id: 'content-rules', label: 'Content Rules', description: 'Enforce content policies and restrictions' },
  { id: 'pii-detection', label: 'PII Detection', description: 'Detect and redact personally identifiable information' },
  { id: 'network-rules', label: 'Network Rules', description: 'Control network access and egress policies' },
  { id: 'gdpr', label: 'GDPR Compliance', description: 'European data protection regulation compliance' },
  { id: 'hipaa', label: 'HIPAA Compliance', description: 'Healthcare data protection compliance' },
  { id: 'pci-dss', label: 'PCI-DSS Compliance', description: 'Payment card industry security standards' },
];
