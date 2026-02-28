import type { StepDef } from '../state/types';

export const STEPS: StepDef[] = [
  { id: 'welcome', label: 'Welcome', icon: 'Sparkles', description: 'Get started with XClaw setup' },
  { id: 'hardware', label: 'Hardware', icon: 'Cpu', description: 'Detect your system capabilities' },
  { id: 'platform', label: 'Platform', icon: 'Layers', description: 'Choose your agent platform' },
  { id: 'deployment', label: 'Deployment', icon: 'Container', description: 'Select deployment method' },
  { id: 'llm', label: 'LLM Provider', icon: 'Brain', description: 'Configure your LLM backend' },
  { id: 'models', label: 'Models', icon: 'Boxes', description: 'Select local models to deploy' },
  { id: 'security', label: 'Security', icon: 'Shield', description: 'Configure security & compliance' },
  { id: 'storage', label: 'Storage', icon: 'Database', description: 'Configure database & shared storage' },
  { id: 'gateway', label: 'Gateway', icon: 'Network', description: 'Set up the API gateway router' },
  { id: 'channels', label: 'Channels', icon: 'MessageSquare', description: 'Configure communication channels' },
  { id: 'review', label: 'Review', icon: 'ClipboardCheck', description: 'Review your configuration' },
  { id: 'deploy', label: 'Deploy', icon: 'Rocket', description: 'Deploy your infrastructure' },
];
