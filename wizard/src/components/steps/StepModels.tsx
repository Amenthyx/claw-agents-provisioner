import { useEffect, useState } from 'react';
import { AlertTriangle, Cloud, Check, Cpu, MemoryStick, Zap } from 'lucide-react';
import { useWizard } from '../../state/context';
import { MODELS as FALLBACK_MODELS } from '../../data/models';
import { api } from '../../lib/api';
import { estimateTokensPerSecond } from '../../lib/token-estimate';
import type { TokenEstimate } from '../../lib/token-estimate';
import { Badge } from '../ui/Badge';
import { Progress } from '../ui/Progress';

/** Parse the numeric parameter count from strings like "70B", "671B (MoE)" */
function parseParamB(s: string | undefined): number {
  if (!s) return 0;
  const match = s.match(/([\d.]+)\s*B/i);
  return match?.[1] ? parseFloat(match[1]) : 0;
}

const CATEGORY_LABELS: Record<string, string> = {
  general: 'General',
  coding: 'Coding',
  reasoning: 'Reasoning',
};

export function StepModels() {
  const { state, toggleModel } = useWizard();
  const models = FALLBACK_MODELS;
  const [apiVram, setApiVram] = useState<number | null>(null);

  useEffect(() => {
    // Only fetch to get detected VRAM — always keep the full model catalog
    api.getModels()
      .then((data) => {
        if (typeof data.available_memory_gb === 'number') {
          setApiVram(data.available_memory_gb);
        }
      })
      .catch(() => { /* use fallback */ });
  }, []);

  if (state.llmProvider === 'cloud') {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent mb-4">
          <Cloud size={24} />
        </div>
        <h3 className="text-lg font-medium text-text-primary">No Local Models Needed</h3>
        <p className="text-sm text-text-secondary mt-2 max-w-sm">
          Cloud-only mode uses remote APIs — no local model downloads required.
          Continue to configure security settings.
        </p>
      </div>
    );
  }

  const totalVram = apiVram ?? state.hardware?.gpus.reduce((sum, g) => sum + (g.vram ?? 0), 0) ?? 0;
  const totalRam = state.hardware?.ram ?? 16;
  // For model fitting, available memory = max(VRAM, RAM) since large models can run in CPU offload mode
  const availableMemory = Math.max(totalVram, totalRam);

  const usedMemory = state.selectedModels.reduce((sum, id) => {
    const model = models.find((m) => m.id === id);
    return sum + (model?.vramRequired ?? 0);
  }, 0);
  const exceeds = usedMemory > availableMemory;

  // GPU name for display
  const gpuName = state.hardware?.gpus?.[0]?.name ?? '';
  const gpuShort = gpuName.length > 40 ? gpuName.slice(0, 40) + '...' : gpuName;

  // Group by size tier
  const tiers = [
    { label: 'Tiny (0.6-1.7B)', min: 0, max: 3 },
    { label: 'Small (3-8B)', min: 3, max: 9 },
    { label: 'Medium (12-16B)', min: 9, max: 20 },
    { label: 'Large (22-33B)', min: 20, max: 40 },
    { label: 'XL (70-109B)', min: 40, max: 80 },
    { label: 'XXL (124-236B)', min: 80, max: 200 },
    { label: 'Ultra (397B+)', min: 200, max: Infinity },
  ];

  const categoryColors = { general: 'default', coding: 'accent', reasoning: 'warning' } as const;

  const MODE_LABELS: Record<string, string> = { gpu: 'GPU', partial: 'offload', cpu: 'CPU' };
  function tokBadgeVariant(est: TokenEstimate): 'accent' | 'secondary' | 'warning' | 'error' {
    if (est.tokensPerSecond >= 30) return 'accent';
    if (est.tokensPerSecond >= 10) return 'secondary';
    if (est.tokensPerSecond >= 3) return 'warning';
    return 'error';
  }

  return (
    <div className="space-y-6">
      {/* Memory Budget Bar — values from hardware detection */}
      <div className="rounded-xl border border-border-base bg-surface-1 p-4">
        <div className="flex items-center justify-between text-sm mb-2">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5 text-text-secondary">
                <Cpu size={14} />
                GPU: {totalVram} GB
              </span>
              <span className="flex items-center gap-1.5 text-text-secondary">
                <MemoryStick size={14} />
                RAM: {totalRam} GB
              </span>
            </div>
            {gpuShort && (
              <span className="text-xs text-text-muted">{gpuShort}</span>
            )}
          </div>
          <span className={exceeds ? 'text-error font-medium' : 'text-text-primary'}>
            {usedMemory} / {availableMemory} GB used
          </span>
        </div>
        <Progress value={usedMemory} max={availableMemory} size="md" />
        {exceeds && (
          <div className="flex items-center gap-1.5 mt-2 text-xs text-error">
            <AlertTriangle size={12} />
            Memory budget exceeded — models may swap to disk or fail to load
          </div>
        )}
        {availableMemory >= 256 && (
          <p className="text-xs text-accent mt-2">
            High-capacity system — 400B+ parameter models are available
          </p>
        )}
        <p className="text-xs text-text-muted mt-1">
          Detected from device hardware analysis. Available: {availableMemory} GB (max of GPU + RAM for CPU offload).
        </p>
      </div>

      {/* Model Grid grouped by tier */}
      {tiers.map((tier) => {
        const tierModels = models.filter((m) => {
          const v = m.vramRequired;
          return v >= tier.min && v < tier.max;
        });
        if (tierModels.length === 0) return null;

        // Check if any model in this tier fits
        const anyFits = tierModels.some((m) => m.vramRequired <= availableMemory);

        return (
          <div key={tier.label}>
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-sm font-medium text-text-primary">{tier.label}</h3>
              {!anyFits && (
                <Badge variant="error">Exceeds capacity</Badge>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              {tierModels.map((m) => {
                const selected = state.selectedModels.includes(m.id);
                const wouldExceed = !selected && usedMemory + m.vramRequired > availableMemory;
                const paramB = parseParamB(m.parameters);
                const estimate = estimateTokensPerSecond(m, state.hardware);

                return (
                  <div
                    key={m.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => toggleModel(m.id)}
                    className={[
                      'rounded-xl border p-5 transition-all duration-150 h-full cursor-pointer hover:bg-surface-2',
                      selected
                        ? 'border-accent bg-accent/[0.03] ring-1 ring-accent/30'
                        : 'border-border-base bg-surface-1',
                    ].join(' ')}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="text-sm font-medium text-text-primary">
                          {m.name}
                        </h4>
                        <p className="text-xs text-text-muted mt-0.5">
                          {m.parameters}
                          {paramB >= 100 ? ' — multi-GPU / CPU offload' : ''}
                        </p>
                      </div>
                      {selected ? (
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-white shrink-0">
                          <Check size={12} />
                        </span>
                      ) : wouldExceed ? (
                        <Badge variant="warning">Exceeds RAM</Badge>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      <Badge variant={categoryColors[m.category] ?? 'default'}>
                        {CATEGORY_LABELS[m.category] ?? m.category}
                      </Badge>
                      <Badge variant="muted">{m.diskSize}</Badge>
                      <Badge variant={wouldExceed ? 'error' : 'secondary'}>
                        {m.vramRequired} GB {m.vramRequired >= 48 ? 'RAM/VRAM' : 'VRAM'}
                      </Badge>
                      {estimate && (
                        <Badge variant={tokBadgeVariant(estimate)}>
                          <span className="inline-flex items-center gap-1">
                            <Zap size={10} />
                            ~{estimate.tokensPerSecond} tok/s
                            <span className="opacity-60">{MODE_LABELS[estimate.mode]}</span>
                          </span>
                        </Badge>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
