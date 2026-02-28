import { Download, AlertTriangle, HardDrive } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Checkbox } from '../ui/checkbox';
import { MODELS } from '../../lib/types';

interface StepModelsProps {
  llmProvider: 'cloud' | 'local';
  selectedModels: string[];
  onToggleModel: (modelName: string) => void;
  availableVram: number;
}

export function StepModels({ llmProvider, selectedModels, onToggleModel, availableVram }: StepModelsProps) {
  if (llmProvider === 'cloud') {
    return (
      <div>
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-[#e0e0e0] mb-2">Model Selection</h2>
          <p className="text-[#a0a0a0]">
            You selected Cloud API as your LLM provider. Models will be accessed via API and
            don't need to be downloaded locally.
          </p>
        </div>

        <Card className="border-[#00d4aa]/30 bg-[#00d4aa]/5 max-w-2xl">
          <CardContent className="py-8">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-xl bg-[#00d4aa]/20 text-[#00d4aa] flex items-center justify-center">
                <Download className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-[#e0e0e0]">No Local Models Needed</h3>
                <p className="text-sm text-[#a0a0a0]">
                  Cloud providers handle model hosting and inference
                </p>
              </div>
            </div>
            <p className="text-sm text-[#a0a0a0] leading-relaxed">
              You can configure your API keys and preferred models after deployment.
              The agent platform supports dynamic model switching at runtime.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const totalSelectedVram = MODELS
    .filter((m) => selectedModels.includes(m.name))
    .reduce((sum, m) => sum + m.vram_gb, 0);

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-[#e0e0e0] mb-2">Select Local Models</h2>
        <p className="text-[#a0a0a0]">
          Choose which models to download and run locally. Models are filtered by your
          available VRAM ({availableVram} GB).
        </p>
      </div>

      {/* VRAM usage indicator */}
      <div className="flex items-center gap-4 p-4 rounded-lg border border-[#2a2a4e] bg-[#16213e]/50 mb-6 max-w-2xl">
        <HardDrive className="w-5 h-5 text-[#00d4aa] shrink-0" />
        <div className="flex-1">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-[#a0a0a0]">VRAM Usage</span>
            <span className={totalSelectedVram > availableVram ? 'text-[#ff4757]' : 'text-[#00d4aa]'}>
              {totalSelectedVram} / {availableVram} GB
            </span>
          </div>
          <div className="w-full h-2 bg-[#1a1a2e] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                totalSelectedVram > availableVram
                  ? 'bg-[#ff4757]'
                  : totalSelectedVram > availableVram * 0.8
                    ? 'bg-[#ffa502]'
                    : 'bg-[#00d4aa]'
              }`}
              style={{ width: `${Math.min((totalSelectedVram / availableVram) * 100, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {totalSelectedVram > availableVram && (
        <div className="flex items-center gap-3 p-4 rounded-lg border border-[#ff4757]/20 bg-[#ff4757]/5 mb-6 max-w-2xl">
          <AlertTriangle className="w-5 h-5 text-[#ff4757] shrink-0" />
          <p className="text-sm text-[#ff4757]">
            Selected models exceed available VRAM. Performance may be degraded.
          </p>
        </div>
      )}

      {/* Model cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl">
        {MODELS.map((model) => {
          const canRun = model.vram_gb <= availableVram;
          const isSelected = selectedModels.includes(model.name);

          return (
            <Card
              key={model.name}
              selected={isSelected}
              hoverable={canRun}
              onClick={() => canRun && onToggleModel(model.name)}
              className={!canRun ? 'opacity-50' : ''}
            >
              <CardContent>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Checkbox
                        checked={isSelected}
                        disabled={!canRun}
                        onChange={() => canRun && onToggleModel(model.name)}
                      />
                      <h3 className="text-sm font-semibold text-[#e0e0e0]">{model.name}</h3>
                    </div>
                    <div className="flex flex-wrap gap-2 ml-8">
                      <Badge>{model.parameters} params</Badge>
                      <Badge>{model.size_gb} GB disk</Badge>
                      <Badge variant={canRun ? 'success' : 'error'}>
                        {model.vram_gb} GB VRAM
                      </Badge>
                    </div>
                  </div>
                </div>
                {!canRun && (
                  <p className="text-xs text-[#ff4757] mt-2 ml-8">
                    Requires {model.vram_gb} GB VRAM (you have {availableVram} GB)
                  </p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
