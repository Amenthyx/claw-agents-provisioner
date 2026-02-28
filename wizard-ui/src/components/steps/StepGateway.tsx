import { Network, ArrowRightLeft, Gauge, Router, Radio, Settings } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import type { GatewayConfig } from '../../lib/types';
import { PLATFORMS, FAILOVER_STRATEGIES, ROUTING_MODES, SERVICE_PORTS } from '../../lib/types';
import { staggerContainer, cardVariant, fadeInUp } from '../../lib/motion';

interface StepGatewayProps {
  config: GatewayConfig;
  onChange: (config: GatewayConfig) => void;
  selectedPlatform: string;
}

export function StepGateway({ config, onChange, selectedPlatform }: StepGatewayProps) {
  const platform = PLATFORMS.find((p) => p.id === selectedPlatform);

  return (
    <div>
      <motion.div className="mb-8" variants={fadeInUp} initial="initial" animate="animate">
        <h2 className="text-2xl font-bold text-text-primary mb-2">Gateway Configuration</h2>
        <p className="text-text-secondary">
          Configure the XClaw Router — the OpenAI-compatible proxy that routes requests
          to your agent platform with task detection, failover, and rate limiting.
        </p>
      </motion.div>

      <motion.div
        className="max-w-5xl space-y-6"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        {/* Architecture diagram */}
        <motion.div variants={cardVariant}>
          <Card className="border-neon-cyan/20">
            <CardContent className="py-6">
              <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider mb-4 flex items-center gap-2">
                <Network className="w-4 h-4 text-neon-cyan" />
                Request Flow
              </h3>
              <div className="flex items-center justify-center gap-3 flex-wrap py-4">
                <FlowNode label="Client App" sublabel="Any OpenAI SDK" />
                <ArrowRightLeft className="w-5 h-5 text-neon-cyan shrink-0" />
                <FlowNode label="XClaw Router" sublabel={`Port ${config.port}`} active />
                <ArrowRightLeft className="w-5 h-5 text-neon-cyan shrink-0" />
                <FlowNode label={platform?.name || 'Agent'} sublabel={`Port ${platform?.port || '...'}`} />
              </div>
              <div className="flex items-center justify-center gap-6 mt-3 flex-wrap">
                <span className="text-[10px] font-mono text-text-muted flex items-center gap-1.5">
                  <Radio className="w-3 h-3 text-neon-cyan" />
                  Dashboard :{SERVICE_PORTS.dashboard}
                </span>
                <span className="text-[10px] font-mono text-text-muted flex items-center gap-1.5">
                  <Settings className="w-3 h-3 text-neon-magenta" />
                  Orchestrator :{SERVICE_PORTS.orchestrator}
                </span>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Port + Rate Limit */}
        <motion.div variants={cardVariant}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardContent className="py-5">
                <div className="flex items-center gap-2 mb-4">
                  <Router className="w-4 h-4 text-neon-cyan" />
                  <h3 className="text-sm font-semibold text-text-primary">Gateway Port</h3>
                </div>
                <div className="relative">
                  <input
                    type="number"
                    min={1024}
                    max={65535}
                    value={config.port}
                    onChange={(e) => onChange({ ...config, port: parseInt(e.target.value) || 9095 })}
                    className="w-full rounded-lg border border-cyber-border bg-cyber-bg-surface px-4 py-2.5 text-sm text-text-primary font-mono focus:outline-none focus:ring-2 focus:ring-neon-cyan focus:border-transparent focus:shadow-neon-sm transition-all"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-text-muted font-mono">
                    TCP
                  </span>
                </div>
                <p className="text-[11px] text-text-muted mt-2 font-mono">
                  OpenAI-compatible endpoint at http://localhost:{config.port}/v1
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="py-5">
                <div className="flex items-center gap-2 mb-4">
                  <Gauge className="w-4 h-4 text-neon-cyan" />
                  <h3 className="text-sm font-semibold text-text-primary">Rate Limit</h3>
                </div>
                <div className="relative">
                  <input
                    type="number"
                    min={1}
                    max={10000}
                    value={config.rateLimit}
                    onChange={(e) => onChange({ ...config, rateLimit: parseInt(e.target.value) || 120 })}
                    className="w-full rounded-lg border border-cyber-border bg-cyber-bg-surface px-4 py-2.5 text-sm text-text-primary font-mono focus:outline-none focus:ring-2 focus:ring-neon-cyan focus:border-transparent focus:shadow-neon-sm transition-all"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-text-muted font-mono">
                    RPM
                  </span>
                </div>
                <p className="text-[11px] text-text-muted mt-2 font-mono">
                  Token bucket algorithm, 60s sliding window
                </p>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        {/* Failover Strategy */}
        <motion.div variants={cardVariant}>
          <Card>
            <CardContent className="py-6">
              <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider mb-4 flex items-center gap-2">
                <ArrowRightLeft className="w-4 h-4 text-neon-cyan" />
                Failover Strategy
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {FAILOVER_STRATEGIES.map((strategy) => (
                  <button
                    key={strategy.id}
                    onClick={() => onChange({ ...config, failover: strategy.id })}
                    className={`
                      p-4 rounded-lg border text-left transition-all duration-200
                      ${config.failover === strategy.id
                        ? 'border-neon-cyan bg-neon-cyan/5 shadow-neon-sm'
                        : 'border-cyber-border hover:border-neon-cyan/30 bg-transparent'
                      }
                    `}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <p className="text-sm font-medium text-text-primary">{strategy.name}</p>
                      {config.failover === strategy.id && <Badge variant="accent">Active</Badge>}
                    </div>
                    <p className="text-xs text-text-muted leading-relaxed">{strategy.description}</p>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Routing Mode */}
        <motion.div variants={cardVariant}>
          <Card>
            <CardContent className="py-6">
              <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider mb-4 flex items-center gap-2">
                <Network className="w-4 h-4 text-neon-cyan" />
                Routing Mode
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {ROUTING_MODES.map((mode) => (
                  <button
                    key={mode.id}
                    onClick={() => onChange({ ...config, routing: mode.id })}
                    className={`
                      p-4 rounded-lg border text-left transition-all duration-200
                      ${config.routing === mode.id
                        ? 'border-neon-cyan bg-neon-cyan/5 shadow-neon-sm'
                        : 'border-cyber-border hover:border-neon-cyan/30 bg-transparent'
                      }
                    `}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <p className="text-sm font-medium text-text-primary">{mode.name}</p>
                      {config.routing === mode.id && <Badge variant="accent">Active</Badge>}
                    </div>
                    <p className="text-xs text-text-muted leading-relaxed">{mode.description}</p>
                  </button>
                ))}
              </div>
              {config.routing === 'auto' && (
                <div className="mt-4 p-3 rounded-lg bg-cyber-bg-surface border border-cyber-border">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-2 font-mono">
                    Auto-detected task categories
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {['coding', 'reasoning', 'creative', 'translation', 'summarization', 'data_analysis'].map((cat) => (
                      <span key={cat} className="text-[10px] px-2 py-0.5 rounded bg-cyber-bg text-text-secondary border border-cyber-border font-mono">
                        {cat}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </div>
  );
}

function FlowNode({ label, sublabel, active }: { label: string; sublabel: string; active?: boolean }) {
  return (
    <div
      className={`
        flex flex-col items-center justify-center px-5 py-3 rounded-lg border font-mono text-center min-w-[120px]
        ${active
          ? 'border-neon-cyan bg-neon-cyan/10 text-neon-cyan shadow-neon-sm'
          : 'border-cyber-border bg-cyber-bg-surface text-text-secondary'
        }
      `}
    >
      <span className="text-sm font-semibold">{label}</span>
      <span className={`text-[10px] ${active ? 'text-neon-cyan-dim' : 'text-text-muted'}`}>{sublabel}</span>
    </div>
  );
}
