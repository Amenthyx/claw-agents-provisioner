import { Plus, Trash2 } from 'lucide-react';
import { useWizard } from '../../../state/context';
import { ROUTING_TARGETS, DEFAULT_ROUTES } from '../../../data/gateway';
import { Card } from '../../ui/Card';
import { Input } from '../../ui/Input';
import { Button } from '../../ui/Button';
import type { RoutingRule } from '../../../state/types';

export function ManualRoutingEditor() {
  const { state, setGatewayRoutes } = useWizard();
  const routes = state.gateway.routes;

  const addRoute = () => {
    const newRoute: RoutingRule = {
      pattern: '/api/new/*',
      target: 'auto',
      priority: routes.length + 1,
    };
    setGatewayRoutes([...routes, newRoute]);
  };

  const updateRoute = (index: number, updates: Partial<RoutingRule>) => {
    const next = routes.map((r, i) => (i === index ? { ...r, ...updates } : r));
    setGatewayRoutes(next);
  };

  const removeRoute = (index: number) => {
    setGatewayRoutes(routes.filter((_, i) => i !== index));
  };

  const loadDefaults = () => {
    setGatewayRoutes(DEFAULT_ROUTES);
  };

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-text-primary">Routing Rules</h4>
        <div className="flex gap-2">
          {routes.length === 0 && (
            <Button variant="ghost" size="sm" onClick={loadDefaults}>
              Load Defaults
            </Button>
          )}
          <Button size="sm" onClick={addRoute} icon={<Plus size={14} />}>
            Add Rule
          </Button>
        </div>
      </div>

      {routes.length > 0 ? (
        <div className="space-y-2">
          {/* Header */}
          <div className="grid grid-cols-[1fr_140px_60px_80px_32px] gap-2 text-xs font-medium text-text-muted px-1">
            <span>Pattern</span>
            <span>Target</span>
            <span>Priority</span>
            <span>RPM Override</span>
            <span />
          </div>

          {/* Rows */}
          {routes.map((rule, idx) => (
            <div
              key={idx}
              className="grid grid-cols-[1fr_140px_60px_80px_32px] gap-2 items-center"
            >
              <Input
                value={rule.pattern}
                onChange={(e) => updateRoute(idx, { pattern: e.target.value })}
                placeholder="/api/chat/*"
                className="font-mono text-xs"
              />
              <select
                value={rule.target}
                onChange={(e) => updateRoute(idx, { target: e.target.value })}
                className="h-9 rounded-lg border border-border-base bg-surface-2 px-2 text-sm text-text-primary"
              >
                {ROUTING_TARGETS.map((t) => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </select>
              <Input
                type="number"
                value={String(rule.priority)}
                onChange={(e) => updateRoute(idx, { priority: parseInt(e.target.value) || 1 })}
                className="text-center"
              />
              <Input
                type="number"
                placeholder="—"
                value={rule.rateLimitOverride != null ? String(rule.rateLimitOverride) : ''}
                onChange={(e) => {
                  const val = e.target.value ? parseInt(e.target.value) : undefined;
                  updateRoute(idx, { rateLimitOverride: val });
                }}
              />
              <button
                type="button"
                onClick={() => removeRoute(idx)}
                className="flex h-8 w-8 items-center justify-center rounded-md text-text-muted hover:text-error hover:bg-error/10 cursor-pointer"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-muted italic text-center py-4">
          No routing rules defined. Click "Add Rule" or "Load Defaults" to get started.
        </p>
      )}

      <p className="text-xs text-text-muted">
        Rules are evaluated in priority order (1 = highest). Use <code className="font-mono bg-surface-3 px-1 rounded">*</code> as a wildcard in patterns.
      </p>
    </Card>
  );
}
