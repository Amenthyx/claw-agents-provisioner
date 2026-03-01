import { useState } from 'react';
import { ChevronDown, ChevronUp, Send, MessageCircle, Hash, Gamepad2, Mail, Webhook, CheckCircle2, XCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWizard } from '../../state/context';
import { CHANNELS } from '../../data/channels';
import { api } from '../../lib/api';
import { Card } from '../ui/Card';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { Toggle } from '../ui/Toggle';
import { Badge } from '../ui/Badge';
import { stagger, fadeInUp, fadeIn } from '../../lib/motion';
import type { ChannelDef } from '../../data/channels';

const CHANNEL_ICONS: Record<string, React.FC<{ size?: number; className?: string }>> = {
  Send, MessageCircle, Hash, Gamepad2, Mail, Webhook,
};

type TestStatus = 'idle' | 'testing' | 'success' | 'error';

export function StepChannels() {
  const { state, setChannel } = useWizard();
  const [expandedChannel, setExpandedChannel] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState<string | null>(null);
  const [testStatuses, setTestStatuses] = useState<Record<string, TestStatus>>({});

  const enabledCount = Object.values(state.channels).filter((c) => c.enabled).length;

  const handleToggle = (channelId: string) => {
    const current = state.channels[channelId];
    setChannel(channelId, { enabled: !current?.enabled });
    if (!current?.enabled) {
      setExpandedChannel(channelId);
    }
  };

  const handleConfigChange = (channelId: string, key: string, value: string) => {
    const current = state.channels[channelId];
    setChannel(channelId, {
      config: { ...current?.config, [key]: value },
    });
  };

  const handleTest = async (channel: ChannelDef) => {
    setTestStatuses((prev) => ({ ...prev, [channel.id]: 'testing' }));
    try {
      const cfg = state.channels[channel.id]?.config ?? {};
      await api.testChannel(channel.id, cfg);
      setTestStatuses((prev) => ({ ...prev, [channel.id]: 'success' }));
    } catch {
      setTestStatuses((prev) => ({ ...prev, [channel.id]: 'error' }));
    }
    setTimeout(() => {
      setTestStatuses((prev) => ({ ...prev, [channel.id]: 'idle' }));
    }, 3000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-xs text-text-muted">
          {enabledCount > 0
            ? `${enabledCount} channel${enabledCount > 1 ? 's' : ''} enabled`
            : 'No channels enabled (optional — you can skip this step)'}
        </p>
      </div>

      <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-3">
        {CHANNELS.map((channel) => {
          const cfg = state.channels[channel.id];
          const isEnabled = cfg?.enabled ?? false;
          const isExpanded = expandedChannel === channel.id;
          const Icon = CHANNEL_ICONS[channel.icon] ?? Send;
          const testStatus = testStatuses[channel.id] ?? 'idle';

          return (
            <motion.div key={channel.id} variants={fadeInUp}>
              <Card className="space-y-0">
                {/* Channel Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-3 text-text-muted">
                      <Icon size={16} />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-text-primary">{channel.name}</p>
                      <p className="text-xs text-text-muted">{channel.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Toggle enabled={isEnabled} onChange={() => handleToggle(channel.id)} />
                    {isEnabled && (
                      <button
                        type="button"
                        onClick={() => setExpandedChannel(isExpanded ? null : channel.id)}
                        className="text-text-muted hover:text-text-primary cursor-pointer p-1"
                      >
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                    )}
                  </div>
                </div>

                {/* Config Form */}
                <AnimatePresence>
                  {isEnabled && isExpanded && (
                    <motion.div
                      variants={fadeIn}
                      initial="initial"
                      animate="animate"
                      exit="exit"
                      className="border-t border-border-base mt-4 pt-4 space-y-4"
                    >
                      {/* Fields */}
                      <div className="space-y-3">
                        {channel.fields.map((field) => {
                          if (field.type === 'toggle') {
                            return (
                              <Toggle
                                key={field.key}
                                enabled={cfg?.config[field.key] === 'true'}
                                onChange={(val) => handleConfigChange(channel.id, field.key, String(val))}
                                label={field.label}
                              />
                            );
                          }
                          return (
                            <Input
                              key={field.key}
                              label={field.label}
                              placeholder={field.placeholder}
                              type={field.type === 'password' ? undefined : field.type}
                              isPassword={field.type === 'password'}
                              value={cfg?.config[field.key] ?? ''}
                              onChange={(e) => handleConfigChange(channel.id, field.key, e.target.value)}
                            />
                          );
                        })}
                      </div>

                      {/* Test Connection */}
                      <div className="flex items-center gap-3">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleTest(channel)}
                          loading={testStatus === 'testing'}
                        >
                          {testStatus === 'testing' ? 'Testing...' : 'Test Connection'}
                        </Button>
                        {testStatus === 'success' && (
                          <span className="flex items-center gap-1 text-xs text-success">
                            <CheckCircle2 size={14} /> Connected
                          </span>
                        )}
                        {testStatus === 'error' && (
                          <span className="flex items-center gap-1 text-xs text-error">
                            <XCircle size={14} /> Failed
                          </span>
                        )}
                      </div>

                      {/* Setup Guide */}
                      <div>
                        <button
                          type="button"
                          onClick={() => setShowGuide(showGuide === channel.id ? null : channel.id)}
                          className="text-xs text-accent hover:text-accent-hover cursor-pointer"
                        >
                          {showGuide === channel.id ? 'Hide setup guide' : 'Show setup guide'}
                        </button>
                        <AnimatePresence>
                          {showGuide === channel.id && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden"
                            >
                              <ol className="mt-2 space-y-1.5 text-xs text-text-secondary list-decimal list-inside">
                                {channel.guideSteps.map((step, i) => (
                                  <li key={i}>{step}</li>
                                ))}
                              </ol>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </Card>
            </motion.div>
          );
        })}
      </motion.div>

      {/* Summary */}
      {enabledCount > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {CHANNELS.filter((c) => state.channels[c.id]?.enabled).map((c) => (
            <Badge key={c.id} variant="accent">{c.name}</Badge>
          ))}
        </div>
      )}
    </div>
  );
}
