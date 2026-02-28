import { useState, useRef } from 'react';
import {
  Layers, Container, Brain, Boxes, Shield, Network, MessageSquare, Database,
  Pencil, Copy, Check, ChevronDown, ChevronUp, Rocket, Upload, Download,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useWizard } from '../../state/context';
import { PLATFORMS } from '../../data/platforms';
import { MODELS } from '../../data/models';
import { CLOUD_PROVIDERS, LOCAL_RUNTIMES } from '../../data/providers';
import { SECURITY_OPTIONS } from '../../data/security';
import { CHANNELS } from '../../data/channels';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { stagger, fadeInUp } from '../../lib/motion';
export function StepReview() {
  const { state, goToStep, nextStep, assessmentJSON, dispatch } = useWizard();
  const [showJson, setShowJson] = useState(false);
  const [copied, setCopied] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const platform = PLATFORMS.find((p) => p.id === state.platform);
  const runtime = LOCAL_RUNTIMES.find((r) => r.id === state.runtime);
  const selectedModels = MODELS.filter((m) => state.selectedModels.includes(m.id));
  const selectedProviders = CLOUD_PROVIDERS.filter((p) => state.cloudProviders.includes(p.id));
  const selectedSecurity = SECURITY_OPTIONS.filter((o) => state.securityFeatures.includes(o.id));
  const enabledChannels = CHANNELS.filter((c) => state.channels[c.id]?.enabled);

  const copyJson = async () => {
    await navigator.clipboard.writeText(JSON.stringify(assessmentJSON, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(assessmentJSON, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `xclaw-config-${state.agentName || 'untitled'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const importJson = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportError(null);

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const data = JSON.parse(event.target?.result as string) as Record<string, unknown>;
        applyImportedConfig(data);
      } catch {
        setImportError('Invalid JSON file');
      }
    };
    reader.readAsText(file);
    // Reset so same file can be re-selected
    e.target.value = '';
  };

  const applyImportedConfig = (data: Record<string, unknown>) => {
    // Apply known fields from imported config
    if (typeof data.agent_name === 'string') {
      dispatch({ type: 'SET_AGENT_NAME', name: data.agent_name });
    }
    if (typeof data.platform === 'string') {
      dispatch({ type: 'SET_PLATFORM', platform: data.platform });
    }
    if (typeof data.deployment_method === 'string') {
      dispatch({ type: 'SET_DEPLOYMENT_METHOD', method: data.deployment_method });
    }
    if (typeof data.llm_provider === 'string') {
      dispatch({ type: 'SET_LLM_PROVIDER', provider: data.llm_provider });
    }
    if (typeof data.runtime === 'string') {
      dispatch({ type: 'SET_RUNTIME', runtime: data.runtime });
    }
    if (Array.isArray(data.selected_models)) {
      for (const m of data.selected_models) {
        if (typeof m === 'string' && !state.selectedModels.includes(m)) {
          dispatch({ type: 'TOGGLE_MODEL', modelId: m });
        }
      }
    }
    if (Array.isArray(data.cloud_providers)) {
      dispatch({ type: 'SET_CLOUD_PROVIDERS', providers: data.cloud_providers as string[] });
    }
    if (data.gateway && typeof data.gateway === 'object') {
      const gw = data.gateway as Record<string, unknown>;
      dispatch({
        type: 'SET_GATEWAY',
        config: {
          ...(typeof gw.port === 'number' ? { port: gw.port } : {}),
          ...(typeof gw.rateLimit === 'number' ? { rateLimit: gw.rateLimit } : {}),
          ...(typeof gw.failover === 'string' ? { failover: gw.failover } : {}),
          ...(typeof gw.routing === 'string' ? { routing: gw.routing } : {}),
        },
      });
    }
    if (data.security && typeof data.security === 'object') {
      const sec = data.security as Record<string, unknown>;
      if (typeof sec.enabled === 'boolean') {
        dispatch({ type: 'SET_SECURITY_ENABLED', enabled: sec.enabled });
      }
    }
    if (data.channels && typeof data.channels === 'object') {
      for (const [id, cfg] of Object.entries(data.channels as Record<string, Record<string, string>>)) {
        dispatch({ type: 'SET_CHANNEL', channelId: id, config: { enabled: true, config: cfg } });
      }
    }
  };

  const sections = [
    {
      icon: Layers,
      title: 'XClaw',
      step: 0,
      content: (
        <div>
          <p className="font-medium text-text-primary">{state.agentName || 'Unnamed'}</p>
          <p className="text-xs text-text-muted mt-0.5">
            Platform: {platform ? `${platform.name} (${platform.language})` : 'Not selected'}
          </p>
        </div>
      ),
    },
    {
      icon: Container,
      title: 'Deployment',
      step: 3,
      content: state.deploymentMethod.charAt(0).toUpperCase() + state.deploymentMethod.slice(1),
    },
    {
      icon: Brain,
      title: 'LLM Provider',
      step: 4,
      content: (
        <div>
          <p className="capitalize">{state.llmProvider}</p>
          {selectedProviders.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {selectedProviders.map((p) => (
                <Badge key={p.id} dot={p.color}>{p.name}</Badge>
              ))}
            </div>
          )}
          {runtime && <p className="text-xs text-text-muted mt-1">Runtime: {runtime.name}</p>}
          {state.runtime === 'manual' && state.gateway.customLocalEndpoint && (
            <p className="text-xs text-text-muted mt-1 font-mono">{state.gateway.customLocalEndpoint}</p>
          )}
        </div>
      ),
    },
    {
      icon: Boxes,
      title: 'Models',
      step: 5,
      content:
        state.llmProvider === 'cloud' ? (
          <span className="text-text-muted">Cloud-only (no local models)</span>
        ) : selectedModels.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {selectedModels.map((m) => (
              <Badge key={m.id}>{m.name}</Badge>
            ))}
          </div>
        ) : (
          <span className="text-text-muted">None selected</span>
        ),
    },
    {
      icon: Shield,
      title: 'Security',
      step: 6,
      content: state.securityEnabled ? (
        <div className="space-y-1">
          {selectedSecurity.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {selectedSecurity.map((s) => (
                <Badge key={s.id} variant="accent">{s.name}</Badge>
              ))}
            </div>
          )}
          {Object.entries(state.complianceConfig).some(([, c]) => c.enabled) && (
            <div className="flex flex-wrap gap-1 mt-1">
              {Object.entries(state.complianceConfig)
                .filter(([, c]) => c.enabled)
                .map(([id]) => (
                  <Badge key={id} variant="warning">{id.toUpperCase()}</Badge>
                ))}
            </div>
          )}
        </div>
      ) : (
        <span className="text-text-muted">Disabled</span>
      ),
    },
    {
      icon: Database,
      title: 'Storage',
      step: 7,
      content: (
        <div>
          <p className="capitalize">{state.storage.instanceDb.engine} instance DB</p>
          {state.storage.sharedDb.enabled && (
            <p className="text-xs text-text-muted mt-1">
              Shared DB: {state.storage.sharedDb.engine}
            </p>
          )}
          {!state.storage.sharedDb.enabled && (
            <span className="text-xs text-text-muted">Shared DB disabled</span>
          )}
        </div>
      ),
    },
    {
      icon: Network,
      title: 'Gateway',
      step: 8,
      content: (
        <div>
          <p>Port {state.gateway.port} · {state.gateway.rateLimit} RPM · {state.gateway.failover} · {state.gateway.routing}</p>
          {state.gateway.routes.length > 0 && (
            <p className="text-xs text-text-muted mt-1">{state.gateway.routes.length} manual routes</p>
          )}
        </div>
      ),
    },
    {
      icon: MessageSquare,
      title: 'Channels',
      step: 9,
      content: enabledChannels.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {enabledChannels.map((c) => (
            <Badge key={c.id} variant="accent">{c.name}</Badge>
          ))}
        </div>
      ) : (
        <span className="text-text-muted">No channels configured</span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-3">
        {sections.map((s) => (
          <motion.div key={s.title} variants={fadeInUp}>
            <Card className="flex items-start gap-4">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-3 text-text-muted">
                <s.icon size={16} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-text-primary">{s.title}</h3>
                  <button
                    type="button"
                    onClick={() => goToStep(s.step)}
                    className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover transition-colors cursor-pointer"
                  >
                    <Pencil size={12} />
                    Edit
                  </button>
                </div>
                <div className="text-sm text-text-secondary mt-1">{s.content}</div>
              </div>
            </Card>
          </motion.div>
        ))}
      </motion.div>

      {/* JSON Export / Import */}
      <div className="rounded-xl border border-border-base bg-surface-1">
        <button
          type="button"
          onClick={() => setShowJson((v) => !v)}
          className="flex w-full items-center justify-between px-5 py-3 text-sm font-medium text-text-secondary hover:text-text-primary cursor-pointer"
        >
          Assessment JSON
          {showJson ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {showJson && (
          <div className="border-t border-border-base px-5 py-4">
            <div className="flex justify-between mb-2">
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Upload size={14} />}
                  onClick={() => fileInputRef.current?.click()}
                >
                  Import
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json"
                  onChange={importJson}
                  className="hidden"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Download size={14} />}
                  onClick={exportJson}
                >
                  Export
                </Button>
              </div>
              <Button
                variant="ghost"
                size="sm"
                icon={copied ? <Check size={14} /> : <Copy size={14} />}
                onClick={copyJson}
              >
                {copied ? 'Copied' : 'Copy'}
              </Button>
            </div>
            {importError && (
              <p className="text-xs text-error mb-2">{importError}</p>
            )}
            <pre className="overflow-x-auto rounded-lg bg-surface-0 p-4 text-xs font-mono text-text-secondary">
              {JSON.stringify(assessmentJSON, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Deploy CTA */}
      <div className="flex justify-center pt-2">
        <Button size="lg" onClick={nextStep} icon={<Rocket size={16} />}>
          Deploy Configuration
        </Button>
      </div>
    </div>
  );
}
