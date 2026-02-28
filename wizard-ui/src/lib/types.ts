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

export interface GatewayConfig {
  port: number;
  rateLimit: number;
  failover: 'local-first' | 'cloud-first' | 'round-robin';
  routing: 'auto' | 'manual';
}

export interface WizardState {
  currentStep: number;
  platform: string;
  deploymentMethod: 'docker' | 'vagrant' | 'local';
  llmProvider: 'cloud' | 'local' | 'hybrid';
  runtime: string;
  selectedModels: string[];
  securityEnabled: boolean;
  securityFeatures: string[];
  companyName: string;
  industry: string;
  useCase: string[];
  budget: number;
  sensitivity: string;
  apiKeys: Record<string, string>;
  cloudProviders: string[];
  gateway: GatewayConfig;
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
  'Gateway',
  'Review',
  'Deploy',
] as const;

export const PLATFORMS: Platform[] = [
  {
    id: 'zeroclaw',
    name: 'ZeroClaw',
    language: 'Rust',
    memory: '512MB',
    port: 3100,
    description: 'Lightweight zero-config agent for quick deployments. Minimal resource footprint with essential agent capabilities.',
    icon: 'zap',
    features: ['Zero configuration', 'Fast startup', 'REST API', 'Lightweight'],
  },
  {
    id: 'nanoclaw',
    name: 'NanoClaw',
    language: 'TypeScript',
    memory: '1GB',
    port: 3200,
    description: 'Small but capable agent with extended tooling. Balanced between resource usage and functionality.',
    icon: 'cpu',
    features: ['Tool integration', 'Memory system', 'Plugin support', 'Async tasks'],
  },
  {
    id: 'picoclaw',
    name: 'PicoClaw',
    language: 'Go',
    memory: '128MB',
    port: 3300,
    description: 'Ultra-minimal agent for edge deployments and IoT scenarios. Smallest possible footprint.',
    icon: 'minimize-2',
    features: ['Edge-ready', 'Ultra-light', 'MQTT support', 'Embedded mode'],
  },
  {
    id: 'openclaw',
    name: 'OpenClaw',
    language: 'Node.js',
    memory: '4GB',
    port: 3400,
    description: 'Full-featured open agent platform with advanced reasoning, multi-model support, and enterprise integrations.',
    icon: 'globe',
    features: ['Multi-model', 'RAG pipeline', 'Enterprise APIs', 'Advanced reasoning'],
  },
  {
    id: 'parlant',
    name: 'Parlant',
    language: 'Python',
    memory: '2GB',
    port: 8800,
    description: 'Conversational agent platform with dialogue management, persona system, and multi-turn reasoning.',
    icon: 'message-circle',
    features: ['Dialogue engine', 'Persona system', 'Context tracking', 'Multi-turn'],
  },
];

export const SERVICE_PORTS = {
  router: 9095,
  wizard: 9098,
  dashboard: 9099,
  orchestrator: 9100,
} as const;

export const FAILOVER_STRATEGIES = [
  { id: 'local-first' as const, name: 'Local First', description: 'Try local runtimes before falling back to cloud APIs' },
  { id: 'cloud-first' as const, name: 'Cloud First', description: 'Prefer cloud APIs, fall back to local on failure' },
  { id: 'round-robin' as const, name: 'Round Robin', description: 'Distribute requests evenly across all backends' },
];

export const ROUTING_MODES = [
  { id: 'auto' as const, name: 'Auto-Detect', description: 'Automatically route based on task keywords (coding, reasoning, creative, etc.)' },
  { id: 'manual' as const, name: 'Manual', description: 'Always route to a specific backend — no automatic task detection' },
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

export const CLOUD_PROVIDERS = [
  { id: 'anthropic', name: 'Anthropic', model: 'Claude', color: '#d4a574' },
  { id: 'openai', name: 'OpenAI', model: 'GPT-4', color: '#74aa9c' },
  { id: 'deepseek', name: 'DeepSeek', model: 'DeepSeek V3', color: '#4a9eff' },
  { id: 'google', name: 'Google', model: 'Gemini', color: '#4285f4' },
  { id: 'groq', name: 'Groq', model: 'LPU Inference', color: '#f55036' },
];

export const LOCAL_RUNTIMES = [
  { id: 'ollama', name: 'Ollama', description: 'Easy-to-use local model runner', port: 11434 },
  { id: 'llama-cpp', name: 'llama.cpp', description: 'High-performance CPU/GPU inference', port: 8080 },
  { id: 'vllm', name: 'vLLM', description: 'Production-grade GPU inference server', port: 8000 },
  { id: 'localai', name: 'LocalAI', description: 'OpenAI-compatible local API', port: 8080 },
];
