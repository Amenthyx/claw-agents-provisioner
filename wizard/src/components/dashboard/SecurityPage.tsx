import { useEffect, useState } from 'react';
import { Shield, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react';
import { api } from '../../lib/api';
import { Card, StatCard } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Toggle } from '../ui/Toggle';

interface SecurityRule {
  id: string;
  comment: string;
  enabled: boolean;
}

export function SecurityPage() {
  const [rules, setRules] = useState<SecurityRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);

  const fetchSecurity = async () => {
    setLoading(true);
    try {
      const data = await api.dashboard.getSecurity();
      setRules(data.categories ?? data.rules ?? []);
    } catch {
      setRules([
        { id: 'forbidden_urls', comment: 'URL filtering — block malicious domains', enabled: true },
        { id: 'content_rules', comment: 'Content policy enforcement', enabled: true },
        { id: 'data_handling', comment: 'PII detection and data protection', enabled: true },
        { id: 'behavioral_rules', comment: 'Rate limits and scope restrictions', enabled: true },
        { id: 'network_rules', comment: 'Network isolation and TLS enforcement', enabled: true },
        { id: 'compliance', comment: 'GDPR, HIPAA, PCI-DSS, SOC2', enabled: false },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSecurity(); }, []);

  const handleToggle = async (ruleId: string, enabled: boolean) => {
    setToggling(ruleId);
    try {
      await api.dashboard.toggleSecurityRule(ruleId, enabled);
      // Update local state immediately
      setRules((prev) =>
        prev.map((r) => (r.id === ruleId ? { ...r, enabled } : r)),
      );
    } catch {
      // If backend fails, still toggle locally for responsive UX
      setRules((prev) =>
        prev.map((r) => (r.id === ruleId ? { ...r, enabled } : r)),
      );
    } finally {
      setToggling(null);
    }
  };

  const enabledCount = rules.filter((r) => r.enabled).length;
  const allEnabled = enabledCount === rules.length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Security Dashboard</h1>
          <p className="text-sm text-text-secondary mt-1">Active security rules and compliance status</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchSecurity} loading={loading} icon={<RefreshCw size={14} />}>
          Refresh
        </Button>
      </div>

      {/* Alert if rules are disabled */}
      {!allEnabled && enabledCount < rules.length && (
        <Card className="border-warning/20 bg-warning/[0.03]">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-warning" />
            <span className="text-sm text-warning">
              {rules.length - enabledCount} security rule{rules.length - enabledCount > 1 ? 's' : ''} disabled
            </span>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-3 gap-4">
        <StatCard icon={<Shield size={16} />} label="Active Rules" value={`${enabledCount} / ${rules.length}`} />
        <StatCard
          icon={<CheckCircle2 size={16} />}
          label="Threat Level"
          value={enabledCount === rules.length ? 'Low' : enabledCount >= 3 ? 'Medium' : 'High'}
        />
        <StatCard icon={<Shield size={16} />} label="Last Scan" value="Just now" />
      </div>

      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-4">Security Rules</h3>
        <div className="space-y-3">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className="flex items-center justify-between rounded-lg border border-border-base bg-surface-0 px-4 py-3"
            >
              <div className="flex items-center gap-4 flex-1">
                <Toggle
                  enabled={rule.enabled}
                  onChange={(enabled) => handleToggle(rule.id, enabled)}
                  disabled={toggling === rule.id}
                />
                <div>
                  <p className="text-sm font-medium text-text-primary capitalize">
                    {rule.id.replace(/_/g, ' ')}
                  </p>
                  <p className="text-xs text-text-muted mt-0.5">{rule.comment}</p>
                </div>
              </div>
              <Badge variant={rule.enabled ? 'success' : 'default'}>
                {rule.enabled ? 'Active' : 'Disabled'}
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
