import { useEffect, useState } from 'react';
import { AlertTriangle, Check } from 'lucide-react';
import { motion } from 'framer-motion';
import { useWizard } from '../../state/context';
import { PLATFORMS as FALLBACK_PLATFORMS } from '../../data/platforms';
import { api } from '../../lib/api';
import { SelectionCard } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { stagger, fadeInUp } from '../../lib/motion';
import type { Platform, HardwareProfile } from '../../state/types';

function getCompatibility(platform: Platform, hw: HardwareProfile | null) {
  if (!hw) return { compatible: true, reason: '' };
  if (platform.minRam && hw.ram < platform.minRam) {
    return { compatible: false, reason: `Requires ${platform.minRam} GB RAM (you have ${hw.ram} GB)` };
  }
  if (platform.minCores && hw.cpu.cores < platform.minCores) {
    return { compatible: false, reason: `Requires ${platform.minCores} CPU cores (you have ${hw.cpu.cores})` };
  }
  return { compatible: true, reason: '' };
}

function sortPlatforms(platforms: Platform[], hw: HardwareProfile | null) {
  return [...platforms].sort((a, b) => {
    const ca = getCompatibility(a, hw).compatible;
    const cb = getCompatibility(b, hw).compatible;
    if (ca !== cb) return ca ? -1 : 1;
    return 0;
  });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizePlatforms(raw: any[]): Platform[] {
  return raw.map((p) => ({
    id: p.id ?? '',
    name: p.name ?? '',
    language: p.language ?? '',
    memory: p.memory ?? '',
    port: p.port ?? 0,
    description: p.description ?? '',
    features: p.features ?? [],
    minRam: p.minRam ?? p.min_ram ?? 0,
    minCores: p.minCores ?? p.min_cores ?? 0,
    gpuRequired: p.gpuRequired ?? p.gpu_required ?? false,
    tier: p.tier ?? 'standard',
  }));
}

export function StepPlatform() {
  const { state, setPlatform } = useWizard();
  const [platforms, setPlatforms] = useState<Platform[]>(FALLBACK_PLATFORMS);

  useEffect(() => {
    api.getPlatforms()
      .then((data) => {
        const raw = data.platforms ?? data;
        if (Array.isArray(raw) && raw.length > 0) {
          setPlatforms(normalizePlatforms(raw));
        }
      })
      .catch(() => { /* use fallback */ });
  }, []);

  const sorted = sortPlatforms(platforms, state.hardware);

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-3">
      {sorted.map((p) => {
        const { compatible, reason } = getCompatibility(p, state.hardware);
        const selected = state.platform === p.id;

        return (
          <motion.div key={p.id} variants={fadeInUp}>
            <SelectionCard
              selected={selected}
              disabled={!compatible}
              onClick={() => setPlatform(p.id)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-text-primary">{p.name}</h3>
                    <Badge variant="secondary">{p.language}</Badge>
                    {p.tier && <Badge variant="muted">{p.tier}</Badge>}
                    {selected && (
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-white">
                        <Check size={12} />
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-text-secondary mt-1">{p.description}</p>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {p.features.map((f) => (
                      <Badge key={f} variant="default">{f}</Badge>
                    ))}
                  </div>
                  <div className="flex gap-4 mt-2 text-xs text-text-muted">
                    <span>Memory: {p.memory}</span>
                    <span>Port: {p.port}</span>
                  </div>
                </div>
              </div>
              {!compatible && (
                <div className="mt-3 flex items-center gap-1.5 text-xs text-warning">
                  <AlertTriangle size={12} />
                  {reason}
                </div>
              )}
            </SelectionCard>
          </motion.div>
        );
      })}
    </motion.div>
  );
}
