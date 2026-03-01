import { useEffect } from 'react';
import { Cpu, HardDrive, Monitor, Zap } from 'lucide-react';
import { motion } from 'framer-motion';
import { useWizard } from '../../state/context';
import { useHardwareDetection } from '../../hooks/useHardwareDetection';
import { Card, StatCard } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { stagger, fadeInUp } from '../../lib/motion';

function str(val: unknown): string {
  if (val == null) return '';
  if (typeof val === 'string') return val;
  if (typeof val === 'object' && 'name' in (val as Record<string, unknown>)) {
    const o = val as Record<string, unknown>;
    return [o.name, o.version].filter(Boolean).join(' ');
  }
  return String(val);
}

export function StepHardware() {
  const { setHardware } = useWizard();
  const { hardware, recommendation, loading, error, detect } = useHardwareDetection();

  useEffect(() => {
    detect().then((data) => {
      if (data) setHardware(data.hardware, data.recommendation);
    });
  }, [detect, setHardware]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        <p className="mt-4 text-sm text-text-secondary">Detecting hardware...</p>
      </div>
    );
  }

  if (!hardware) return null;

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-6">
      {error && (
        <motion.div variants={fadeInUp}>
          <Badge variant="warning">{error}</Badge>
        </motion.div>
      )}

      {/* System overview */}
      <motion.div variants={fadeInUp} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard icon={<Monitor size={16} />} label="OS" value={str(hardware.os)} />
        <StatCard icon={<Cpu size={16} />} label="Cores" value={String(hardware.cpu.cores)} />
        <StatCard icon={<HardDrive size={16} />} label="RAM" value={`${hardware.ram} GB`} />
        <StatCard icon={<Zap size={16} />} label="Arch" value={str(hardware.arch)} />
      </motion.div>

      {/* CPU Details */}
      <motion.div variants={fadeInUp}>
        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-1">CPU</h3>
          <p className="text-sm text-text-secondary">{str(hardware.cpu.brand)}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {hardware.cpu.features.map((f, i) => (
              <Badge key={i} variant="secondary">{str(f)}</Badge>
            ))}
          </div>
        </Card>
      </motion.div>

      {/* GPU Details */}
      {hardware.gpus.length > 0 && (
        <motion.div variants={fadeInUp}>
          <Card>
            <h3 className="text-sm font-medium text-text-primary mb-3">GPU</h3>
            <div className="space-y-3">
              {hardware.gpus.map((gpu, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-text-primary">{str(gpu.name)}</p>
                    <p className="text-xs text-text-muted">{str(gpu.api)}</p>
                  </div>
                  <Badge variant="accent">{gpu.vram} GB VRAM</Badge>
                </div>
              ))}
            </div>
          </Card>
        </motion.div>
      )}

      {/* Recommendation */}
      {recommendation && (
        <motion.div variants={fadeInUp}>
          <Card className="border-accent/20 bg-accent/[0.03]">
            <h3 className="text-sm font-medium text-accent mb-1">Recommended Runtime</h3>
            <p className="text-sm text-text-primary">
              {str(recommendation.primary)}
              <span className="text-text-muted"> · Fallback: {str(recommendation.fallback)}</span>
            </p>
            <p className="text-xs text-text-secondary mt-2">{str(recommendation.reason)}</p>
          </Card>
        </motion.div>
      )}
    </motion.div>
  );
}
