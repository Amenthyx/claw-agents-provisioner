import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { useWizard } from '../../../state/context';
import { DEFAULT_FORBIDDEN_IP_RANGES, DEFAULT_ALLOWED_API_HOSTS } from '../../../data/security';
import { Card } from '../../ui/Card';
import { Input } from '../../ui/Input';
import { Button } from '../../ui/Button';
import { Badge } from '../../ui/Badge';
import { Toggle } from '../../ui/Toggle';
import { SelectionCard } from '../../ui/Card';

export function NetworkRulesPanel() {
  const { state, setSecurityConfig } = useWizard();
  const cfg = state.securityConfig.networkRules;
  const [newPort, setNewPort] = useState('');
  const [newIpRange, setNewIpRange] = useState('');
  const [newHost, setNewHost] = useState('');

  const addPort = () => {
    const port = parseInt(newPort);
    if (!isNaN(port) && port > 0 && port <= 65535 && !cfg.allowedPorts.includes(port)) {
      setSecurityConfig({
        networkRules: { ...cfg, allowedPorts: [...cfg.allowedPorts, port] },
      });
      setNewPort('');
    }
  };

  const removePort = (port: number) => {
    setSecurityConfig({
      networkRules: { ...cfg, allowedPorts: cfg.allowedPorts.filter((p) => p !== port) },
    });
  };

  const addIpRange = () => {
    const trimmed = newIpRange.trim();
    if (trimmed && !cfg.forbiddenIpRanges.includes(trimmed)) {
      setSecurityConfig({
        networkRules: { ...cfg, forbiddenIpRanges: [...cfg.forbiddenIpRanges, trimmed] },
      });
      setNewIpRange('');
    }
  };

  const removeIpRange = (range: string) => {
    setSecurityConfig({
      networkRules: { ...cfg, forbiddenIpRanges: cfg.forbiddenIpRanges.filter((r) => r !== range) },
    });
  };

  const seedIpRanges = () => {
    const merged = [...new Set([...cfg.forbiddenIpRanges, ...DEFAULT_FORBIDDEN_IP_RANGES])];
    setSecurityConfig({
      networkRules: { ...cfg, forbiddenIpRanges: merged },
    });
  };

  const addHost = () => {
    const trimmed = newHost.trim();
    if (trimmed && !cfg.allowedApiHosts.includes(trimmed)) {
      setSecurityConfig({
        networkRules: { ...cfg, allowedApiHosts: [...cfg.allowedApiHosts, trimmed] },
      });
      setNewHost('');
    }
  };

  const removeHost = (host: string) => {
    setSecurityConfig({
      networkRules: { ...cfg, allowedApiHosts: cfg.allowedApiHosts.filter((h) => h !== host) },
    });
  };

  const seedHosts = () => {
    const merged = [...new Set([...cfg.allowedApiHosts, ...DEFAULT_ALLOWED_API_HOSTS])];
    setSecurityConfig({
      networkRules: { ...cfg, allowedApiHosts: merged },
    });
  };

  return (
    <Card className="space-y-4">
      <h4 className="text-sm font-medium text-text-primary">Network Rules</h4>

      {/* Allowed Outbound Ports */}
      <div className="space-y-2">
        <label className="block text-xs font-medium text-text-secondary">Allowed Outbound Ports</label>
        <div className="flex gap-2">
          <Input
            type="number"
            placeholder="8443"
            value={newPort}
            onChange={(e) => setNewPort(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addPort()}
            className="w-28"
          />
          <Button size="sm" onClick={addPort} icon={<Plus size={14} />}>
            Add
          </Button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {cfg.allowedPorts.map((p) => (
            <Badge key={p} variant="default">
              {p}
              <button type="button" onClick={() => removePort(p)} className="ml-1 cursor-pointer">
                <X size={10} />
              </button>
            </Badge>
          ))}
        </div>
      </div>

      {/* Forbidden IP Ranges */}
      <div className="space-y-2">
        <label className="block text-xs font-medium text-text-secondary">Forbidden IP Ranges</label>
        <div className="flex gap-2">
          <Input
            placeholder="10.0.0.0/8"
            value={newIpRange}
            onChange={(e) => setNewIpRange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addIpRange()}
            className="flex-1 font-mono"
          />
          <Button size="sm" onClick={addIpRange} icon={<Plus size={14} />}>
            Add
          </Button>
        </div>
        {cfg.forbiddenIpRanges.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {cfg.forbiddenIpRanges.map((r) => (
              <Badge key={r} variant="error">
                <span className="font-mono text-xs">{r}</span>
                <button type="button" onClick={() => removeIpRange(r)} className="ml-1 cursor-pointer">
                  <X size={10} />
                </button>
              </Badge>
            ))}
          </div>
        ) : (
          <Button variant="ghost" size="sm" onClick={seedIpRanges}>
            Load default forbidden ranges
          </Button>
        )}
      </div>

      {/* Allowed API Hosts */}
      <div className="space-y-2">
        <label className="block text-xs font-medium text-text-secondary">Allowed API Hosts</label>
        <div className="flex gap-2">
          <Input
            placeholder="api.example.com"
            value={newHost}
            onChange={(e) => setNewHost(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addHost()}
            className="flex-1"
          />
          <Button size="sm" onClick={addHost} icon={<Plus size={14} />}>
            Add
          </Button>
        </div>
        {cfg.allowedApiHosts.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {cfg.allowedApiHosts.map((h) => (
              <Badge key={h} variant="success">
                {h}
                <button type="button" onClick={() => removeHost(h)} className="ml-1 cursor-pointer">
                  <X size={10} />
                </button>
              </Badge>
            ))}
          </div>
        ) : (
          <Button variant="ghost" size="sm" onClick={seedHosts}>
            Load default API hosts
          </Button>
        )}
      </div>

      {/* TLS Settings */}
      <div className="flex items-center justify-between">
        <Toggle
          enabled={cfg.requireTls}
          onChange={(val) =>
            setSecurityConfig({ networkRules: { ...cfg, requireTls: val } })
          }
          label="Require TLS"
          description="Enforce encrypted connections for all outbound traffic"
        />
      </div>

      {cfg.requireTls && (
        <div className="space-y-2">
          <label className="block text-xs font-medium text-text-secondary">Minimum TLS Version</label>
          <div className="grid grid-cols-2 gap-2">
            {(['1.2', '1.3'] as const).map((ver) => (
              <SelectionCard
                key={ver}
                selected={cfg.tlsMinVersion === ver}
                onClick={() =>
                  setSecurityConfig({ networkRules: { ...cfg, tlsMinVersion: ver } })
                }
                className="py-2 px-3 text-center"
              >
                <p className="text-sm font-medium text-text-primary">TLS {ver}</p>
              </SelectionCard>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
