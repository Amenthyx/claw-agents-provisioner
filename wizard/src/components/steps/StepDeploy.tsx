import { useEffect, useRef } from 'react';
import {
  Play, CheckCircle2, Circle, Loader2, XCircle,
  ExternalLink, Copy, ArrowRight,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useWizard } from '../../state/context';
import { useDeploy } from '../../hooks/useDeploy';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { fadeInUp } from '../../lib/motion';
import { ArchitectureDiagram } from './ArchitectureDiagram';

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'complete':
    case 'healthy':
      return <CheckCircle2 size={16} className="text-success" />;
    case 'running':
      return <Loader2 size={16} className="text-accent animate-spin" />;
    case 'error':
    case 'unhealthy':
      return <XCircle size={16} className="text-error" />;
    default:
      return <Circle size={16} className="text-text-muted" />;
  }
}

const DEFAULT_ENDPOINTS = [
  { name: 'Agent Platform', url: 'http://localhost:3100' },
  { name: 'Gateway Router', url: 'http://localhost:9095' },
  { name: 'Optimizer', url: 'http://localhost:9091' },
  { name: 'Dashboard', url: 'http://localhost:9099' },
  { name: 'Watchdog', url: 'http://localhost:9097' },
];

export function StepDeploy() {
  const { state, assessmentJSON } = useWizard();
  const {
    steps, healthChecks, logs, isDeploying, isDone, hasError,
    endpoints: liveEndpoints, startDeploy, cleanup,
  } = useDeploy();
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleStart = () => {
    startDeploy(assessmentJSON);
  };

  const copyEndpoint = async (url: string) => {
    await navigator.clipboard.writeText(url);
  };

  const displayEndpoints = liveEndpoints.length > 0 ? liveEndpoints : DEFAULT_ENDPOINTS;

  // Pre-deploy state
  if (!isDeploying && !isDone && !hasError) {
    return (
      <motion.div
        variants={fadeInUp}
        initial="initial"
        animate="animate"
        className="flex flex-col items-center justify-center py-16 text-center"
      >
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 text-accent mb-5">
          <Play size={28} />
        </div>
        <h3 className="text-lg font-medium text-text-primary">Ready to Deploy</h3>
        <p className="text-sm text-text-secondary mt-2 max-w-sm">
          Deploy <span className="font-medium text-text-primary">{state.agentName}</span> with
          your configuration. This will provision all services and run health checks.
        </p>
        <Button size="lg" className="mt-8" onClick={handleStart} icon={<Play size={16} />}>
          Start Deployment
        </Button>
      </motion.div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-[220px_1fr] gap-6">
        {/* Step List */}
        <div className="space-y-1">
          {steps.map((s, i) => (
            <div
              key={i}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm"
            >
              <StatusIcon status={s.status} />
              <span className={s.status === 'running' ? 'text-text-primary font-medium' : 'text-text-secondary'}>
                {s.label}
              </span>
            </div>
          ))}
        </div>

        {/* Log Output */}
        <Card className="h-[360px] overflow-hidden p-0">
          <div className="flex items-center justify-between border-b border-border-base px-4 py-2">
            <span className="text-xs font-medium text-text-muted">Deployment Logs</span>
            {isDeploying && (
              <span className="flex items-center gap-1.5 text-xs text-accent">
                <Loader2 size={12} className="animate-spin" />
                Running
              </span>
            )}
          </div>
          <div className="h-[calc(100%-36px)] overflow-y-auto p-4 font-mono text-xs text-text-secondary leading-relaxed">
            {logs.map((log, i) => (
              <div key={i} className="whitespace-pre-wrap">{log}</div>
            ))}
            <div ref={logEndRef} />
          </div>
        </Card>
      </div>

      {/* Health Checks */}
      {(isDone || healthChecks.some((h) => h.status !== 'pending')) && (
        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-3">Service Health</h3>
          <div className="grid grid-cols-2 gap-3">
            {healthChecks.map((hc) => (
              <div
                key={hc.name}
                className="flex items-center gap-2.5 rounded-lg border border-border-base bg-surface-0 px-3 py-2"
              >
                <StatusIcon status={hc.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-text-primary truncate">{hc.name}</p>
                  <p className="text-xs text-text-muted truncate">{hc.endpoint}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Success State */}
      {isDone && (
        <motion.div variants={fadeInUp} initial="initial" animate="animate" className="space-y-6">
          <Card className="border-success/20 bg-success/[0.03] text-center py-6">
            <CheckCircle2 size={32} className="mx-auto text-success mb-3" />
            <h3 className="text-lg font-medium text-text-primary">Deployment Complete</h3>
            <p className="text-sm text-text-secondary mt-1">
              <span className="font-medium text-text-primary">{state.agentName}</span> is running and healthy.
            </p>
          </Card>

          {/* Architecture Diagram */}
          <ArchitectureDiagram state={state} />

          <div>
            <h3 className="text-sm font-medium text-text-primary mb-3">Service Endpoints</h3>
            <div className="space-y-2">
              {displayEndpoints.map((ep) => (
                <div
                  key={ep.name}
                  className="flex items-center justify-between rounded-lg border border-border-base bg-surface-1 px-4 py-3"
                >
                  <div>
                    <p className="text-sm text-text-primary">{ep.name}</p>
                    <p className="text-xs font-mono text-text-muted">{ep.url}</p>
                  </div>
                  <div className="flex gap-1.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<Copy size={14} />}
                      onClick={() => copyEndpoint(ep.url)}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<ExternalLink size={14} />}
                      onClick={() => window.open(ep.url, '_blank')}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <Card>
            <h3 className="text-sm font-medium text-text-primary mb-3">Next Steps</h3>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li className="flex items-center gap-2">
                <ArrowRight size={14} className="text-accent shrink-0" />
                Open the Dashboard to manage your agent fleet
              </li>
              <li className="flex items-center gap-2">
                <ArrowRight size={14} className="text-accent shrink-0" />
                Configure API keys in the Gateway settings
              </li>
              <li className="flex items-center gap-2">
                <ArrowRight size={14} className="text-accent shrink-0" />
                Review security policies in the compliance panel
              </li>
            </ul>
          </Card>
        </motion.div>
      )}

      {/* Error State */}
      {hasError && (
        <Card className="border-error/20 bg-error/[0.03] text-center py-6">
          <XCircle size={32} className="mx-auto text-error mb-3" />
          <h3 className="text-lg font-medium text-text-primary">Deployment Failed</h3>
          <p className="text-sm text-text-secondary mt-1">Check the logs above for details.</p>
          <Button variant="outline" className="mt-4" onClick={handleStart}>
            Retry Deployment
          </Button>
        </Card>
      )}
    </div>
  );
}
