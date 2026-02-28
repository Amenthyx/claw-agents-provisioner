import { Shield, ShieldCheck, ShieldAlert } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent } from '../ui/card';
import { Checkbox } from '../ui/checkbox';
import { Badge } from '../ui/badge';
import { SECURITY_OPTIONS } from '../../lib/types';
import { fadeInUp } from '../../lib/motion';

interface StepSecurityProps {
  enabled: boolean;
  onToggleEnabled: () => void;
  features: string[];
  onToggleFeature: (featureId: string) => void;
}

export function StepSecurity({ enabled, onToggleEnabled, features, onToggleFeature }: StepSecurityProps) {
  return (
    <div>
      <motion.div className="mb-8" variants={fadeInUp} initial="initial" animate="animate">
        <h2 className="text-2xl font-bold text-text-primary mb-2">Security Configuration</h2>
        <p className="text-text-secondary">
          Configure security scanning and compliance features for your agent deployment.
        </p>
      </motion.div>

      {/* Main toggle */}
      <Card
        className={`mb-8 max-w-2xl cursor-pointer ${enabled ? 'border-neon-cyan/30' : ''}`}
        onClick={onToggleEnabled}
      >
        <CardContent className="py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`
                w-14 h-14 rounded-2xl flex items-center justify-center transition-colors
                ${enabled ? 'bg-neon-cyan/20 text-neon-cyan' : 'bg-cyber-bg-surface text-text-secondary'}
              `}>
                {enabled ? <ShieldCheck className="w-7 h-7" /> : <Shield className="w-7 h-7" />}
              </div>
              <div>
                <h3 className="text-lg font-semibold text-text-primary">Security Scanning</h3>
                <p className="text-sm text-text-secondary">
                  Enable security features for agent interactions
                </p>
              </div>
            </div>

            {/* Toggle switch */}
            <button
              onClick={(e) => { e.stopPropagation(); onToggleEnabled(); }}
              className={`
                w-14 h-7 rounded-full transition-all duration-300 relative
                ${enabled ? 'bg-neon-cyan shadow-neon-sm' : 'bg-cyber-border'}
              `}
            >
              <div
                className={`
                  w-5 h-5 rounded-full bg-white absolute top-1 transition-transform duration-300
                  ${enabled ? 'translate-x-8' : 'translate-x-1'}
                `}
              />
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Feature checkboxes */}
      <AnimatePresence>
        {enabled && (
          <motion.div
            className="space-y-6 max-w-2xl"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
          >
            {/* Filtering & Detection */}
            <div>
              <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider mb-4 flex items-center gap-2 font-mono">
                <ShieldAlert className="w-4 h-4 text-neon-cyan" />
                Filtering & Detection
              </h3>
              <div className="space-y-1">
                {SECURITY_OPTIONS.filter(o => ['url-filtering', 'content-rules', 'pii-detection', 'network-rules'].includes(o.id)).map((option) => (
                  <Card
                    key={option.id}
                    className={`cursor-pointer ${features.includes(option.id) ? 'border-neon-cyan/30 bg-neon-cyan/5' : ''}`}
                    onClick={() => onToggleFeature(option.id)}
                  >
                    <CardContent className="py-3">
                      <Checkbox
                        checked={features.includes(option.id)}
                        onChange={() => onToggleFeature(option.id)}
                        label={option.label}
                        description={option.description}
                      />
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            {/* Compliance */}
            <div>
              <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider mb-4 flex items-center gap-2 font-mono">
                <Shield className="w-4 h-4 text-neon-cyan" />
                Compliance Standards
              </h3>
              <div className="space-y-1">
                {SECURITY_OPTIONS.filter(o => ['gdpr', 'hipaa', 'pci-dss'].includes(o.id)).map((option) => (
                  <Card
                    key={option.id}
                    className={`cursor-pointer ${features.includes(option.id) ? 'border-neon-cyan/30 bg-neon-cyan/5' : ''}`}
                    onClick={() => onToggleFeature(option.id)}
                  >
                    <CardContent className="py-3">
                      <div className="flex items-center justify-between">
                        <Checkbox
                          checked={features.includes(option.id)}
                          onChange={() => onToggleFeature(option.id)}
                          label={option.label}
                          description={option.description}
                        />
                        <Badge variant={features.includes(option.id) ? 'accent' : 'default'}>
                          <span className="font-mono">{option.id.toUpperCase()}</span>
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            {/* Summary */}
            {features.length > 0 && (
              <div className="p-4 rounded-lg border border-cyber-border glass-card">
                <p className="text-xs text-text-muted uppercase tracking-wider mb-2 font-mono">
                  {features.length} feature{features.length !== 1 ? 's' : ''} enabled
                </p>
                <div className="flex flex-wrap gap-2">
                  {features.map((f) => {
                    const opt = SECURITY_OPTIONS.find((o) => o.id === f);
                    return <Badge key={f} variant="accent">{opt?.label || f}</Badge>;
                  })}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
