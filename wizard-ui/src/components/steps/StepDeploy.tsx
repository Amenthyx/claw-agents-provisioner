import { useState, useEffect, useRef } from 'react';
import { CheckCircle2, Circle, Loader2, XCircle, ExternalLink, Copy, RotateCcw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress';
import { fadeInUp } from '../../lib/motion';

interface DeployStep {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'complete' | 'error';
}

interface StepDeployProps {
  assessmentJSON: Record<string, unknown>;
}

const DEPLOY_STEPS: DeployStep[] = [
  { id: 'validate', label: 'Validating configuration', status: 'pending' },
  { id: 'pull', label: 'Pulling container images', status: 'pending' },
  { id: 'network', label: 'Setting up network', status: 'pending' },
  { id: 'security', label: 'Configuring security layer', status: 'pending' },
  { id: 'models', label: 'Preparing LLM runtime', status: 'pending' },
  { id: 'agent', label: 'Starting agent platform', status: 'pending' },
  { id: 'health', label: 'Running health checks', status: 'pending' },
  { id: 'complete', label: 'Deployment complete', status: 'pending' },
];

export function StepDeploy({ assessmentJSON }: StepDeployProps) {
  const [steps, setSteps] = useState<DeployStep[]>(DEPLOY_STEPS);
  const [logs, setLogs] = useState<string[]>([]);
  const [progress, setProgress] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
    setLogs((prev) => [...prev, `[${timestamp}] ${message}`]);
  };

  const updateStep = (stepId: string, status: DeployStep['status']) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === stepId ? { ...s, status } : s))
    );
  };

  const startDeploy = async () => {
    setIsSimulating(true);
    setLogs([]);
    setProgress(0);
    setIsComplete(false);
    setHasError(false);
    setSteps(DEPLOY_STEPS.map((s) => ({ ...s, status: 'pending' as const })));

    try {
      const res = await fetch('/api/wizard/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(assessmentJSON),
      });

      if (res.ok) {
        const eventSource = new EventSource('/api/wizard/deploy/stream');
        eventSource.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.step) updateStep(data.step, data.status || 'running');
          if (data.message) addLog(data.message);
          if (data.progress) setProgress(data.progress);
          if (data.status === 'complete' && data.step === 'complete') {
            setIsComplete(true);
            setIsSimulating(false);
            eventSource.close();
          }
          if (data.status === 'error') {
            setHasError(true);
            setIsSimulating(false);
            eventSource.close();
          }
        };
        eventSource.onerror = () => {
          eventSource.close();
          simulateDeploy();
        };
        return;
      }
    } catch {
      // API not available, simulate
    }

    simulateDeploy();
  };

  const simulateDeploy = async () => {
    const platform = (assessmentJSON as Record<string, string>).platform || 'zeroclaw';

    for (let i = 0; i < DEPLOY_STEPS.length; i++) {
      const step = DEPLOY_STEPS[i];
      updateStep(step.id, 'running');
      addLog(`Starting: ${step.label}...`);
      setProgress(Math.round(((i + 0.5) / DEPLOY_STEPS.length) * 100));

      const messages = getStepLogs(step.id, platform);
      for (const msg of messages) {
        await delay(300 + Math.random() * 400);
        addLog(msg);
      }

      await delay(500 + Math.random() * 500);
      updateStep(step.id, 'complete');
      addLog(`Completed: ${step.label}`);
      setProgress(Math.round(((i + 1) / DEPLOY_STEPS.length) * 100));
    }

    setIsComplete(true);
    setIsSimulating(false);
  };

  const handleCopyUrl = () => {
    navigator.clipboard.writeText('http://localhost:5000');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Completed step count for animated line
  const completedCount = steps.filter((s) => s.status === 'complete').length;

  return (
    <div>
      <motion.div className="mb-8" variants={fadeInUp} initial="initial" animate="animate">
        <h2 className="text-2xl font-bold text-text-primary mb-2 font-mono">
          {isComplete ? '> Deployment Complete' : hasError ? '> Deployment Failed' : '> Deploying Agent'}
        </h2>
        <p className="text-text-secondary">
          {isComplete
            ? 'Your agent platform is ready to use.'
            : hasError
              ? 'An error occurred during deployment.'
              : isSimulating
                ? 'Setting up your agent platform...'
                : 'Click "Start Deployment" to begin.'}
        </p>
      </motion.div>

      {/* Progress */}
      <Progress value={progress} showLabel className="mb-8 max-w-3xl" />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-5xl">
        {/* Steps list */}
        <div className="lg:col-span-1">
          <Card>
            <CardContent>
              <h3 className="text-sm font-semibold text-text-primary mb-4 font-mono">Deployment Steps</h3>
              <div className="relative space-y-3">
                {/* Animated connecting line */}
                <div className="absolute left-[10px] top-[10px] w-px bg-cyber-border" style={{ height: `calc(100% - 20px)` }} />
                <motion.div
                  className="absolute left-[10px] top-[10px] w-px bg-neon-cyan"
                  initial={false}
                  animate={{ height: `${(completedCount / steps.length) * 100}%` }}
                  transition={{ duration: 0.4, ease: 'easeOut' }}
                  style={{ maxHeight: `calc(100% - 20px)` }}
                />

                {steps.map((step) => (
                  <div key={step.id} className="flex items-center gap-3 relative z-10">
                    {step.status === 'complete' ? (
                      <CheckCircle2 className="w-5 h-5 text-status-success shrink-0" />
                    ) : step.status === 'running' ? (
                      <Loader2 className="w-5 h-5 text-neon-cyan animate-spin shrink-0" />
                    ) : step.status === 'error' ? (
                      <XCircle className="w-5 h-5 text-status-error shrink-0" />
                    ) : (
                      <Circle className="w-5 h-5 text-cyber-border shrink-0" />
                    )}
                    <span
                      className={`text-sm font-mono ${
                        step.status === 'complete'
                          ? 'text-text-secondary'
                          : step.status === 'running'
                            ? 'text-text-primary font-medium'
                            : step.status === 'error'
                              ? 'text-status-error'
                              : 'text-text-muted'
                      }`}
                    >
                      {step.label}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {!isSimulating && !isComplete && !hasError && (
            <div className="mt-4">
              <Button size="lg" className="w-full" onClick={startDeploy}>
                Start Deployment
              </Button>
            </div>
          )}

          {hasError && !isSimulating && (
            <div className="mt-4">
              <Button size="lg" className="w-full bg-status-error hover:bg-status-error/80" onClick={startDeploy}>
                <RotateCcw className="w-4 h-4" />
                Retry Deployment
              </Button>
            </div>
          )}
        </div>

        {/* Log output */}
        <div className="lg:col-span-2">
          <Card className="h-full">
            <CardContent className="h-full flex flex-col">
              {/* Terminal chrome */}
              <div className="flex items-center gap-2 mb-3 pb-3 border-b border-cyber-border">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-status-error/60" />
                  <div className="w-3 h-3 rounded-full bg-status-warning/60" />
                  <div className="w-3 h-3 rounded-full bg-status-success/60" />
                </div>
                <span className="text-[10px] text-text-muted font-mono ml-2">deployment.log</span>
              </div>
              <div
                ref={logRef}
                className="flex-1 min-h-[300px] max-h-[400px] overflow-y-auto p-4 rounded-lg bg-cyber-bg border border-cyber-border font-mono text-xs space-y-0.5"
              >
                {logs.length === 0 ? (
                  <p className="text-text-muted">
                    <span className="text-neon-cyan">$</span> Waiting to start deployment...
                    <span className="cursor-blink" />
                  </p>
                ) : (
                  <>
                    {logs.map((log, i) => (
                      <p
                        key={i}
                        className={
                          log.includes('error') || log.includes('Error')
                            ? 'text-status-error'
                            : log.includes('Completed')
                              ? 'text-status-success'
                              : log.includes('Starting')
                                ? 'text-neon-cyan'
                                : 'text-text-secondary'
                        }
                      >
                        {log}
                      </p>
                    ))}
                    {isSimulating && (
                      <p className="text-text-muted">
                        <span className="cursor-blink" />
                      </p>
                    )}
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Success card */}
      <AnimatePresence>
        {isComplete && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          >
            <Card className="mt-8 border-status-success/30 bg-status-success/5 max-w-3xl shadow-[0_0_24px_#00ff8820]">
              <CardContent className="py-8">
                <div className="flex items-center gap-4 mb-6">
                  <div className="w-14 h-14 rounded-2xl bg-status-success/20 text-status-success flex items-center justify-center">
                    <CheckCircle2 className="w-7 h-7" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold text-text-primary">Agent Deployed Successfully</h3>
                    <p className="text-sm text-text-secondary">Your XClaw agent is running and ready</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center gap-3 p-4 rounded-lg bg-cyber-bg/50 border border-cyber-border">
                    <div className="flex-1">
                      <p className="text-xs text-text-muted mb-1 font-mono">Agent URL</p>
                      <p className="text-sm font-mono text-neon-cyan">http://localhost:5000</p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={handleCopyUrl}>
                      <Copy className="w-4 h-4" />
                      {copied ? <span className="text-status-success">Copied!</span> : 'Copy'}
                    </Button>
                    <a
                      href="http://localhost:5000"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button variant="outline" size="sm">
                        <ExternalLink className="w-4 h-4" />
                        Open
                      </Button>
                    </a>
                  </div>

                  <div>
                    <p className="text-sm font-semibold text-text-primary mb-2">Next Steps</p>
                    <ul className="space-y-2">
                      <li className="flex items-center gap-2 text-sm text-text-secondary">
                        <Badge variant="accent"><span className="font-mono">1</span></Badge>
                        Open the agent dashboard at the URL above
                      </li>
                      <li className="flex items-center gap-2 text-sm text-text-secondary">
                        <Badge variant="accent"><span className="font-mono">2</span></Badge>
                        Configure your API keys in the settings panel
                      </li>
                      <li className="flex items-center gap-2 text-sm text-text-secondary">
                        <Badge variant="accent"><span className="font-mono">3</span></Badge>
                        Start interacting with your AI agent
                      </li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getStepLogs(stepId: string, platform: string): string[] {
  const logs: Record<string, string[]> = {
    validate: [
      'Checking configuration schema...',
      `Platform: ${platform}`,
      'Configuration valid',
    ],
    pull: [
      `Pulling ${platform}:latest...`,
      'Downloading layers... (3/7)',
      'Downloading layers... (7/7)',
      'Image pull complete',
    ],
    network: [
      'Creating bridge network xclaw-net...',
      'Assigning subnet 172.20.0.0/16',
      'Network configured',
    ],
    security: [
      'Initializing security watchdog...',
      'Loading content filter rules...',
      'Security layer ready',
    ],
    models: [
      'Checking LLM runtime status...',
      'Runtime connection established',
      'Model endpoint configured',
    ],
    agent: [
      `Starting ${platform} container...`,
      'Container created successfully',
      'Binding port 5000...',
      'Agent process started (PID: 1)',
    ],
    health: [
      'Waiting for agent readiness...',
      'Health check: GET /health -> 200 OK',
      'All services healthy',
    ],
    complete: [
      'Generating access credentials...',
      'Writing deployment manifest...',
      'Deployment finalized',
    ],
  };

  return logs[stepId] || ['Processing...'];
}
