import { useEffect, useState } from 'react';
import { Bell, Plus, Trash2, Play, RefreshCw, Zap } from 'lucide-react';
import { api } from '../../lib/api';
import { Card, StatCard } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Input } from '../ui/Input';
import { Toggle } from '../ui/Toggle';

interface Trigger {
  id: string;
  name: string;
  enabled: boolean;
  condition: { type: string; [k: string]: unknown };
  actions: { type: string; [k: string]: unknown }[];
  cooldown: number;
  last_fired?: number;
  fire_count?: number;
}

interface TriggersData {
  triggers: Trigger[];
  condition_types: string[];
  action_types: string[];
}

const CONDITION_LABELS: Record<string, string> = {
  agent_status: 'Agent Status Change',
  memory_threshold: 'Memory Threshold',
  cpu_threshold: 'CPU Threshold',
  response_time: 'Response Time',
  cost_limit: 'Cost Limit Reached',
  model_pull_failure: 'Model Pull Failure',
  custom_http: 'Custom HTTP Check',
};

const ACTION_LABELS: Record<string, string> = {
  alert: 'Send Alert',
  restart_container: 'Restart Container',
  switch_model: 'Switch Model',
  scale_down: 'Scale Down',
  webhook: 'Call Webhook',
  log: 'Log Event',
};

