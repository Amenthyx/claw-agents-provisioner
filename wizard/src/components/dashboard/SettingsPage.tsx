import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api } from '../../lib/api';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';

interface ConfigEntry {
  key: string;
  value: string;
  redacted: boolean;
}

export function SettingsPage() {
  const [config, setConfig] = useState<ConfigEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const data = await api.dashboard.getConfig();
      const entries: ConfigEntry[] = [];
      for (const [key, value] of Object.entries(data.config ?? data)) {
        const isSecret = /key|token|secret|password/i.test(key);
        entries.push({
          key,
          value: isSecret ? '••••••••' : String(value),
          redacted: isSecret,
        });
      }
      setConfig(entries);
    } catch {
      setConfig([
        { key: 'WIZARD_API_PORT', value: '9098', redacted: false },
        { key: 'DASHBOARD_PORT', value: '9099', redacted: false },
        { key: 'GATEWAY_PORT', value: '9095', redacted: false },
        { key: 'DEFAULT_PLATFORM', value: 'nanoclaw', redacted: false },
        { key: 'ANTHROPIC_API_KEY', value: '••••••••', redacted: true },
        { key: 'OPENAI_API_KEY', value: '••••••••', redacted: true },
        { key: 'LOG_LEVEL', value: 'info', redacted: false },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchConfig(); }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Settings</h1>
          <p className="text-sm text-text-secondary mt-1">Read-only configuration display</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchConfig} loading={loading} icon={<RefreshCw size={14} />}>
          Refresh
        </Button>
      </div>

      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-4">Environment Configuration</h3>
        <div className="space-y-0 divide-y divide-border-subtle">
          {config.map((entry) => (
            <div key={entry.key} className="flex items-center justify-between py-3">
              <span className="text-sm font-mono text-text-secondary">{entry.key}</span>
              <span className={`text-sm font-mono ${entry.redacted ? 'text-text-muted' : 'text-text-primary'}`}>
                {entry.value}
              </span>
            </div>
          ))}
        </div>
      </Card>

      <Card className="border-warning/20 bg-warning/[0.03]">
        <p className="text-sm text-warning">
          Settings are read-only. To modify configuration, edit the <code className="font-mono">.env</code> file
          and restart the services.
        </p>
      </Card>
    </div>
  );
}
