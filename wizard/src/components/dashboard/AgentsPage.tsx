import { useEffect, useState } from 'react';
import { Play, Square, RotateCw, RefreshCw } from 'lucide-react';
import { api } from '../../lib/api';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

interface Agent {
  id: string;
  name: string;
  status: string;
  port: number;
  language: string;
  memory: string;
  features: string[];
}

export function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchAgents = async () => {
    setLoading(true);
    try {
      const data = await api.dashboard.getAgents();
      setAgents(data.agents ?? []);
    } catch {
      setAgents([
        { id: 'zeroclaw', name: 'ZeroClaw', status: 'stopped', port: 3100, language: 'Rust', memory: '512 MB', features: ['Minimal footprint'] },
        { id: 'nanoclaw', name: 'NanoClaw', status: 'stopped', port: 3200, language: 'TypeScript', memory: '1 GB', features: ['Claude-native'] },
        { id: 'picoclaw', name: 'PicoClaw', status: 'stopped', port: 3300, language: 'Go', memory: '128 MB', features: ['Data processing'] },
        { id: 'openclaw', name: 'OpenClaw', status: 'stopped', port: 3400, language: 'Node.js', memory: '4 GB', features: ['50+ integrations'] },
        { id: 'parlant', name: 'Parlant', status: 'stopped', port: 8800, language: 'Python', memory: '2 GB', features: ['MCP protocol'] },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAgents(); }, []);

  const handleAction = async (agentId: string, action: 'start' | 'stop' | 'restart') => {
    setActionLoading(`${agentId}-${action}`);
    try {
      await api.dashboard.agentAction(agentId, action);
      await fetchAgents();
    } catch {
      // Silently fail — UI remains consistent
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Agent Management</h1>
          <p className="text-sm text-text-secondary mt-1">Start, stop, and monitor agent platforms</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchAgents} loading={loading} icon={<RefreshCw size={14} />}>
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {agents.map((agent) => {
          const isRunning = agent.status === 'running';
          return (
            <Card key={agent.id} className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`h-3 w-3 rounded-full ${isRunning ? 'bg-success' : 'bg-text-muted'}`} />
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-text-primary">{agent.name}</h3>
                    <Badge variant={isRunning ? 'success' : 'default'}>{agent.status}</Badge>
                  </div>
                  <p className="text-xs text-text-muted mt-0.5">
                    {agent.language} · {agent.memory} · Port {agent.port}
                  </p>
                  <div className="flex gap-1 mt-1.5">
                    {(agent.features ?? []).map((f) => (
                      <Badge key={f} variant="muted" className="text-[10px]">{f}</Badge>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                {!isRunning && (
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Play size={14} />}
                    loading={actionLoading === `${agent.id}-start`}
                    onClick={() => handleAction(agent.id, 'start')}
                  >
                    Start
                  </Button>
                )}
                {isRunning && (
                  <>
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<RotateCw size={14} />}
                      loading={actionLoading === `${agent.id}-restart`}
                      onClick={() => handleAction(agent.id, 'restart')}
                    >
                      Restart
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      icon={<Square size={14} />}
                      loading={actionLoading === `${agent.id}-stop`}
                      onClick={() => handleAction(agent.id, 'stop')}
                    >
                      Stop
                    </Button>
                  </>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
