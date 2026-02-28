import { Cloud, HardDrive } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';

interface StepLLMProps {
  selected: 'cloud' | 'local';
  onSelect: (provider: 'cloud' | 'local') => void;
  runtime: string;
  onRuntimeChange: (runtime: string) => void;
}

const cloudProviders = [
  { name: 'Anthropic', model: 'Claude', color: '#d4a574' },
  { name: 'OpenAI', model: 'GPT-4', color: '#74aa9c' },
  { name: 'DeepSeek', model: 'DeepSeek V3', color: '#4a9eff' },
  { name: 'Google', model: 'Gemini', color: '#4285f4' },
  { name: 'Groq', model: 'LPU Inference', color: '#f55036' },
];

const localRuntimes = [
  { id: 'ollama', name: 'Ollama', description: 'Easy-to-use local model runner', port: 11434 },
  { id: 'llama-cpp', name: 'llama.cpp', description: 'High-performance CPU/GPU inference', port: 8080 },
  { id: 'vllm', name: 'vLLM', description: 'Production-grade GPU inference server', port: 8000 },
  { id: 'localai', name: 'LocalAI', description: 'OpenAI-compatible local API', port: 8080 },
];

export function StepLLM({ selected, onSelect, runtime, onRuntimeChange }: StepLLMProps) {
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-[#e0e0e0] mb-2">LLM Provider</h2>
        <p className="text-[#a0a0a0]">
          Choose between cloud-based API providers or running models locally on your hardware.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl">
        {/* Cloud API */}
        <Card
          selected={selected === 'cloud'}
          hoverable
          onClick={() => onSelect('cloud')}
          className="relative"
        >
          {selected === 'cloud' && (
            <div className="absolute top-4 right-4">
              <Badge variant="accent">Selected</Badge>
            </div>
          )}
          <CardContent className="pt-8 pb-8">
            <div className={`
              w-16 h-16 rounded-2xl flex items-center justify-center mb-6
              ${selected === 'cloud' ? 'bg-[#00d4aa]/20 text-[#00d4aa]' : 'bg-[#1a1a2e] text-[#a0a0a0]'}
              transition-colors
            `}>
              <Cloud className="w-8 h-8" />
            </div>

            <h3 className="text-xl font-semibold text-[#e0e0e0] mb-2">Cloud API</h3>
            <p className="text-sm text-[#a0a0a0] mb-6 leading-relaxed">
              Use cloud-hosted LLM providers. No GPU required. Pay-per-use pricing
              with instant access to the latest models.
            </p>

            <div className="space-y-3">
              <p className="text-xs text-[#666] uppercase tracking-wider font-medium">
                Supported Providers
              </p>
              {cloudProviders.map((provider) => (
                <div key={provider.name} className="flex items-center gap-3">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: provider.color }}
                  />
                  <span className="text-sm text-[#e0e0e0]">{provider.name}</span>
                  <span className="text-xs text-[#666]">{provider.model}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Local LLM */}
        <Card
          selected={selected === 'local'}
          hoverable
          onClick={() => onSelect('local')}
          className="relative"
        >
          {selected === 'local' && (
            <div className="absolute top-4 right-4">
              <Badge variant="accent">Selected</Badge>
            </div>
          )}
          <CardContent className="pt-8 pb-8">
            <div className={`
              w-16 h-16 rounded-2xl flex items-center justify-center mb-6
              ${selected === 'local' ? 'bg-[#00d4aa]/20 text-[#00d4aa]' : 'bg-[#1a1a2e] text-[#a0a0a0]'}
              transition-colors
            `}>
              <HardDrive className="w-8 h-8" />
            </div>

            <h3 className="text-xl font-semibold text-[#e0e0e0] mb-2">Local LLM</h3>
            <p className="text-sm text-[#a0a0a0] mb-6 leading-relaxed">
              Run models on your own hardware. Full data privacy, no API costs,
              and offline capability. Requires GPU for best performance.
            </p>

            <div className="space-y-3">
              <p className="text-xs text-[#666] uppercase tracking-wider font-medium">
                Select Runtime
              </p>
              {localRuntimes.map((rt) => (
                <button
                  key={rt.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect('local');
                    onRuntimeChange(rt.id);
                  }}
                  className={`
                    w-full flex items-center justify-between p-3 rounded-lg border text-left
                    transition-all duration-200
                    ${runtime === rt.id && selected === 'local'
                      ? 'border-[#00d4aa] bg-[#00d4aa]/5'
                      : 'border-[#2a2a4e] hover:border-[#00d4aa]/30 bg-transparent'
                    }
                  `}
                >
                  <div>
                    <p className="text-sm font-medium text-[#e0e0e0]">{rt.name}</p>
                    <p className="text-xs text-[#666]">{rt.description}</p>
                  </div>
                  <Badge variant={runtime === rt.id && selected === 'local' ? 'accent' : 'default'}>
                    :{rt.port}
                  </Badge>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
