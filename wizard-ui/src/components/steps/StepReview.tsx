import { useState } from 'react';
import { Edit3, ChevronDown, ChevronUp, Rocket } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import type { WizardState } from '../../lib/types';
import { PLATFORMS, SECURITY_OPTIONS } from '../../lib/types';

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
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-[#e0e0e0] mb-2">Review Configuration</h2>
        <p className="text-[#a0a0a0]">
          Review your selections before deploying. Click "Edit" on any section to make changes.
        </p>
      </div>

      <div className="max-w-3xl space-y-4">
        {/* Platform */}
        <ReviewSection title="Agent Platform" step={1} onEdit={onGoToStep}>
          <div className="flex items-center gap-3">
            <Badge variant="accent">{platform?.name || state.platform}</Badge>
            {platform && (
              <>
                <span className="text-sm text-[#a0a0a0]">{platform.language}</span>
                <span className="text-xs text-[#666]">|</span>
                <span className="text-sm text-[#a0a0a0]">{platform.memory}</span>
                <span className="text-xs text-[#666]">|</span>
                <span className="text-sm text-[#a0a0a0]">Port {platform.port}</span>
              </>
            )}
          </div>
          {platform && (
            <p className="text-sm text-[#666] mt-2">{platform.description}</p>
          )}
        </ReviewSection>

        {/* Deployment */}
        <ReviewSection title="Deployment Method" step={2} onEdit={onGoToStep}>
          <Badge variant="accent">
            {state.deploymentMethod === 'docker' ? 'Docker' : 'Vagrant'}
          </Badge>
          <p className="text-sm text-[#666] mt-2">
            {state.deploymentMethod === 'docker'
              ? 'Containerized deployment with Docker Compose'
              : 'Virtual machine deployment with Vagrant'}
          </p>
        </ReviewSection>

        {/* LLM Provider */}
        <ReviewSection title="LLM Provider" step={3} onEdit={onGoToStep}>
          <Badge variant="accent">
            {state.llmProvider === 'cloud' ? 'Cloud API' : 'Local LLM'}
          </Badge>
          {state.llmProvider === 'local' && state.runtime && (
            <span className="text-sm text-[#a0a0a0] ml-3">
              Runtime: {state.runtime}
            </span>
          )}
        </ReviewSection>

        {/* Models */}
        {state.llmProvider === 'local' && state.selectedModels.length > 0 && (
          <ReviewSection title="Selected Models" step={5} onEdit={onGoToStep}>
            <div className="flex flex-wrap gap-2">
              {state.selectedModels.map((model) => (
                <Badge key={model} variant="accent">{model}</Badge>
              ))}
            </div>
          </ReviewSection>
        )}

        {/* Security */}
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

        {/* Assessment JSON */}
        <Card className="border-[#2a2a4e]">
          <CardContent>
            <button
              className="w-full flex items-center justify-between text-left"
              onClick={() => setShowJSON(!showJSON)}
            >
              <h3 className="text-sm font-semibold text-[#e0e0e0]">Assessment JSON</h3>
              {showJSON ? (
                <ChevronUp className="w-4 h-4 text-[#a0a0a0]" />
              ) : (
                <ChevronDown className="w-4 h-4 text-[#a0a0a0]" />
              )}
            </button>
            {showJSON && (
              <pre className="mt-4 p-4 rounded-lg bg-[#0a0a0f] border border-[#2a2a4e] text-xs text-[#a0a0a0] overflow-x-auto font-mono">
                {JSON.stringify(assessmentJSON, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>

        {/* Deploy button */}
        <div className="pt-6 flex justify-center">
          <Button size="xl" onClick={onDeploy}>
            <Rocket className="w-5 h-5" />
            Deploy Agent
          </Button>
        </div>
      </div>
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
          <h3 className="text-sm font-semibold text-[#e0e0e0]">{title}</h3>
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
