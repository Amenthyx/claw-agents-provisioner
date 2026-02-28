import { useState } from 'react';
import { Edit3, ChevronDown, ChevronUp, Rocket, Key, Router } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import type { WizardState } from '../../lib/types';
import { PLATFORMS, SECURITY_OPTIONS, CLOUD_PROVIDERS, FAILOVER_STRATEGIES, ROUTING_MODES } from '../../lib/types';
import { staggerContainer, cardVariant, fadeInUp } from '../../lib/motion';

interface StepReviewProps {
  state: WizardState;
  assessmentJSON: Record<string, unknown>;
  onGoToStep: (step: number) => void;
  onDeploy: () => void;
}

export function StepReview({ state, assessmentJSON, onGoToStep, onDeploy }: StepReviewProps) {
  const [showJSON, setShowJSON] = useState(false);

  const platform = PLATFORMS.find((p) => p.id === state.platform);

  return (
    <div>
      <motion.div className="mb-8" variants={fadeInUp} initial="initial" animate="animate">
        <h2 className="text-2xl font-bold text-text-primary mb-2">Review Configuration</h2>
        <p className="text-text-secondary">
          Review your selections before deploying. Click "Edit" on any section to make changes.
        </p>
      </motion.div>

      <motion.div
        className="max-w-3xl space-y-4"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        {/* Platform */}
        <motion.div variants={cardVariant}>
          <ReviewSection title="Agent Platform" step={1} onEdit={onGoToStep}>
            <div className="flex items-center gap-3">
              <Badge variant="accent">{platform?.name || state.platform}</Badge>
              {platform && (
                <>
                  <span className="text-sm text-text-secondary font-mono">{platform.language}</span>
                  <span className="text-xs text-text-muted">|</span>
                  <span className="text-sm text-text-secondary font-mono">{platform.memory}</span>
                  <span className="text-xs text-text-muted">|</span>
                  <span className="text-sm text-text-secondary font-mono">Port {platform.port}</span>
                </>
              )}
            </div>
            {platform && (
              <p className="text-sm text-text-muted mt-2">{platform.description}</p>
            )}
          </ReviewSection>
        </motion.div>

        {/* Deployment */}
        <motion.div variants={cardVariant}>
          <ReviewSection title="Deployment Method" step={2} onEdit={onGoToStep}>
            <Badge variant="accent">
              {state.deploymentMethod === 'docker' ? 'Docker' : state.deploymentMethod === 'vagrant' ? 'Vagrant' : 'Local Hardware'}
            </Badge>
            <p className="text-sm text-text-muted mt-2">
              {state.deploymentMethod === 'docker'
                ? 'Containerized deployment with Docker Compose'
                : state.deploymentMethod === 'vagrant'
                  ? 'Virtual machine deployment with Vagrant'
                  : 'Direct installation on local hardware'}
            </p>
          </ReviewSection>
        </motion.div>

        {/* LLM Provider */}
        <motion.div variants={cardVariant}>
          <ReviewSection title="LLM Provider" step={3} onEdit={onGoToStep}>
            <Badge variant="accent">
              {state.llmProvider === 'cloud' ? 'Cloud API' : state.llmProvider === 'local' ? 'Local LLM' : 'Hybrid'}
            </Badge>
            {(state.llmProvider === 'local' || state.llmProvider === 'hybrid') && state.runtime && (
              <span className="text-sm text-text-secondary ml-3 font-mono">
                Runtime: {state.runtime}
              </span>
            )}
            {/* Cloud providers */}
            {(state.llmProvider === 'cloud' || state.llmProvider === 'hybrid') && state.cloudProviders.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {state.cloudProviders.map((id) => {
                  const provider = CLOUD_PROVIDERS.find((p) => p.id === id);
                  return <Badge key={id}>{provider?.name || id}</Badge>;
                })}
              </div>
            )}
            {/* API Keys (redacted) */}
            {Object.keys(state.apiKeys).length > 0 && (
              <div className="flex items-center gap-2 mt-2">
                <Key className="w-3 h-3 text-neon-cyan" />
                <span className="text-xs text-text-muted font-mono">
                  {Object.keys(state.apiKeys).filter(k => state.apiKeys[k]).length} API key(s) configured
                </span>
              </div>
            )}
          </ReviewSection>
        </motion.div>

        {/* Models */}
        {(state.llmProvider === 'local' || state.llmProvider === 'hybrid') && state.selectedModels.length > 0 && (
          <motion.div variants={cardVariant}>
            <ReviewSection title="Selected Models" step={5} onEdit={onGoToStep}>
              <div className="flex flex-wrap gap-2">
                {state.selectedModels.map((model) => (
                  <Badge key={model} variant="accent"><span className="font-mono">{model}</span></Badge>
                ))}
              </div>
            </ReviewSection>
          </motion.div>
        )}

        {/* Security */}
        <motion.div variants={cardVariant}>
          <ReviewSection title="Security" step={6} onEdit={onGoToStep}>
            <Badge variant={state.securityEnabled ? 'success' : 'warning'}>
              {state.securityEnabled ? 'Enabled' : 'Disabled'}
            </Badge>
            {state.securityEnabled && state.securityFeatures.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {state.securityFeatures.map((f) => {
                  const opt = SECURITY_OPTIONS.find((o) => o.id === f);
                  return <Badge key={f}>{opt?.label || f}</Badge>;
                })}
              </div>
            )}
          </ReviewSection>
        </motion.div>

        {/* Gateway */}
        <motion.div variants={cardVariant}>
          <ReviewSection title="Gateway" step={7} onEdit={onGoToStep}>
            <div className="flex items-center gap-3 flex-wrap">
              <Router className="w-4 h-4 text-neon-cyan" />
              <Badge variant="accent">
                <span className="font-mono">:{state.gateway.port}</span>
              </Badge>
              <span className="text-xs text-text-muted">|</span>
              <Badge>
                {FAILOVER_STRATEGIES.find((f) => f.id === state.gateway.failover)?.name || state.gateway.failover}
              </Badge>
              <span className="text-xs text-text-muted">|</span>
              <Badge>
                {ROUTING_MODES.find((r) => r.id === state.gateway.routing)?.name || state.gateway.routing}
              </Badge>
              <span className="text-xs text-text-muted">|</span>
              <span className="text-xs text-text-muted font-mono">{state.gateway.rateLimit} RPM</span>
            </div>
          </ReviewSection>
        </motion.div>

        {/* Assessment JSON */}
        <motion.div variants={cardVariant}>
          <Card className="border-cyber-border">
            <CardContent>
              <button
                className="w-full flex items-center justify-between text-left"
                onClick={() => setShowJSON(!showJSON)}
              >
                <h3 className="text-sm font-semibold text-text-primary font-mono">Assessment JSON</h3>
                {showJSON ? (
                  <ChevronUp className="w-4 h-4 text-text-secondary" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-text-secondary" />
                )}
              </button>
              {showJSON && (
                <div className="mt-4 rounded-lg glass-card border border-cyber-border overflow-hidden">
                  {/* Terminal chrome */}
                  <div className="flex items-center gap-2 px-4 py-2 border-b border-cyber-border">
                    <div className="w-3 h-3 rounded-full bg-status-error/60" />
                    <div className="w-3 h-3 rounded-full bg-status-warning/60" />
                    <div className="w-3 h-3 rounded-full bg-status-success/60" />
                    <span className="text-[10px] text-text-muted font-mono ml-2">assessment.json</span>
                  </div>
                  <pre className="p-4 text-xs text-text-secondary overflow-x-auto font-mono bg-cyber-bg/80">
                    {JSON.stringify(assessmentJSON, null, 2)}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Deploy button */}
        <motion.div className="pt-6 flex justify-center" variants={cardVariant}>
          <Button
            size="xl"
            onClick={onDeploy}
            className="bg-gradient-to-r from-neon-cyan to-neon-magenta text-cyber-bg font-semibold shadow-neon-lg hover:shadow-neon-lg active:scale-[0.97]"
          >
            <Rocket className="w-5 h-5" />
            Deploy Agent
          </Button>
        </motion.div>
      </motion.div>
    </div>
  );
}

function ReviewSection({
  title,
  step,
  onEdit,
  children,
}: {
  title: string;
  step: number;
  onEdit: (step: number) => void;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardContent>
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
          <Button variant="ghost" size="sm" onClick={() => onEdit(step)}>
            <Edit3 className="w-3 h-3" />
            Edit
          </Button>
        </div>
        {children}
      </CardContent>
    </Card>
  );
}
