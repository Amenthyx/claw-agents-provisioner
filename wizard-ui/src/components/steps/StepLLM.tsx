import { useState } from 'react';
import { Cloud, HardDrive, Shuffle, Eye, EyeOff, Key } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Checkbox } from '../ui/checkbox';
import { staggerContainer, cardVariant, fadeInUp } from '../../lib/motion';
import { CLOUD_PROVIDERS, LOCAL_RUNTIMES } from '../../lib/types';

interface StepLLMProps {
  selected: 'cloud' | 'local' | 'hybrid';
  onSelect: (provider: 'cloud' | 'local' | 'hybrid') => void;
  runtime: string;
  onRuntimeChange: (runtime: string) => void;
  cloudProviders: string[];
  onCloudProvidersChange: (providers: string[]) => void;
  apiKeys: Record<string, string>;
  onApiKeysChange: (keys: Record<string, string>) => void;
}

const modeCards = [
  {
    id: 'cloud' as const,
    icon: Cloud,
    title: 'Cloud API',
    description: 'Use cloud-hosted LLM providers. No GPU required. Pay-per-use pricing with instant access to the latest models.',
  },
  {
    id: 'local' as const,
    icon: HardDrive,
    title: 'Local LLM',
    description: 'Run models on your own hardware. Full data privacy, no API costs, and offline capability.',
  },
  {
    id: 'hybrid' as const,
    icon: Shuffle,
    title: 'Hybrid',
    description: 'Best of both — cloud fallback with local primary. Use local models when available, cloud when needed.',
  },
];

