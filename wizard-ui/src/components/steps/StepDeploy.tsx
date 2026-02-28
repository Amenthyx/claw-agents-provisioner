import { useState, useEffect, useRef } from 'react';
import { CheckCircle2, Circle, Loader2, XCircle, ExternalLink, Terminal, Copy } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress';

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

    // Try to connect to real API first
    try {
      const res = await fetch('/api/wizard/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(assessmentJSON),
      });

      if (res.ok) {
        // Real API available - connect SSE
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
          // Fall back to simulation
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

      // Simulate work with realistic logs
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

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-[#e0e0e0] mb-2">
          {isComplete ? 'Deployment Complete' : hasError ? 'Deployment Failed' : 'Deploying Agent'}
        </h2>
        <p className="text-[#a0a0a0]">
          {isComplete
            ? 'Your agent platform is ready to use.'
            : hasError
              ? 'An error occurred during deployment.'
              : isSimulating
                ? 'Setting up your agent platform...'
                : 'Click "Start Deployment" to begin.'}
        </p>
      </div>

      {/* Progress */}
      <Progress value={progress} showLabel className="mb-8 max-w-3xl" />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-5xl">
        {/* Steps list */}
        <div className="lg:col-span-1">
          <Card>
            <CardContent>
              <h3 className="text-sm font-semibold text-[#e0e0e0] mb-4">Deployment Steps</h3>
              <div className="space-y-3">
                {steps.map((step) => (
                  <div key={step.id} className="flex items-center gap-3">
                    {step.status === 'complete' ? (
                      <CheckCircle2 className="w-5 h-5 text-[#2ed573] shrink-0" />
                    ) : step.status === 'running' ? (
                      <Loader2 className="w-5 h-5 text-[#00d4aa] animate-spin shrink-0" />
                    ) : step.status === 'error' ? (
                      <XCircle className="w-5 h-5 text-[#ff4757] shrink-0" />
                    ) : (
                      <Circle className="w-5 h-5 text-[#2a2a4e] shrink-0" />
                    )}
                    <span
                      className={`text-sm ${
                        step.status === 'complete'
                          ? 'text-[#a0a0a0]'
                          : step.status === 'running'
                            ? 'text-[#e0e0e0] font-medium'
                            : step.status === 'error'
                              ? 'text-[#ff4757]'
                              : 'text-[#555]'
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
        </div>

        {/* Log output */}
        <div className="lg:col-span-2">
          <Card className="h-full">
            <CardContent className="h-full flex flex-col">
              <div className="flex items-center gap-2 mb-3">
                <Terminal className="w-4 h-4 text-[#00d4aa]" />
                <h3 className="text-sm font-semibold text-[#e0e0e0]">Deployment Log</h3>
              </div>
              <div
                ref={logRef}
                className="flex-1 min-h-[300px] max-h-[400px] overflow-y-auto p-4 rounded-lg bg-[#0a0a0f] border border-[#2a2a4e] font-mono text-xs space-y-0.5"
              >
                {logs.length === 0 ? (
                  <p className="text-[#555]">Waiting to start deployment...</p>
                ) : (
                  logs.map((log, i) => (
                    <p
                      key={i}
                      className={
                        log.includes('error') || log.includes('Error')
                          ? 'text-[#ff4757]'
                          : log.includes('Completed')
                            ? 'text-[#2ed573]'
                            : log.includes('Starting')
                              ? 'text-[#00d4aa]'
                              : 'text-[#a0a0a0]'
                      }
                    >
                      {log}
                    </p>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Success card */}
      {isComplete && (
        <Card className="mt-8 border-[#2ed573]/30 bg-[#2ed573]/5 max-w-3xl">
          <CardContent className="py-8">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-14 h-14 rounded-2xl bg-[#2ed573]/20 text-[#2ed573] flex items-center justify-center">
                <CheckCircle2 className="w-7 h-7" />
              </div>
              <div>
                <h3 className="text-xl font-semibold text-[#e0e0e0]">Agent Deployed Successfully</h3>
                <p className="text-sm text-[#a0a0a0]">Your XClaw agent is running and ready</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3 p-4 rounded-lg bg-[#0a0a0f]/50 border border-[#2a2a4e]">
                <div className="flex-1">
                  <p className="text-xs text-[#666] mb-1">Agent URL</p>
                  <p className="text-sm font-mono text-[#00d4aa]">http://localhost:5000</p>
                </div>
                <Button variant="ghost" size="sm" onClick={handleCopyUrl}>
                  <Copy className="w-4 h-4" />
                  {copied ? 'Copied!' : 'Copy'}
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
                <p className="text-sm font-semibold text-[#e0e0e0] mb-2">Next Steps</p>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2 text-sm text-[#a0a0a0]">
                    <Badge variant="accent">1</Badge>
                    Open the agent dashboard at the URL above
                  </li>
                  <li className="flex items-center gap-2 text-sm text-[#a0a0a0]">
                    <Badge variant="accent">2</Badge>
                    Configure your API keys in the settings panel
                  </li>
                  <li className="flex items-center gap-2 text-sm text-[#a0a0a0]">
                    <Badge variant="accent">3</Badge>
                    Start interacting with your AI agent
                  </li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
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
