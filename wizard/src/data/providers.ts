import type { CloudProvider, LocalRuntime } from '../state/types';

export const CLOUD_PROVIDERS: CloudProvider[] = [
  { id: 'anthropic', name: 'Anthropic', model: 'Claude 4', color: '#d97706' },
  { id: 'openai', name: 'OpenAI', model: 'GPT-4o', color: '#10b981' },
  { id: 'deepseek', name: 'DeepSeek', model: 'DeepSeek V3', color: '#6366f1' },
  { id: 'google', name: 'Google', model: 'Gemini Pro', color: '#3b82f6' },
  { id: 'groq', name: 'Groq', model: 'LPU Inference', color: '#f97316' },
];

// Fallback data — used when backend /runtimes is unavailable
// All runtimes install natively on the host (bare metal) for full GPU access
export const LOCAL_RUNTIMES: LocalRuntime[] = [
  { id: 'ollama', name: 'Ollama', port: 11434, description: 'Native install — easiest setup, full GPU passthrough, CPU + GPU' },
  { id: 'llamacpp', name: 'llama.cpp', port: 8080, description: 'Native install — most efficient CPU inference, smallest footprint' },
  { id: 'vllm', name: 'vLLM', port: 8000, description: 'Native install — highest throughput GPU inference with PagedAttention' },
  { id: 'ipexllm', name: 'ipex-llm', port: 8010, description: 'Native install — Intel-optimized with SYCL/AMX acceleration' },
  { id: 'sglang', name: 'SGLang', port: 30000, description: 'Native install — fast serving with RadixAttention, CUDA GPU' },
  { id: 'localai', name: 'LocalAI', port: 8081, description: 'Native install — OpenAI-compatible API for local models' },
];