export function StepLLM({
  selected,
  onSelect,
  runtime,
  onRuntimeChange,
  cloudProviders,
  onCloudProvidersChange,
  apiKeys,
  onApiKeysChange,
}: StepLLMProps) {
  const showCloudSection = selected === 'cloud' || selected === 'hybrid';
  const showLocalSection = selected === 'local' || selected === 'hybrid';

  const toggleProvider = (providerId: string) => {
    const next = cloudProviders.includes(providerId)
      ? cloudProviders.filter((p) => p !== providerId)
      : [...cloudProviders, providerId];
    onCloudProvidersChange(next);
    if (!next.includes(providerId)) {
      const nextKeys = { ...apiKeys };
      delete nextKeys[providerId];
      onApiKeysChange(nextKeys);
    }
  };

  const updateApiKey = (providerId: string, value: string) => {
    onApiKeysChange({ ...apiKeys, [providerId]: value });
  };

  return (
    <div>
      <motion.div className="mb-8" variants={fadeInUp} initial="initial" animate="animate">
        <h2 className="text-2xl font-bold text-text-primary mb-2">LLM Provider</h2>
        <p className="text-text-secondary">
          Choose between cloud-based API providers, running models locally, or a hybrid approach.
        </p>
      </motion.div>

      {/* 3 Mode Cards */}
      <motion.div
        className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-5xl mb-8"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        {modeCards.map((mode) => (
          <motion.div key={mode.id} variants={cardVariant}>
            <Card
              selected={selected === mode.id}
              hoverable
              onClick={() => onSelect(mode.id)}
              className="relative h-full"
            >
              {selected === mode.id && (
                <div className="absolute top-4 right-4">
                  <Badge variant="accent">Selected</Badge>
                </div>
              )}
              <CardContent className="pt-8 pb-8">
                <div className={`
                  w-14 h-14 rounded-2xl flex items-center justify-center mb-5
                  ${selected === mode.id ? 'bg-neon-cyan/20 text-neon-cyan' : 'bg-cyber-bg-surface text-text-secondary'}
                  transition-colors
                `}>
                  <mode.icon className="w-7 h-7" />
                </div>
                <h3 className="text-lg font-semibold text-text-primary mb-2">{mode.title}</h3>
                <p className="text-sm text-text-secondary leading-relaxed">{mode.description}</p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </motion.div>

      {/* Cloud Providers + API Keys Section */}
      <AnimatePresence>
        {showCloudSection && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="overflow-hidden mb-8"
          >
            <Card className="max-w-5xl">
              <CardContent className="py-6">
                <div className="flex items-center gap-2 mb-4">
                  <Key className="w-4 h-4 text-neon-cyan" />
                  <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">
                    Cloud Providers & API Keys
                  </h3>
                </div>
                <p className="text-xs text-text-muted mb-5">
                  Select providers and enter API keys. Keys are stored locally and never sent to our servers.
                </p>

                <div className="space-y-3">
                  {CLOUD_PROVIDERS.map((provider) => {
                    const isChecked = cloudProviders.includes(provider.id);
                    return (
                      <div key={provider.id} className="space-y-2">
                        <div
                          className={`
                            flex items-center justify-between p-3 rounded-lg border transition-all cursor-pointer
                            ${isChecked ? 'border-neon-cyan/30 bg-neon-cyan/5' : 'border-cyber-border hover:border-neon-cyan/20'}
                          `}
                          onClick={() => toggleProvider(provider.id)}
                        >
                          <div className="flex items-center gap-3">
                            <Checkbox
                              checked={isChecked}
                              onChange={() => toggleProvider(provider.id)}
                            />
                            <div
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: provider.color }}
                            />
                            <span className="text-sm font-medium text-text-primary">{provider.name}</span>
                            <span className="text-xs text-text-muted font-mono">{provider.model}</span>
                          </div>
                        </div>

                        <AnimatePresence>
                          {isChecked && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={{ opacity: 0, height: 0 }}
                              transition={{ duration: 0.2 }}
                              className="overflow-hidden pl-11"
                            >
                              <ApiKeyInput
                                providerId={provider.id}
                                providerName={provider.name}
                                value={apiKeys[provider.id] || ''}
                                onChange={(val) => updateApiKey(provider.id, val)}
                              />
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Local Runtime Selection */}
      <AnimatePresence>
        {showLocalSection && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <Card className="max-w-5xl">
              <CardContent className="py-6">
                <p className="text-sm font-semibold text-text-primary uppercase tracking-wider mb-4 flex items-center gap-2">
                  <HardDrive className="w-4 h-4 text-neon-cyan" />
                  Select Runtime
                </p>
                <div className="space-y-3">
                  {LOCAL_RUNTIMES.map((rt) => (
                    <button
                      key={rt.id}
                      onClick={() => onRuntimeChange(rt.id)}
                      className={`
                        w-full flex items-center justify-between p-3 rounded-lg border text-left
                        transition-all duration-200
                        ${runtime === rt.id
                          ? 'border-neon-cyan bg-neon-cyan/5 shadow-neon-sm'
                          : 'border-cyber-border hover:border-neon-cyan/30 bg-transparent'
                        }
                      `}
                    >
                      <div>
                        <p className="text-sm font-medium text-text-primary">{rt.name}</p>
                        <p className="text-xs text-text-muted font-mono">{rt.description}</p>
                      </div>
                      <Badge variant={runtime === rt.id ? 'accent' : 'default'}>
                        <span className="font-mono">:{rt.port}</span>
                      </Badge>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ApiKeyInput({
  providerId,
  providerName,
  value,
  onChange,
}: {
  providerId: string;
  providerName: string;
  value: string;
  onChange: (val: string) => void;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="flex items-center gap-2 mb-2">
      <div className="relative flex-1">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`${providerName} API key (${providerId === 'anthropic' ? 'sk-ant-...' : providerId === 'openai' ? 'sk-...' : 'key...'})`}
          className="w-full rounded-lg border border-cyber-border bg-cyber-bg-surface px-4 py-2 text-sm text-text-primary placeholder-text-muted font-mono focus:outline-none focus:ring-2 focus:ring-neon-cyan focus:border-transparent focus:shadow-neon-sm transition-all pr-10"
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors p-1"
        >
          {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}
