import { useEffect, useState } from 'react';
import {
  Send, MessageCircle, Hash, Gamepad2, Mail, Webhook,
  RefreshCw, CheckCircle2, XCircle, ArrowRight, GripVertical,
} from 'lucide-react';
import { api } from '../../lib/api';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { CHANNELS } from '../../data/channels';

const CHANNEL_ICONS: Record<string, React.FC<{ size?: number; className?: string }>> = {
  Send, MessageCircle, Hash, Gamepad2, Mail, Webhook,
};

interface ChannelStatus {
  configured: boolean;
  status: 'connected' | 'not_configured' | 'error';
  message?: string;
}

export function ChannelsPage() {
  const [statusMap, setStatusMap] = useState<Record<string, ChannelStatus>>({});
  const [fallbackChain, setFallbackChain] = useState<string[]>([
    'telegram', 'slack', 'discord', 'email', 'webhook',
  ]);
  const [loading, setLoading] = useState(false);
  const [testingChannel, setTestingChannel] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message?: string }>>({});

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const data = await api.dashboard.getChannelsStatus();
      if (data.channels) {
        setStatusMap(data.channels);
      }
      if (data.fallback_chain) {
        setFallbackChain(data.fallback_chain);
      }
    } catch {
      // Channels not configured yet - use defaults
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStatus(); }, []);

  const handleTestChannel = async (channelId: string) => {
    setTestingChannel(channelId);
    try {
      const result = await api.testChannel(channelId, {});
      setTestResults((prev) => ({ ...prev, [channelId]: result }));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [channelId]: { success: false, message: 'Test failed — channel not configured' },
      }));
    }
    setTestingChannel(null);
  };

  const getStatusBadge = (channelId: string) => {
    const status = statusMap[channelId];
    if (!status) return <Badge variant="default">Not configured</Badge>;
    if (status.status === 'connected') return <Badge variant="success">Connected</Badge>;
    if (status.status === 'error') return <Badge variant="error">Error</Badge>;
    return <Badge variant="default">Not configured</Badge>;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Communication Channels</h1>
          <p className="text-sm text-text-secondary mt-1">
            Manage notification channels, test connectivity, and configure fallback routing
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchStatus} loading={loading} icon={<RefreshCw size={14} />}>
          Refresh
        </Button>
      </div>

      {/* Channel Grid */}
      <div className="grid grid-cols-2 gap-4">
        {CHANNELS.map((channel) => {
          const Icon = CHANNEL_ICONS[channel.icon] ?? Send;
          const testResult = testResults[channel.id];
          return (
            <Card key={channel.id} className="space-y-3">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-3 text-text-muted">
                  <Icon size={18} />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-text-primary">{channel.name}</h3>
                    {getStatusBadge(channel.id)}
                  </div>
                  <p className="text-xs text-text-muted mt-1">{channel.description}</p>
                </div>
              </div>

              {/* Fields summary */}
              <div className="text-xs text-text-muted">
                Fields: {channel.fields.map((f) => f.label).join(', ')}
              </div>

              {/* Test result */}
              {testResult && (
                <div className={`flex items-center gap-2 rounded-md px-3 py-2 text-xs ${
                  testResult.success ? 'bg-success/10 text-success' : 'bg-error/10 text-error'
                }`}>
                  {testResult.success ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                  {testResult.message}
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleTestChannel(channel.id)}
                  loading={testingChannel === channel.id}
                  icon={<CheckCircle2 size={12} />}
                >
                  Test
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Fallback Chain */}
      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-3">Fallback Chain</h3>
        <p className="text-xs text-text-muted mb-4">
          If the primary channel fails, alerts cascade through this priority order
        </p>
        <div className="flex items-center gap-2 flex-wrap">
          {fallbackChain.map((chId, idx) => {
            const ch = CHANNELS.find((c) => c.id === chId);
            const Icon = CHANNEL_ICONS[ch?.icon ?? 'Send'] ?? Send;
            return (
              <div key={chId} className="flex items-center gap-2">
                <div className="flex items-center gap-2 rounded-lg border border-border-base bg-surface-0 px-3 py-2">
                  <GripVertical size={12} className="text-text-muted" />
                  <Icon size={14} className="text-text-muted" />
                  <span className="text-xs font-medium text-text-primary">{ch?.name ?? chId}</span>
                  <Badge variant="muted" className="text-[10px]">{idx + 1}</Badge>
                </div>
                {idx < fallbackChain.length - 1 && (
                  <ArrowRight size={14} className="text-text-muted" />
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Routing Rules */}
      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-3">Alert Routing</h3>
        <p className="text-xs text-text-muted mb-4">
          Which alert types are sent to which channels
        </p>
        <div className="space-y-2">
          {[
            { type: 'Agent Down', channels: ['telegram', 'slack'], severity: 'critical' },
            { type: 'Cost Limit', channels: ['email', 'slack'], severity: 'warning' },
            { type: 'Model Failure', channels: ['telegram', 'discord'], severity: 'error' },
            { type: 'Health Degraded', channels: ['slack'], severity: 'warning' },
            { type: 'Trigger Fired', channels: fallbackChain.slice(0, 2), severity: 'info' },
          ].map((rule) => (
            <div key={rule.type} className="flex items-center justify-between rounded-lg border border-border-base bg-surface-0 px-4 py-2">
              <div className="flex items-center gap-2">
                <Badge variant={
                  rule.severity === 'critical' ? 'error'
                    : rule.severity === 'error' ? 'error'
                    : rule.severity === 'warning' ? 'warning'
                    : 'default'
                }>
                  {rule.severity}
                </Badge>
                <span className="text-sm text-text-primary">{rule.type}</span>
              </div>
              <div className="flex gap-1">
                {rule.channels.map((chId) => {
                  const ch = CHANNELS.find((c) => c.id === chId);
                  return (
                    <Badge key={chId} variant="accent">{ch?.name ?? chId}</Badge>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
