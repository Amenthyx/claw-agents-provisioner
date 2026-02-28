import { useState, useEffect } from 'react';
import { Cpu, MemoryStick, Monitor, Loader2, AlertTriangle, Settings } from 'lucide-react';
import { motion } from 'framer-motion';
import { StatCard } from '../ui/card';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import type { HardwareProfile } from '../../lib/types';
import { staggerContainer, cardVariant, fadeInUp } from '../../lib/motion';

const MOCK_HARDWARE: HardwareProfile = {
  os: { name: 'Windows', version: '11', arch: 'x86_64' },
  cpu: { brand: 'AMD Ryzen 9 5900X', cores: 12, features: ['AVX2', 'SSE4.2'] },
  ram_gb: 32,
  gpus: [{ vendor: 'NVIDIA', name: 'RTX 3080', vram_gb: 10, api: 'CUDA 12.1' }],
  gpu_summary: { has_gpu: true, primary_vendor: 'NVIDIA', max_vram_gb: 10 },
};

const MOCK_RECOMMENDATION = {
  primary: { id: 'ollama', name: 'Ollama', port: 11434 },
  fallback: { id: 'llama-cpp', name: 'llama.cpp', port: 8080 },
  reason: 'NVIDIA GPU detected with 10GB VRAM. Ollama provides the best balance of ease-of-use and performance.',
};

export function StepHardware() {
  const [hardware, setHardware] = useState<HardwareProfile | null>(null);
  const [recommendation, setRecommendation] = useState<typeof MOCK_RECOMMENDATION | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function detect() {
      setLoading(true);
      try {
        const res = await fetch('/api/wizard/hardware');
        if (!res.ok) throw new Error('API not available');
        const data = await res.json();
        setHardware(data.hardware);
        setRecommendation(data.recommendation);
      } catch {
        setError('Hardware detection API not available. Showing example configuration.');
        setHardware(MOCK_HARDWARE);
        setRecommendation(MOCK_RECOMMENDATION);
      } finally {
        setLoading(false);
      }
    }
    detect();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh]">
        <Loader2 className="w-8 h-8 text-neon-cyan animate-spin mb-4" />
        <p className="text-text-secondary font-mono text-neon-cyan">Scanning hardware...</p>
      </div>
    );
  }

  return (
    <div>
      <motion.div className="mb-8" variants={fadeInUp} initial="initial" animate="animate">
        <h2 className="text-2xl font-bold text-text-primary mb-2">Hardware Profile</h2>
        <p className="text-text-secondary">
          Your system hardware has been analyzed to determine optimal configuration.
        </p>
      </motion.div>

      {error && (
        <div className="flex items-center gap-3 p-4 rounded-lg border border-status-warning/20 bg-status-warning/5 mb-6">
          <AlertTriangle className="w-5 h-5 text-status-warning shrink-0" />
          <p className="text-sm text-status-warning font-mono">{error}</p>
        </div>
      )}

      {hardware && (
        <>
          {/* System stats */}
          <motion.div
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8"
            variants={staggerContainer}
            initial="initial"
            animate="animate"
          >
            <motion.div variants={cardVariant}>
              <StatCard
                label="Operating System"
                value={`${hardware.os.name} ${hardware.os.version}`}
                icon={<Monitor className="w-5 h-5" />}
              />
            </motion.div>
            <motion.div variants={cardVariant}>
              <StatCard
                label="CPU"
                value={`${hardware.cpu.cores} Cores`}
                icon={<Cpu className="w-5 h-5" />}
              />
            </motion.div>
            <motion.div variants={cardVariant}>
              <StatCard
                label="RAM"
                value={`${hardware.ram_gb} GB`}
                icon={<MemoryStick className="w-5 h-5" />}
              />
            </motion.div>
            <motion.div variants={cardVariant}>
              <StatCard
                label="Architecture"
                value={hardware.os.arch}
                icon={<Settings className="w-5 h-5" />}
              />
            </motion.div>
          </motion.div>

          {/* CPU Details */}
          <Card className="mb-4">
            <CardContent>
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-neon-cyan" />
                Processor
              </h3>
              <p className="text-text-secondary text-sm mb-2 font-mono">{hardware.cpu.brand}</p>
              <div className="flex gap-2 flex-wrap">
                {hardware.cpu.features.map((f) => (
                  <Badge key={f} variant="accent">{f}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* GPU Details */}
          <Card className="mb-6">
            <CardContent>
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Monitor className="w-4 h-4 text-neon-cyan" />
                GPU
              </h3>
              {hardware.gpus.length > 0 ? (
                <div className="space-y-3">
                  {hardware.gpus.map((gpu, i) => (
                    <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-cyber-bg-surface border border-cyber-border">
                      <div>
                        <p className="text-sm font-medium text-text-primary font-mono">{gpu.name}</p>
                        <p className="text-xs text-text-muted font-mono">{gpu.vendor} - {gpu.api}</p>
                      </div>
                      <Badge variant="success">{gpu.vram_gb} GB VRAM</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-3 rounded-lg bg-cyber-bg-surface border border-cyber-border">
                  <p className="text-sm text-text-secondary">No dedicated GPU detected</p>
                  <p className="text-xs text-text-muted mt-1 font-mono">CPU inference will be used for local models</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recommendation */}
          {recommendation && (
            <Card className="border-neon-cyan/30 bg-neon-cyan/5 border-l-4 border-l-neon-cyan" style={{ borderImage: 'linear-gradient(to bottom, #00ffcc, #ff00ff) 1', borderImageSlice: '0 0 0 4' }}>
              <CardContent>
                <h3 className="text-sm font-semibold text-neon-cyan mb-3 flex items-center gap-2">
                  <Settings className="w-4 h-4" />
                  Recommended Runtime
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-3">
                  <div className="p-3 rounded-lg bg-cyber-bg/50 border border-cyber-border">
                    <p className="text-xs text-text-muted mb-1 font-mono">Primary</p>
                    <p className="text-sm font-medium text-text-primary">{recommendation.primary.name}</p>
                    <Badge variant="accent" className="mt-1"><span className="font-mono">:{recommendation.primary.port}</span></Badge>
                  </div>
                  <div className="p-3 rounded-lg bg-cyber-bg/50 border border-cyber-border">
                    <p className="text-xs text-text-muted mb-1 font-mono">Fallback</p>
                    <p className="text-sm font-medium text-text-primary">{recommendation.fallback.name}</p>
                    <Badge className="mt-1"><span className="font-mono">:{recommendation.fallback.port}</span></Badge>
                  </div>
                </div>
                <p className="text-sm text-text-secondary">{recommendation.reason}</p>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
