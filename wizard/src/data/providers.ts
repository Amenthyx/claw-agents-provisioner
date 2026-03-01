import type { CloudProvider, LocalRuntime } from '../state/types';

export const CLOUD_PROVIDERS: CloudProvider[] = [
  { id: 'anthropic', name: 'Anthropic', model: 'Claude 4', color: '#d97706' },
  { id: 'openai', name: 'OpenAI', model: 'GPT-4o', color: '#10b981' },
  { id: 'deepseek', name: 'DeepSeek', model: 'DeepSeek V3', color: '#6366f1' },
  { id: 'google', name: 'Google', model: 'Gemini Pro', color: '#3b82f6' },
  { id: 'groq', name: 'Groq', model: 'LPU Inference', color: '#f97316' },
];

// Fallback data — used when backend /runtimes is unavailable
export const LOCAL_RUNTIMES: LocalRuntime[] = [
  { id: 'ollama', name: 'Ollama', port: 11434, description: 'Easiest setup, broad hardware support, CPU + GPU' },
  { id: 'llamacpp', name: 'llama.cpp', port: 8080, description: 'Most efficient CPU inference, smallest footprint' },
  { id: 'vllm', name: 'vLLM', port: 8000, description: 'Highest throughput GPU inference with PagedAttention' },
  { id: 'ipexllm', name: 'ipex-llm', port: 8010, description: 'Intel-optimized with SYCL/AMX acceleration' },
  { id: 'sglang', name: 'SGLang', port: 30000, description: 'Fast serving with RadixAttention, CUDA only' },
  { id: 'docker_model_runner', name: 'Docker Model Runner', port: 12434, description: 'Docker-native model serving, easy container integration' },
  { id: 'localai', name: 'LocalAI', port: 8081, description: 'OpenAI-compatible API for local models' },
];
