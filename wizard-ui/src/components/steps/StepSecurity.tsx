import { Shield, ShieldCheck, ShieldAlert } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Checkbox } from '../ui/checkbox';
import { Badge } from '../ui/badge';
import { SECURITY_OPTIONS } from '../../lib/types';

interface StepSecurityProps {
  enabled: boolean;
  onToggleEnabled: () => void;
  features: string[];
  onToggleFeature: (featureId: string) => void;
}

export function StepSecurity({ enabled, onToggleEnabled, features, onToggleFeature }: StepSecurityProps) {
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-[#e0e0e0] mb-2">Security Configuration</h2>
        <p className="text-[#a0a0a0]">
          Configure security scanning and compliance features for your agent deployment.
        </p>
      </div>

      {/* Main toggle */}
      <Card
        className={`mb-8 max-w-2xl cursor-pointer ${enabled ? 'border-[#00d4aa]/30' : ''}`}
        onClick={onToggleEnabled}
      >
        <CardContent className="py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`
                w-14 h-14 rounded-2xl flex items-center justify-center transition-colors
                ${enabled ? 'bg-[#00d4aa]/20 text-[#00d4aa]' : 'bg-[#1a1a2e] text-[#a0a0a0]'}
              `}>
                {enabled ? <ShieldCheck className="w-7 h-7" /> : <Shield className="w-7 h-7" />}
              </div>
              <div>
                <h3 className="text-lg font-semibold text-[#e0e0e0]">Security Scanning</h3>
                <p className="text-sm text-[#a0a0a0]">
                  Enable security features for agent interactions
                </p>
              </div>
            </div>

            {/* Toggle switch */}
            <button
              onClick={(e) => { e.stopPropagation(); onToggleEnabled(); }}
              className={`
                w-14 h-7 rounded-full transition-colors duration-300 relative
                ${enabled ? 'bg-[#00d4aa]' : 'bg-[#2a2a4e]'}
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
      {enabled && (
        <div className="space-y-6 max-w-2xl">
          {/* Filtering & Detection */}
          <div>
            <h3 className="text-sm font-semibold text-[#e0e0e0] uppercase tracking-wider mb-4 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-[#00d4aa]" />
              Filtering & Detection
            </h3>
            <div className="space-y-1">
              {SECURITY_OPTIONS.filter(o => ['url-filtering', 'content-rules', 'pii-detection', 'network-rules'].includes(o.id)).map((option) => (
                <Card
                  key={option.id}
                  className={`cursor-pointer ${features.includes(option.id) ? 'border-[#00d4aa]/30 bg-[#00d4aa]/5' : ''}`}
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
            <h3 className="text-sm font-semibold text-[#e0e0e0] uppercase tracking-wider mb-4 flex items-center gap-2">
              <Shield className="w-4 h-4 text-[#00d4aa]" />
              Compliance Standards
            </h3>
            <div className="space-y-1">
              {SECURITY_OPTIONS.filter(o => ['gdpr', 'hipaa', 'pci-dss'].includes(o.id)).map((option) => (
                <Card
                  key={option.id}
                  className={`cursor-pointer ${features.includes(option.id) ? 'border-[#00d4aa]/30 bg-[#00d4aa]/5' : ''}`}
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
                        {option.id.toUpperCase()}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {/* Summary */}
          {features.length > 0 && (
            <div className="p-4 rounded-lg border border-[#2a2a4e] bg-[#16213e]/50">
              <p className="text-xs text-[#666] uppercase tracking-wider mb-2">
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
        </div>
      )}
    </div>
  );
}
