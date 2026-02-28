import { Download, AlertTriangle, HardDrive } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Checkbox } from '../ui/checkbox';
import { MODELS } from '../../lib/types';
import { staggerContainer, cardVariant, fadeInUp } from '../../lib/motion';

interface StepModelsProps {
  llmProvider: 'cloud' | 'local' | 'hybrid';
  selectedModels: string[];
  onToggleModel: (modelName: string) => void;
  availableVram: number;
}

export function StepModels({ llmProvider, selectedModels, onToggleModel, availableVram }: StepModelsProps) {
  if (llmProvider === 'cloud') {
    return (
      <div>
        <motion.div className="mb-8" variants={fadeInUp} initial="initial" animate="animate">
          <h2 className="text-2xl font-bold text-text-primary mb-2">Model Selection</h2>
          <p className="text-text-secondary">
            You selected Cloud API as your LLM provider. Models will be accessed via API and
            don't need to be downloaded locally.
          </p>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card className="border-neon-cyan/30 bg-neon-cyan/5 max-w-2xl">
            <CardContent className="py-8">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-xl bg-neon-cyan/20 text-neon-cyan flex items-center justify-center">
                  <Download className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-text-primary">No Local Models Needed</h3>
                  <p className="text-sm text-text-secondary">
                    Cloud providers handle model hosting and inference
                  </p>
                </div>
              </div>
              <p className="text-sm text-text-secondary leading-relaxed">
                You can configure your API keys and preferred models after deployment.
                The agent platform supports dynamic model switching at runtime.
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }

  const totalSelectedVram = MODELS
    .filter((m) => selectedModels.includes(m.name))
    .reduce((sum, m) => sum + m.vram_gb, 0);

  return (
    <div>
      <motion.div className="mb-8" variants={fadeInUp} initial="initial" animate="animate">
        <h2 className="text-2xl font-bold text-text-primary mb-2">Select Local Models</h2>
        <p className="text-text-secondary">
          Choose which models to download and run locally. Models are filtered by your
          available VRAM (<span className="font-mono text-neon-cyan">{availableVram} GB</span>).
        </p>
      </motion.div>

      {/* VRAM usage indicator */}
      <div className="flex items-center gap-4 p-4 rounded-lg border border-cyber-border glass-card mb-6 max-w-2xl">
        <HardDrive className="w-5 h-5 text-neon-cyan shrink-0" />
        <div className="flex-1">
          <div className="flex justify-between text-sm mb-1 font-mono">
            <span className="text-text-secondary">VRAM Usage</span>
            <span className={totalSelectedVram > availableVram ? 'text-status-error' : 'text-neon-cyan'}>
              {totalSelectedVram} / {availableVram} GB
            </span>
          </div>
          <div className="w-full h-2 bg-cyber-bg-surface rounded-full overflow-hidden border border-cyber-border">
            <div
              className={`h-full rounded-full transition-all duration-300 relative ${
                totalSelectedVram > availableVram
                  ? 'bg-status-error shadow-[0_0_8px_#ff335540]'
                  : totalSelectedVram > availableVram * 0.8
                    ? 'bg-status-warning'
                    : 'bg-neon-cyan shadow-neon-sm'
              }`}
              style={{ width: `${Math.min((totalSelectedVram / availableVram) * 100, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {totalSelectedVram > availableVram && (
        <div className="flex items-center gap-3 p-4 rounded-lg border border-status-error/20 bg-status-error/5 mb-6 max-w-2xl">
          <AlertTriangle className="w-5 h-5 text-status-error shrink-0" />
          <p className="text-sm text-status-error font-mono">
            Selected models exceed available VRAM. Performance may be degraded.
          </p>
        </div>
      )}

      {/* Model cards */}
      <motion.div
        className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        {MODELS.map((model) => {
          const canRun = model.vram_gb <= availableVram;
          const isSelected = selectedModels.includes(model.name);

          return (
            <motion.div key={model.name} variants={cardVariant}>
              <Card
                selected={isSelected}
                hoverable={canRun}
                onClick={() => canRun && onToggleModel(model.name)}
                className={!canRun ? 'opacity-40 grayscale' : ''}
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
                        <h3 className="text-sm font-semibold text-text-primary font-mono">{model.name}</h3>
                      </div>
                      <div className="flex flex-wrap gap-2 ml-8">
                        <Badge><span className="font-mono">{model.parameters} params</span></Badge>
                        <Badge><span className="font-mono">{model.size_gb} GB disk</span></Badge>
                        <Badge variant={canRun ? 'success' : 'error'}>
                          <span className="font-mono">{model.vram_gb} GB VRAM</span>
                        </Badge>
                      </div>
                    </div>
                  </div>
                  {!canRun && (
                    <p className="text-xs text-status-error mt-2 ml-8 font-mono">
                      Requires {model.vram_gb} GB VRAM (you have {availableVram} GB)
                    </p>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}