export function TriggersPage() {
  const [data, setData] = useState<TriggersData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);

  // Form state
  const [formName, setFormName] = useState('');
  const [formCondType, setFormCondType] = useState('agent_status');
  const [formCondAgent, setFormCondAgent] = useState('zeroclaw');
  const [formCondUrl, setFormCondUrl] = useState('');
  const [formCondLimit, setFormCondLimit] = useState('50');
  const [formActions, setFormActions] = useState<string[]>(['log']);
  const [formCooldown, setFormCooldown] = useState('300');

  const fetchData = async () => {
    setLoading(true);
    try {
      const d = await api.dashboard.getTriggers();
      setData(d);
    } catch {
      setData({
        triggers: [],
        condition_types: Object.keys(CONDITION_LABELS),
        action_types: Object.keys(ACTION_LABELS),
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleSave = async () => {
    if (!data || !formName.trim()) return;
    const newTrigger: Trigger = {
      id: `trig_${Date.now()}`,
      name: formName,
      enabled: true,
      condition: {
        type: formCondType,
        ...(formCondType === 'agent_status' ? { agent_id: formCondAgent, expected: 'running' } : {}),
        ...(formCondType === 'cost_limit' ? { limit: parseFloat(formCondLimit) } : {}),
        ...(formCondType === 'custom_http' ? { url: formCondUrl, expect_status: 200 } : {}),
      },
      actions: formActions.map((a) => ({ type: a })),
      cooldown: parseInt(formCooldown) || 300,
      fire_count: 0,
    };
    const updated = { ...data, triggers: [...data.triggers, newTrigger] };
    await api.dashboard.saveTriggers(updated);
    setShowForm(false);
    setFormName('');
    fetchData();
  };

  const handleDelete = async (id: string) => {
    if (!data) return;
    const updated = { ...data, triggers: data.triggers.filter((t) => t.id !== id) };
    await api.dashboard.saveTriggers(updated);
    fetchData();
  };

  const handleToggle = async (id: string, enabled: boolean) => {
    if (!data) return;
    const updated = {
      ...data,
      triggers: data.triggers.map((t) => (t.id === id ? { ...t, enabled } : t)),
    };
    await api.dashboard.saveTriggers(updated);
    fetchData();
  };

  const handleTest = async (trigger: Trigger) => {
    setTesting(trigger.id);
    try {
      await api.dashboard.testTrigger(trigger as unknown as Record<string, unknown>);
    } catch { /* ignore */ }
    setTesting(null);
  };

  const toggleAction = (action: string) => {
    setFormActions((prev) =>
      prev.includes(action) ? prev.filter((a) => a !== action) : [...prev, action],
    );
  };

  const triggers = data?.triggers ?? [];
  const activeTriggers = triggers.filter((t) => t.enabled).length;
  const totalFires = triggers.reduce((sum, t) => sum + (t.fire_count ?? 0), 0);
  const lastFired = triggers
    .filter((t) => t.last_fired)
    .sort((a, b) => (b.last_fired ?? 0) - (a.last_fired ?? 0))[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Alert Triggers</h1>
          <p className="text-sm text-text-secondary mt-1">
            Automated monitoring rules with multi-channel alerts
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchData} loading={loading} icon={<RefreshCw size={14} />}>
            Refresh
          </Button>
          <Button size="sm" onClick={() => setShowForm(!showForm)} icon={<Plus size={14} />}>
            Add Trigger
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard icon={<Bell size={16} />} label="Active Triggers" value={String(activeTriggers)} />
        <StatCard icon={<Zap size={16} />} label="Total Fires" value={String(totalFires)} />
        <StatCard
          icon={<Play size={16} />}
          label="Last Fired"
          value={lastFired?.last_fired ? new Date(lastFired.last_fired * 1000).toLocaleTimeString() : 'Never'}
        />
      </div>

      {/* Add Form */}
      {showForm && (
        <Card className="space-y-4">
          <h3 className="text-sm font-medium text-text-primary">New Trigger</h3>
          <Input
            label="Trigger Name"
            placeholder="e.g. Agent Down Alert"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
          />
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-2">Condition Type</label>
            <div className="grid grid-cols-3 gap-2">
              {(data?.condition_types ?? Object.keys(CONDITION_LABELS)).map((ct) => (
                <button
                  key={ct}
                  onClick={() => setFormCondType(ct)}
                  className={`rounded-lg border px-3 py-2 text-xs transition-colors ${
                    formCondType === ct
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border-base bg-surface-1 text-text-secondary hover:bg-surface-2'
                  }`}
                >
                  {CONDITION_LABELS[ct] ?? ct}
                </button>
              ))}
            </div>
          </div>
          {formCondType === 'agent_status' && (
            <Input
              label="Agent ID"
              placeholder="zeroclaw"
              value={formCondAgent}
              onChange={(e) => setFormCondAgent(e.target.value)}
            />
          )}
          {formCondType === 'cost_limit' && (
            <Input
              label="Cost Limit ($)"
              placeholder="50"
              value={formCondLimit}
              onChange={(e) => setFormCondLimit(e.target.value)}
            />
          )}
          {formCondType === 'custom_http' && (
            <Input
              label="URL to Check"
              placeholder="http://localhost:3100/health"
              value={formCondUrl}
              onChange={(e) => setFormCondUrl(e.target.value)}
            />
          )}
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-2">Actions</label>
            <div className="flex flex-wrap gap-2">
              {(data?.action_types ?? Object.keys(ACTION_LABELS)).map((at) => (
                <button
                  key={at}
                  onClick={() => toggleAction(at)}
                  className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                    formActions.includes(at)
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border-base text-text-muted hover:bg-surface-2'
                  }`}
                >
                  {ACTION_LABELS[at] ?? at}
                </button>
              ))}
            </div>
          </div>
          <Input
            label="Cooldown (seconds)"
            placeholder="300"
            value={formCooldown}
            onChange={(e) => setFormCooldown(e.target.value)}
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={handleSave}>Save Trigger</Button>
            <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>Cancel</Button>
          </div>
        </Card>
      )}

      {/* Trigger List */}
      {triggers.length === 0 ? (
        <Card>
          <p className="text-sm text-text-muted text-center py-6">
            No triggers configured. Click "Add Trigger" to create one.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {triggers.map((trigger) => (
            <Card key={trigger.id} className="flex items-center justify-between">
              <div className="flex items-center gap-4 flex-1">
                <Toggle
                  enabled={trigger.enabled}
                  onChange={(enabled) => handleToggle(trigger.id, enabled)}
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-text-primary">{trigger.name}</p>
                    <Badge variant={trigger.enabled ? 'success' : 'default'}>
                      {trigger.enabled ? 'Active' : 'Disabled'}
                    </Badge>
                    {(trigger.fire_count ?? 0) > 0 && (
                      <Badge variant="accent">Fired {trigger.fire_count}x</Badge>
                    )}
                  </div>
                  <p className="text-xs text-text-muted mt-0.5">
                    Condition: {CONDITION_LABELS[trigger.condition.type] ?? trigger.condition.type}
                    {' · '}
                    Actions: {trigger.actions.map((a) => ACTION_LABELS[a.type] ?? a.type).join(', ')}
                    {' · '}
                    Cooldown: {trigger.cooldown}s
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleTest(trigger)}
                  loading={testing === trigger.id}
                  icon={<Play size={14} />}
                >
                  Test
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => handleDelete(trigger.id)}
                  icon={<Trash2 size={14} />}
                >
                  Delete
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
