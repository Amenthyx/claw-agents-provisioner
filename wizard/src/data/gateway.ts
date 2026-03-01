import type { RoutingRule } from '../state/types';

export const FAILOVER_STRATEGIES = [
  { id: 'local-first', label: 'Local-First', description: 'Try local LLM, fall back to cloud on failure' },
  { id: 'cloud-first', label: 'Cloud-First', description: 'Try cloud API, fall back to local on failure' },
  { id: 'round-robin', label: 'Round-Robin', description: 'Distribute requests evenly across all backends' },
] as const;

export const ROUTING_MODES = [
  { id: 'auto', label: 'Auto-Detect', description: 'Route based on request complexity and model capability' },
  { id: 'manual', label: 'Manual', description: 'Explicit routing rules defined per endpoint' },
] as const;

export const ROUTING_TARGETS = [
  { id: 'auto', label: 'Auto' },
  { id: 'anthropic', label: 'Anthropic' },
  { id: 'openai', label: 'OpenAI' },
  { id: 'deepseek', label: 'DeepSeek' },
  { id: 'google', label: 'Google' },
  { id: 'groq', label: 'Groq' },
  { id: 'ollama', label: 'Ollama (Local)' },
  { id: 'llamacpp', label: 'llama.cpp (Local)' },
  { id: 'vllm', label: 'vLLM (Local)' },
  { id: 'custom', label: 'Custom Endpoint' },
] as const;

export const DEFAULT_ROUTES: RoutingRule[] = [
  { pattern: '/api/chat/*', target: 'auto', priority: 1 },
  { pattern: '/api/code/*', target: 'auto', priority: 2 },
  { pattern: '/api/embed/*', target: 'auto', priority: 3 },
];
