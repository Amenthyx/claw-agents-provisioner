import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import { useWizard } from '../../../state/context';
import { COMPLIANCE_RULES } from '../../../data/security';
import { Card } from '../../ui/Card';
import { Badge } from '../../ui/Badge';
import { Toggle } from '../../ui/Toggle';
import { Checkbox } from '../../ui/Checkbox';

const STANDARDS = [
  { id: 'gdpr', name: 'GDPR', description: 'EU General Data Protection Regulation' },
  { id: 'hipaa', name: 'HIPAA', description: 'Health Insurance Portability and Accountability Act' },
  { id: 'pci-dss', name: 'PCI-DSS', description: 'Payment Card Industry Data Security Standard' },
  { id: 'soc2', name: 'SOC 2', description: 'Service Organization Control 2' },
] as const;

export function CompliancePanel() {
  const { state, setComplianceConfig } = useWizard();
  const [expandedStandard, setExpandedStandard] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-text-primary">Compliance Standards</h4>

      {STANDARDS.map((std) => {
        const cfg = state.complianceConfig[std.id] ?? { enabled: false, acknowledgedRules: [] };
        const rules = COMPLIANCE_RULES[std.id] ?? [];
        const isExpanded = expandedStandard === std.id;
        const acked = cfg.acknowledgedRules.length;
        const total = rules.length;

        return (
          <Card key={std.id} className="space-y-3">
            {/* Standard Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Toggle
                  enabled={cfg.enabled}
                  onChange={(val) => {
                    setComplianceConfig(std.id, {
                      enabled: val,
                      acknowledgedRules: val ? rules.map((r) => r.id) : [],
                    });
                    if (val) setExpandedStandard(std.id);
                    else if (expandedStandard === std.id) setExpandedStandard(null);
                  }}
                />
                <div>
                  <p className="text-sm font-medium text-text-primary">{std.name}</p>
                  <p className="text-xs text-text-muted">{std.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {cfg.enabled && (
                  <Badge variant={acked === total ? 'success' : 'warning'}>
                    {acked}/{total} rules
                  </Badge>
                )}
                {cfg.enabled && (
                  <button
                    type="button"
                    onClick={() => setExpandedStandard(isExpanded ? null : std.id)}
                    className="text-text-muted hover:text-text-primary cursor-pointer"
                  >
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                )}
              </div>
            </div>

            {/* Rule Checklist */}
            {cfg.enabled && isExpanded && rules.length > 0 && (
              <div className="border-t border-border-base pt-3 space-y-2">
                {rules.map((rule) => {
                  const isAcked = cfg.acknowledgedRules.includes(rule.id);
                  return (
                    <Checkbox
                      key={rule.id}
                      checked={isAcked}
                      onChange={() => {
                        const next = isAcked
                          ? cfg.acknowledgedRules.filter((r) => r !== rule.id)
                          : [...cfg.acknowledgedRules, rule.id];
                        setComplianceConfig(std.id, { acknowledgedRules: next });
                      }}
                      label={rule.id.toUpperCase()}
                      description={rule.description}
                    />
                  );
                })}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}
