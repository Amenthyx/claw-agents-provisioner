import { useEffect, useState, useCallback } from 'react';
import {
  Server, Plus, Trash2, RefreshCw, Activity, AlertTriangle,
  CheckCircle2, XCircle, Cpu, Share2, Shield, MessageSquare, Database,
} from 'lucide-react';
import { api } from '../../lib/api';
import { Card, StatCard } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Input } from '../ui/Input';

interface AgentPort { [id: string]: number }

interface Instance {
  id: string;
  name: string;
  host: string;
  wizard_port: number;
  watchdog_port: number;
  agent_ports: AgentPort;
  is_self?: boolean;
}

interface InstanceHealth {
  id: string;
  status: string;
  wizard: boolean;
  watchdog: boolean;
  agents_running: number;
  agents_total: number;
  agents: { id: string; port: number; status: string }[];
}

interface SharedResources {
  ollama: { host: string; port: number; shared: boolean; note?: string };
  api_keys: { shared: boolean; source: string; note?: string };
}

interface InstancesData {
  instances: Instance[];
  shared_resources?: SharedResources;
}

interface ClawConfig {
  id: string;
  name: string;
  platform: string;
  port: number;
  llm_provider: string;
  created_at: string;
}

const PLATFORMS = [
  { id: 'zeroclaw', name: 'ZeroClaw', language: 'Rust', port: 3100 },
  { id: 'nanoclaw', name: 'NanoClaw', language: 'TypeScript', port: 3200 },
  { id: 'picoclaw', name: 'PicoClaw', language: 'Go', port: 3300 },
  { id: 'openclaw', name: 'OpenClaw', language: 'Node.js', port: 3400 },
  { id: 'parlant', name: 'Parlant', language: 'Python', port: 8800 },
];

