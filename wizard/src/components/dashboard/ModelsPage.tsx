import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api } from '../../lib/api';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

interface StrategyRoute {
  task: string;
  model: string;
  provider: string;
  priority: number;
}

export function ModelsPage() {
  const [routes, setRoutes] = useState<StrategyRoute[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchStrategy = async () => {
    setLoading(true);
    try {
      const data = await api.dashboard.getStrategy();
      setRoutes(data.routes ?? data.strategy?.routes ?? []);
    } catch {
      // Fallback demo data
      setRoutes([
        { task: 'chat', model: 'claude-4', provider: 'anthropic', priority: 1 },
        { task: 'code', model: 'deepseek-v3', provider: 'deepseek', priority: 1 },
        { task: 'reasoning', model: 'deepseek-r1', provider: 'local', priority: 2 },
        { task: 'embedding', model: 'nomic-embed', provider: 'local', priority: 3 },
        { task: 'fallback', model: 'llama-3.2', provider: 'local', priority: 10 },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStrategy(); }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Model Strategy</h1>
          <p className="text-sm text-text-secondary mt-1">View routing table and model assignments</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchStrategy} loading={loading} icon={<RefreshCw size={14} />}>
          Refresh
        </Button>
      </div>

      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-4">Routing Table</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-base text-left text-xs font-medium text-text-muted">
                <th className="pb-3 pr-4">Task</th>
                <th className="pb-3 pr-4">Model</th>
                <th className="pb-3 pr-4">Provider</th>
                <th className="pb-3">Priority</th>
              </tr>
            </thead>
            <tbody>
              {routes.map((route, i) => (
                <tr key={i} className="border-b border-border-subtle last:border-0">
                  <td className="py-3 pr-4">
                    <Badge variant="accent">{route.task}</Badge>
                  </td>
                  <td className="py-3 pr-4 font-mono text-text-primary">{route.model}</td>
                  <td className="py-3 pr-4">
                    <Badge variant={route.provider === 'local' ? 'success' : 'default'}>
                      {route.provider}
                    </Badge>
                  </td>
                  <td className="py-3 text-text-muted">{route.priority}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
