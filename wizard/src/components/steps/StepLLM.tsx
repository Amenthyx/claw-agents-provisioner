import { useEffect, useState } from 'react';
import { Cloud, HardDrive, Shuffle, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWizard } from '../../state/context';
import { CLOUD_PROVIDERS, LOCAL_RUNTIMES as FALLBACK_RUNTIMES } from '../../data/providers';
import { api } from '../../lib/api';
import { SelectionCard } from '../ui/Card';
import { Input } from '../ui/Input';
import { Badge } from '../ui/Badge';
import { stagger, fadeInUp, fadeIn } from '../../lib/motion';
import type { LocalRuntime } from '../../state/types';

const MODES = [
  { id: 'cloud', name: 'Cloud API', icon: Cloud, desc: 'Use hosted LLM providers via API' },
  { id: 'local', name: 'Local LLM', icon: HardDrive, desc: 'Native install on your machine — full GPU access' },
  { id: 'hybrid', name: 'Hybrid', icon: Shuffle, desc: 'Local native + cloud fallback for reliability' },
] as const;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeRuntimes(raw: any[]): LocalRuntime[] {
  return raw.map((r) => ({
    id: r.id ?? '',
    name: r.name ?? '',
    port: r.port ?? 0,
    description: r.description ?? '',
  }));
}

export function StepLLM() {
  const {
    state, setLlmProvider, setRuntime, setCloudProviders, setApiKey, setGateway,
  } = useWizard();

  const [runtimes, setRuntimes] = useState<LocalRuntime[]>(FALLBACK_RUNTIMES);

  useEffect(() => {
    api.getRuntimes()
      .then((data) => {
        const raw = data.runtimes ?? data;
        if (Array.isArray(raw) && raw.length > 0) {
          setRuntimes(normalizeRuntimes(raw));
        }
      })
      .catch(() => { /* use fallback */ });
  }, []);

  const toggleCloudProvider = (id: string) => {
    const next = state.cloudProviders.includes(id)
      ? state.cloudProviders.filter((p) => p !== id)
      : [...state.cloudProviders, id];
    setCloudProviders(next);
  };

  const showCloud = state.llmProvider === 'cloud' || state.llmProvider === 'hybrid';
  const showLocal = state.llmProvider === 'local' || state.llmProvider === 'hybrid';

  return (
    <div className="space-y-6">
      {/* Mode Selection */}
      <motion.div variants={stagger} initial="initial" animate="animate" className="grid grid-cols-3 gap-3">
        {MODES.map((m) => {
          const selected = state.llmProvider === m.id;
          return (
            <motion.div key={m.id} variants={fadeInUp}>
              <SelectionCard
                selected={selected}
                onClick={() => setLlmProvider(m.id)}
                className="text-center h-full"
              >
                <m.icon size={20} className={`mx-auto ${selected ? 'text-accent' : 'text-text-muted'}`} />
                <h3 className="text-sm font-medium text-text-primary mt-2">{m.name}</h3>
                <p className="text-xs text-text-secondary mt-1">{m.desc}</p>
              </SelectionCard>
            </motion.div>
          );
        })}
      </motion.div>

      {/* Cloud Providers */}
      <AnimatePresence>
        {showCloud && (
          <motion.div variants={fadeIn} initial="initial" animate="animate" exit="exit" className="space-y-4">
            <h3 className="text-sm font-medium text-text-primary">Cloud Providers</h3>
            <div className="space-y-2">
              {CLOUD_PROVIDERS.map((cp) => {
                const selected = state.cloudProviders.includes(cp.id);
                return (
                  <div key={cp.id} className="space-y-2">
                    <SelectionCard
                      selected={selected}
                      onClick={() => toggleCloudProvider(cp.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div
                            className="h-3 w-3 rounded-full"
                            style={{ background: cp.color }}
                          />
                          <div>
                            <p className="text-sm font-medium text-text-primary">{cp.name}</p>
                            <p className="text-xs text-text-muted">{cp.model}</p>
                          </div>
                        </div>
                        {selected && (
                          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-white">
                            <Check size={12} />
                          </span>
                        )}
                      </div>
                    </SelectionCard>
                    {selected && (
                      <div className="ml-6">
                        <Input
                          label={`${cp.name} API Key`}
                          isPassword
                          placeholder={`sk-...`}
                          value={state.apiKeys[cp.id] ?? ''}
                          onChange={(e) => setApiKey(cp.id, e.target.value)}
                          hint="Stored locally — never sent externally"
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Local Runtimes */}
      <AnimatePresence>
        {showLocal && (
          <motion.div variants={fadeIn} initial="initial" animate="animate" exit="exit" className="space-y-4">
            <h3 className="text-sm font-medium text-text-primary">Local Runtime</h3>
            <div className="grid grid-cols-2 gap-3">
              {runtimes.map((rt) => {
                const selected = state.runtime === rt.id;
                return (
                  <SelectionCard
                    key={rt.id}
                    selected={selected}
                    onClick={() => setRuntime(rt.id)}
                  >
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium text-text-primary">{rt.name}</h4>
                      {selected && (
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-white">
                          <Check size={12} />
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-text-secondary mt-1">{rt.description}</p>
                    <Badge variant="muted" className="mt-2">Port {rt.port}</Badge>
                  </SelectionCard>
                );
              })}

              {/* Manual / Custom Endpoint card */}
              <SelectionCard
                selected={state.runtime === 'manual'}
                onClick={() => setRuntime('manual')}
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-text-primary">Custom Endpoint</h4>
                  {state.runtime === 'manual' && (
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-white">
                      <Check size={12} />
                    </span>
                  )}
                </div>
                <p className="text-xs text-text-secondary mt-1">Use a custom local LLM endpoint URL</p>
                <Badge variant="muted" className="mt-2">Manual</Badge>
              </SelectionCard>
            </div>

            {/* Custom endpoint URL input */}
            <AnimatePresence>
              {state.runtime === 'manual' && (
                <motion.div variants={fadeIn} initial="initial" animate="animate" exit="exit">
                  <Input
                    label="Custom Endpoint URL"
                    placeholder="http://localhost:8080/v1"
                    value={state.gateway.customLocalEndpoint ?? ''}
                    onChange={(e) => setGateway({ customLocalEndpoint: e.target.value })}
                    hint="Full URL to your local LLM API (e.g., http://localhost:8080/v1)"
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
