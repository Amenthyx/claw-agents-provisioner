import { useEffect, useState, useCallback } from 'react';
import {
  Activity, Bot, RefreshCw, AlertTriangle,
  DollarSign, Bell, Server, Play, Square, Zap, CheckCircle2,
} from 'lucide-react';
import { api } from '../../lib/api';
import { Card, StatCard } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Progress } from '../ui/Progress';

interface AgentInfo {
  id: string;
  name: string;
  status: string;
  port: number;
  language: string;
  memory?: string;
  features?: string[];
}

interface Metrics {
  agents_total: number;
  agents_running: number;
  agents: AgentInfo[];
  cost_today: number;
  total_requests: number;
  active_triggers: number;
  total_triggers: number;
  instances_total: number;
  services: Record<string, boolean>;
  watchdog?: Record<string, unknown> | null;
}

export function OverviewPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.dashboard.getMetrics();
      setMetrics(data);
    } catch {
      setError('Dashboard backend unavailable — ensure wizard API is running on port 9098.');
      setMetrics({
        agents_total: 5, agents_running: 0,
        agents: [
          { id: 'zeroclaw', name: 'ZeroClaw', status: 'stopped', port: 3100, language: 'Rust', memory: '512 MB' },
          { id: 'nanoclaw', name: 'NanoClaw', status: 'stopped', port: 3200, language: 'TypeScript', memory: '1 GB' },
          { id: 'picoclaw', name: 'PicoClaw', status: 'stopped', port: 3300, language: 'Go', memory: '128 MB' },
          { id: 'openclaw', name: 'OpenClaw', status: 'stopped', port: 3400, language: 'Node.js', memory: '4 GB' },
          { id: 'parlant', name: 'Parlant', status: 'stopped', port: 8800, language: 'Python', memory: '2 GB' },
        ],
        cost_today: 0, total_requests: 0,
        active_triggers: 0, total_triggers: 0,
        instances_total: 1,
        services: { gateway: false, optimizer: false, watchdog: false, wizard: true, ollama: false },
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const iv = setInterval(fetchData, 10000);
    return () => clearInterval(iv);
  }, [fetchData]);

  const handleHealthCheckAll = async () => {
    setActionLoading('health');
    await fetchData();
    setActionLoading(null);
  };

  const handleRestartAll = async () => {
    setActionLoading('restart');
    const agents = metrics?.agents ?? [];
    for (const agent of agents) {
      try {
        await api.dashboard.agentAction(agent.id, 'restart');
      } catch { /* continue */ }
    }
    await fetchData();
    setActionLoading(null);
  };

  if (!metrics) {
    return <div className="flex items-center justify-center h-64 text-text-muted">Loading...</div>;
  }

  const agents = metrics.agents ?? [];
  const unhealthy = agents.filter((a) => a.status !== 'running');
  const services = metrics.services ?? {};
  const serviceCount = Object.values(services).filter(Boolean).length;
  const totalServices = Object.keys(services).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Dashboard Overview</h1>
          <p className="text-sm text-text-secondary mt-1">Monitor your XClaw agent fleet in real-time</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleHealthCheckAll} loading={actionLoading === 'health'} icon={<CheckCircle2 size={14} />}>
            Health Check All
          </Button>
          <Button variant="secondary" size="sm" onClick={handleRestartAll} loading={actionLoading === 'restart'} icon={<RefreshCw size={14} />}>
            Restart All
          </Button>
          <Button variant="outline" size="sm" onClick={fetchData} loading={loading} icon={<RefreshCw size={14} />}>
            Refresh
          </Button>
        </div>
      </div>

      {/* Alerts Banner */}
      {(error || unhealthy.length > 0) && (
        <Card className="border-warning/20 bg-warning/[0.03]">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-warning" />
            <span className="text-sm font-medium text-warning">
              {error
                ? error
                : `${unhealthy.length} agent${unhealthy.length > 1 ? 's' : ''} not running: ${unhealthy.map((a) => a.name).join(', ')}`}
            </span>
          </div>
        </Card>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-6 gap-3">
        <StatCard icon={<Bot size={16} />} label="Total Agents" value={String(metrics.agents_total)} />
        <StatCard icon={<Activity size={16} />} label="Running" value={String(metrics.agents_running)} />
        <StatCard icon={<DollarSign size={16} />} label="Cost Today" value={`$${metrics.cost_today.toFixed(2)}`} />
        <StatCard icon={<Zap size={16} />} label="Requests" value={String(metrics.total_requests)} />
        <StatCard icon={<Bell size={16} />} label="Triggers" value={`${metrics.active_triggers}/${metrics.total_triggers}`} />
        <StatCard icon={<Server size={16} />} label="Instances" value={String(metrics.instances_total)} />
      </div>

      {/* Services Health + Agent Fleet */}
      <div className="grid grid-cols-3 gap-4">
        {/* Services */}
        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-3">Services</h3>
          <div className="space-y-2">
            {Object.entries(services).map(([svc, alive]) => (
              <div key={svc} className="flex items-center justify-between">
                <span className="text-xs text-text-secondary capitalize">{svc}</span>
                <div className="flex items-center gap-1.5">
                  <div className={`h-1.5 w-1.5 rounded-full ${alive ? 'bg-success' : 'bg-text-muted'}`} />
                  <span className={`text-xs ${alive ? 'text-success' : 'text-text-muted'}`}>
                    {alive ? 'Up' : 'Down'}
                  </span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-3 border-t border-border-subtle">
            <div className="flex items-center justify-between text-xs text-text-muted mb-1">
              <span>Uptime</span>
              <span>{serviceCount}/{totalServices}</span>
            </div>
            <Progress value={serviceCount} max={totalServices} size="sm" />
          </div>
        </Card>

        {/* Agent Fleet */}
        <div className="col-span-2">
          <Card>
            <h3 className="text-sm font-medium text-text-primary mb-3">Agent Fleet</h3>
            <div className="space-y-2">
              {agents.map((agent) => (
                <div
                  key={agent.id}
                  className="flex items-center justify-between rounded-lg border border-border-base bg-surface-0 px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <div className={`h-2 w-2 rounded-full ${agent.status === 'running' ? 'bg-success' : 'bg-text-muted'}`} />
                    <div>
                      <p className="text-sm font-medium text-text-primary">{agent.name}</p>
                      <p className="text-xs text-text-muted">
                        {agent.language} · :{agent.port} {agent.memory ? `· ${agent.memory}` : ''}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={agent.status === 'running' ? 'success' : 'default'}>
                      {agent.status}
                    </Badge>
                    {agent.status !== 'running' ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={async () => {
                          try { await api.dashboard.agentAction(agent.id, 'start'); } catch {}
                          fetchData();
                        }}
                        icon={<Play size={12} />}
                      />
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={async () => {
                          try { await api.dashboard.agentAction(agent.id, 'stop'); } catch {}
                          fetchData();
                        }}
                        icon={<Square size={12} />}
                      />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* Request Stats / Mini Charts */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-3">Fleet Utilization</h3>
          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                <span>Agents Online</span>
                <span>{metrics.agents_running}/{metrics.agents_total}</span>
              </div>
              <Progress value={metrics.agents_running} max={Math.max(metrics.agents_total, 1)} size="md" />
            </div>
            <div>
              <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                <span>Services Healthy</span>
                <span>{serviceCount}/{totalServices}</span>
              </div>
              <Progress value={serviceCount} max={totalServices} size="md" />
            </div>
            <div>
              <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                <span>Active Triggers</span>
                <span>{metrics.active_triggers}/{Math.max(metrics.total_triggers, 1)}</span>
              </div>
              <Progress value={metrics.active_triggers} max={Math.max(metrics.total_triggers, 1)} size="md" />
            </div>
          </div>
        </Card>

        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-3">Cost & Usage</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-border-base bg-surface-0 px-4 py-3 text-center">
              <p className="text-2xl font-semibold text-text-primary">${metrics.cost_today.toFixed(2)}</p>
              <p className="text-xs text-text-muted mt-1">Cost Today</p>
            </div>
            <div className="rounded-lg border border-border-base bg-surface-0 px-4 py-3 text-center">
              <p className="text-2xl font-semibold text-text-primary">{metrics.total_requests}</p>
              <p className="text-xs text-text-muted mt-1">Total Requests</p>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-border-subtle">
            <div className="grid grid-cols-5 gap-1">
              {agents.map((agent) => (
                <div key={agent.id} className="text-center">
                  <div
                    className={`mx-auto h-8 w-4 rounded-sm ${
                      agent.status === 'running' ? 'bg-accent/60' : 'bg-surface-3'
                    }`}
                    style={{
                      height: agent.status === 'running' ? '32px' : '8px',
                      marginTop: agent.status === 'running' ? '0' : '24px',
                    }}
                  />
                  <p className="text-[10px] text-text-muted mt-1 truncate">{agent.id.slice(0, 5)}</p>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