export function InstancesPage() {
  const [data, setData] = useState<InstancesData | null>(null);
  const [claws, setClaws] = useState<ClawConfig[]>([]);
  const [healthMap, setHealthMap] = useState<Record<string, InstanceHealth>>({});
  const [loading, setLoading] = useState(true);
  const [showAddInstance, setShowAddInstance] = useState(false);
  const [showCreateClaw, setShowCreateClaw] = useState(false);
  const [checking, setChecking] = useState<string | null>(null);

  // Instance form
  const [instName, setInstName] = useState('');
  const [instHost, setInstHost] = useState('');
  const [instWizPort, setInstWizPort] = useState('9098');
  const [instWdPort, setInstWdPort] = useState('9097');

  // Claw form
  const [clawName, setClawName] = useState('');
  const [clawPlatform, setClawPlatform] = useState('zeroclaw');
  const [clawProvider, setClawProvider] = useState('hybrid');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [instData, clawData] = await Promise.all([
        api.dashboard.getInstances(),
        api.dashboard.getClaws(),
      ]);
      setData(instData);
      setClaws(clawData.claws ?? []);
    } catch {
      setData({
        instances: [{
          id: 'inst_local', name: 'Local Dev', host: 'localhost',
          wizard_port: 9098, watchdog_port: 9097,
          agent_ports: { zeroclaw: 3100, nanoclaw: 3200, picoclaw: 3300, openclaw: 3400, parlant: 8800 },
          is_self: true,
        }],
      });
      setClaws([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const iv = setInterval(fetchData, 30000);
    return () => clearInterval(iv);
  }, [fetchData]);

  const checkInstance = async (inst: Instance) => {
    setChecking(inst.id);
    try {
      const health = await api.dashboard.getInstanceStatus(inst.id);
      setHealthMap((prev) => ({ ...prev, [inst.id]: health }));
    } catch { /* ignore */ }
    setChecking(null);
  };

  const handleAddInstance = async () => {
    if (!data || !instName.trim() || !instHost.trim()) return;
    const newInst: Instance = {
      id: `inst_${Date.now()}`,
      name: instName,
      host: instHost,
      wizard_port: parseInt(instWizPort) || 9098,
      watchdog_port: parseInt(instWdPort) || 9097,
      agent_ports: Object.fromEntries(PLATFORMS.map((p) => [p.id, p.port])),
    };
    const updated = { ...data, instances: [...data.instances, newInst] };
    await api.dashboard.saveInstance(updated);
    setShowAddInstance(false);
    setInstName('');
    setInstHost('');
    fetchData();
  };

  const handleDeleteInstance = async (id: string) => {
    await api.dashboard.deleteInstance(id);
    fetchData();
  };

  const handleCreateClaw = async () => {
    if (!clawName.trim()) return;
    const plat = PLATFORMS.find((p) => p.id === clawPlatform);
    await api.dashboard.createClaw({
      name: clawName,
      platform: clawPlatform,
      port: plat?.port ?? 3100,
      llm_provider: clawProvider,
    });
    setShowCreateClaw(false);
    setClawName('');
    fetchData();
  };

  const instances = data?.instances ?? [];
  const shared = data?.shared_resources;
  const healthy = Object.values(healthMap).filter((h) => h.status === 'healthy').length;
  const degraded = Object.values(healthMap).filter((h) => h.status === 'degraded' || h.status === 'partial').length;
  const unreachable = Object.values(healthMap).filter((h) => h.status === 'unreachable').length;

  const statusIcon = (s: string) => {
    if (s === 'healthy') return <CheckCircle2 size={14} className="text-success" />;
    if (s === 'degraded' || s === 'partial') return <AlertTriangle size={14} className="text-warning" />;
    return <XCircle size={14} className="text-error" />;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Cluster Management</h1>
          <p className="text-sm text-text-secondary mt-1">
            Multi-instance fleet with shared resources
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchData} loading={loading} icon={<RefreshCw size={14} />}>
            Refresh
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setShowCreateClaw(true)} icon={<Plus size={14} />}>
            New Claw
          </Button>
          <Button size="sm" onClick={() => setShowAddInstance(true)} icon={<Server size={14} />}>
            Add Instance
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard icon={<Server size={16} />} label="Instances" value={String(instances.length)} />
        <StatCard icon={<CheckCircle2 size={16} />} label="Healthy" value={String(healthy)} />
        <StatCard icon={<AlertTriangle size={16} />} label="Degraded" value={String(degraded)} />
        <StatCard icon={<XCircle size={16} />} label="Unreachable" value={String(unreachable)} />
      </div>

      {/* Shared Resources */}
      {shared && (
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Share2 size={16} className="text-accent" />
            <h3 className="text-sm font-medium text-text-primary">Shared Resources</h3>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-border-base bg-surface-0 px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <Cpu size={14} className="text-text-muted" />
                <span className="text-sm font-medium text-text-primary">Ollama Runtime</span>
                <Badge variant={shared.ollama?.shared ? 'success' : 'default'}>
                  {shared.ollama?.shared ? 'Shared' : 'Per-instance'}
                </Badge>
              </div>
              <p className="text-xs text-text-muted">
                {shared.ollama?.host}:{shared.ollama?.port} — Single Ollama for all claws
              </p>
            </div>
            <div className="rounded-lg border border-border-base bg-surface-0 px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <Activity size={14} className="text-text-muted" />
                <span className="text-sm font-medium text-text-primary">API Keys</span>
                <Badge variant={shared.api_keys?.shared ? 'success' : 'default'}>
                  {shared.api_keys?.shared ? 'Shared' : 'Per-instance'}
                </Badge>
              </div>
              <p className="text-xs text-text-muted">
                Source: {shared.api_keys?.source} — Cloud provider keys shared across agents
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Cluster Configuration */}
      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-4">Cluster Configuration</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-lg border border-border-base bg-surface-0 p-4 space-y-2">
            <div className="flex items-center gap-2 mb-2">
              <Shield size={14} className="text-accent" />
              <span className="text-sm font-medium text-text-primary">Security</span>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Shared security rules</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">PII detection</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">TLS inter-node</span>
                <Badge variant="default">Off</Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Secret masking</span>
                <Badge variant="success">Active</Badge>
              </div>
            </div>
            <p className="text-[10px] text-text-muted pt-1">Security rules from security_rules.json apply to all claws</p>
          </div>

          <div className="rounded-lg border border-border-base bg-surface-0 p-4 space-y-2">
            <div className="flex items-center gap-2 mb-2">
              <MessageSquare size={14} className="text-accent" />
              <span className="text-sm font-medium text-text-primary">Communication</span>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Shared channels</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Fallback chain</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Alert routing</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Cross-claw alerts</span>
                <Badge variant="default">Off</Badge>
              </div>
            </div>
            <p className="text-[10px] text-text-muted pt-1">Channel config shared from channel_config.json</p>
          </div>

          <div className="rounded-lg border border-border-base bg-surface-0 p-4 space-y-2">
            <div className="flex items-center gap-2 mb-2">
              <Database size={14} className="text-accent" />
              <span className="text-sm font-medium text-text-primary">Data Sharing</span>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Shared Ollama models</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Shared API keys</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Cost tracking (unified)</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Shared context store</span>
                <Badge variant="default">Off</Badge>
              </div>
            </div>
            <p className="text-[10px] text-text-muted pt-1">Single .env for API keys, single Ollama for all models</p>
          </div>
        </div>
      </Card>

      {/* Create Claw Form */}
      {showCreateClaw && (
        <Card className="space-y-4 border-accent/20">
          <h3 className="text-sm font-medium text-text-primary">Deploy New Claw Agent</h3>
          <Input
            label="Claw Name"
            placeholder="e.g. my-support-bot"
            value={clawName}
            onChange={(e) => setClawName(e.target.value)}
          />
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-2">Platform</label>
            <div className="grid grid-cols-5 gap-2">
              {PLATFORMS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setClawPlatform(p.id)}
                  className={`rounded-lg border px-3 py-2 text-center text-xs transition-colors ${
                    clawPlatform === p.id
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border-base bg-surface-1 text-text-secondary hover:bg-surface-2'
                  }`}
                >
                  <div className="font-medium">{p.name}</div>
                  <div className="text-text-muted mt-0.5">{p.language}</div>
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-2">LLM Provider</label>
            <div className="flex gap-2">
              {['local', 'cloud', 'hybrid'].map((prov) => (
                <button
                  key={prov}
                  onClick={() => setClawProvider(prov)}
                  className={`rounded-lg border px-4 py-2 text-xs transition-colors ${
                    clawProvider === prov
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border-base bg-surface-1 text-text-secondary hover:bg-surface-2'
                  }`}
                >
                  {prov.charAt(0).toUpperCase() + prov.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleCreateClaw}>Deploy Claw</Button>
            <Button variant="ghost" size="sm" onClick={() => setShowCreateClaw(false)}>Cancel</Button>
          </div>
        </Card>
      )}

      {/* Add Instance Form */}
      {showAddInstance && (
        <Card className="space-y-4">
          <h3 className="text-sm font-medium text-text-primary">Add Remote Instance</h3>
          <div className="grid grid-cols-2 gap-4">
            <Input label="Name" placeholder="Production Server" value={instName} onChange={(e) => setInstName(e.target.value)} />
            <Input label="Host" placeholder="192.168.1.100" value={instHost} onChange={(e) => setInstHost(e.target.value)} />
            <Input label="Wizard Port" placeholder="9098" value={instWizPort} onChange={(e) => setInstWizPort(e.target.value)} />
            <Input label="Watchdog Port" placeholder="9097" value={instWdPort} onChange={(e) => setInstWdPort(e.target.value)} />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleAddInstance}>Add Instance</Button>
            <Button variant="ghost" size="sm" onClick={() => setShowAddInstance(false)}>Cancel</Button>
          </div>
        </Card>
      )}

      {/* Deployed Claws */}
      {claws.length > 0 && (
        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-3">Deployed Claws</h3>
          <div className="space-y-2">
            {claws.map((claw) => (
              <div
                key={claw.id}
                className="flex items-center justify-between rounded-lg border border-border-base bg-surface-0 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <div className="h-2 w-2 rounded-full bg-success" />
                  <div>
                    <p className="text-sm font-medium text-text-primary">{claw.name}</p>
                    <p className="text-xs text-text-muted">
                      {claw.platform} · Port {claw.port} · {claw.llm_provider} · Created {new Date(claw.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <Badge variant="accent">{claw.platform}</Badge>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Instance Grid */}
      <div className="grid grid-cols-2 gap-4">
        {instances.map((inst) => {
          const health = healthMap[inst.id];
          return (
            <Card key={inst.id}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {health ? statusIcon(health.status) : <Server size={14} className="text-text-muted" />}
                  <h3 className="text-sm font-medium text-text-primary">{inst.name}</h3>
                  {inst.is_self && <Badge variant="accent">Self</Badge>}
                  {health && (
                    <Badge variant={health.status === 'healthy' ? 'success' : health.status === 'unreachable' ? 'error' : 'warning'}>
                      {health.status}
                    </Badge>
                  )}
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => checkInstance(inst)}
                    loading={checking === inst.id}
                    icon={<RefreshCw size={12} />}
                  />
                  {!inst.is_self && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteInstance(inst.id)}
                      icon={<Trash2 size={12} />}
                    />
                  )}
                </div>
              </div>
              <p className="text-xs text-text-muted mb-2">
                {inst.host}:{inst.wizard_port} · Watchdog :{inst.watchdog_port}
              </p>
              {health && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {health.agents.map((a) => (
                    <Badge
                      key={a.id}
                      variant={a.status === 'running' ? 'success' : 'default'}
                    >
                      {a.id}:{a.port}
                    </Badge>
                  ))}
                </div>
              )}
              {!health && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {Object.entries(inst.agent_ports).map(([aid, aport]) => (
                    <Badge key={aid} variant="default">{aid}:{aport}</Badge>
                  ))}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {/* Architecture Diagram */}
      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-4">System Architecture</h3>
        <div className="rounded-lg border border-border-base bg-surface-0 p-6 font-mono text-xs leading-relaxed text-text-secondary overflow-x-auto">
          <pre>{`
  ┌─────────────────────────────────────────────────────────────────────┐
  │                        XClaw Cluster                              │
  │                                                                     │
  │  ┌──────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
  │  │  Client   │───▸│  Security    │───▸│  Gateway Router (:9095) │  │
  │  │  Request  │    │  Gate (in)   │    │  - Task auto-detect     │  │
  │  └──────────┘    └──────────────┘    │  - Model routing        │  │
  │                                       └──────────┬───────────────┘  │
  │                                                    │                  │
  │                            ┌────────────────────────┤                  │
  │                            ▼                        ▼                  │
  │               ┌──────────────────┐    ┌──────────────────────┐      │
  │               │  Optimizer       │    │  Shared Ollama       │      │
  │               │  (:9091)         │    │  (:11434)            │      │
  │               │  - 14 rules      │    │  - Local models      │      │
  │               │  - Cost tracking │    │  - Shared by all     │      │
  │               │  - Caching       │    │    claw agents       │      │
  │               └────────┬─────────┘    └──────────────────────┘      │
  │                        │                                             │
  │    ┌───────────────────┼───────────────────────────────┐            │
  │    │                   │         Agent Fleet           │            │
  │    │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  │            │
  │    │  │Zero    │  │Nano    │  │Pico    │  │Open    │  │            │
  │    │  │Claw    │  │Claw    │  │Claw    │  │Claw    │  │            │
  │    │  │:3100   │  │:3200   │  │:3300   │  │:3400   │  │            │
  │    │  │Rust    │  │TS      │  │Go      │  │Node    │  │            │
  │    │  └────────┘  └────────┘  └────────┘  └────────┘  │            │
  │    │              ┌────────┐                           │            │
  │    │              │Parlant │                           │            │
  │    │              │:8800   │                           │            │
  │    │              │Python  │                           │            │
  │    │              └────────┘                           │            │
  │    └───────────────────────────────────────────────────┘            │
  │                        │                                             │
  │               ┌────────┴─────────┐    ┌──────────────────────┐      │
  │               │  Security Gate   │    │  Watchdog (:9097)    │      │
  │               │  (outbound)      │    │  - Health checks     │      │
  │               │  - PII redact    │    │  - Auto-restart      │      │
  │               │  - Secret mask   │    │  - Metrics           │      │
  │               └──────────────────┘    └──────────────────────┘      │
  │                                                                     │
  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐   │
  │  │ Wizard API   │   │ Dashboard    │   │ Cloud APIs           │   │
  │  │ (:9098)      │   │ (:3000)      │   │ Anthropic/OpenAI/    │   │
  │  │ Config +     │   │ React UI     │   │ DeepSeek (shared     │   │
  │  │ Deploy       │   │ Monitoring   │   │ API keys from .env)  │   │
  │  └──────────────┘   └──────────────┘   └──────────────────────┘   │
  └─────────────────────────────────────────────────────────────────────┘
          `}</pre>
        </div>
      </Card>
    </div>
  );
}
