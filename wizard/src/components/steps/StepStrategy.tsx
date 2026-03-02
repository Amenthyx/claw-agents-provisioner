import { useMemo } from 'react';
import {
  DollarSign, Zap, Award, Scale, Wand2,
  MessageSquare, Brain, Code, Pen, BarChart3, Languages,
  ArrowRightLeft, ChevronDown, Network,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useWizard } from '../../state/context';
import { MODELS } from '../../data/models';
import { CLOUD_MODELS, TASK_CATEGORIES, suggestRules, getModelDisplayName } from '../../data/strategy';
import type { TaskCategory } from '../../data/strategy';
import type { OptimizationPreset } from '../../state/types';
import { SelectionCard } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Input } from '../ui/Input';
import { stagger, fadeInUp, fadeIn } from '../../lib/motion';

/* ── Optimization presets ──────────────────────────────────── */

const PRESETS: { id: OptimizationPreset; name: string; icon: typeof DollarSign; desc: string }[] = [
  { id: 'cost', name: 'Cost', icon: DollarSign, desc: 'Minimize API spend — prefer local models' },
  { id: 'speed', name: 'Speed', icon: Zap, desc: 'Minimize latency — prefer fast models' },
  { id: 'quality', name: 'Quality', icon: Award, desc: 'Best output — prefer powerful models' },
  { id: 'balanced', name: 'Balanced', icon: Scale, desc: 'Mix of cost, speed, and quality' },
];

/* ── Task category icons ───────────────────────────────────── */

const TASK_ICONS: Record<string, typeof MessageSquare> = {
  chat: MessageSquare,
  reasoning: Brain,
  coding: Code,
  creative: Pen,
  analysis: BarChart3,
  translation: Languages,
};

/* ── Model select dropdown ─────────────────────────────────── */

function ModelSelect({
  value,
  onChange,
  selectedModels,
  cloudProviders,
  label,
}: {
  value: string;
  onChange: (id: string) => void;
  selectedModels: string[];
  cloudProviders: string[];
  label: string;
}) {
  const localModels = selectedModels
    .map((id) => MODELS.find((m) => m.id === id))
    .filter((m) => m != null);

  const cloudGroups = cloudProviders
    .map((p) => ({
      provider: p,
      models: CLOUD_MODELS[p] ?? [],
    }))
    .filter((g) => g.models.length > 0);

  return (
    <div className="space-y-1">
      <label className="block text-xs font-medium text-text-secondary">{label}</label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none rounded-lg border border-border-base bg-surface-2 px-3 py-2 pr-8 text-sm text-text-primary transition-colors focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/30"
        >
          <option value="">— None —</option>

          {localModels.length > 0 && (
            <optgroup label="Local Models">
              {localModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.parameters})
                </option>
              ))}
            </optgroup>
          )}

          {cloudGroups.map((g) => (
            <optgroup key={g.provider} label={g.provider.charAt(0).toUpperCase() + g.provider.slice(1)}>
              {g.models.map((cm) => (
                <option key={cm.id} value={cm.id}>
                  {cm.name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <ChevronDown
          size={14}
          className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted"
        />
      </div>
    </div>
  );
}

/* ── Task rule card ────────────────────────────────────────── */

function TaskRuleCard({
  task,
  primaryModel,
  fallbackModel,
  selectedModels,
  cloudProviders,
  onPrimaryChange,
  onFallbackChange,
}: {
  task: TaskCategory;
  primaryModel: string;
  fallbackModel: string;
  selectedModels: string[];
  cloudProviders: string[];
  onPrimaryChange: (id: string) => void;
  onFallbackChange: (id: string) => void;
}) {
  const Icon = TASK_ICONS[task.id] ?? MessageSquare;
  const primaryName = getModelDisplayName(primaryModel, MODELS);
  const fallbackName = getModelDisplayName(fallbackModel, MODELS);
  const isConfigured = primaryModel !== '';

  return (
    <div className="rounded-xl border border-border-base bg-surface-1 p-4 space-y-3">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-3 text-text-muted shrink-0">
          <Icon size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-medium text-text-primary">{task.label}</h4>
            {isConfigured ? (
              <Badge variant="accent">Configured</Badge>
            ) : (
              <Badge variant="muted">Not set</Badge>
            )}
          </div>
          <p className="text-xs text-text-muted mt-0.5">{task.description}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <ModelSelect
          value={primaryModel}
          onChange={onPrimaryChange}
          selectedModels={selectedModels}
          cloudProviders={cloudProviders}
          label="Primary Model"
        />
        <ModelSelect
          value={fallbackModel}
          onChange={onFallbackChange}
          selectedModels={selectedModels}
          cloudProviders={cloudProviders}
          label="Fallback Model"
        />
      </div>

      {isConfigured && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <ArrowRightLeft size={12} />
          <span>
            {primaryName}
            {fallbackModel ? ` → ${fallbackName} (fallback)` : ' (no fallback)'}
          </span>
        </div>
      )}
    </div>
  );
}

/* ── Main component ────────────────────────────────────────── */

export function StepStrategy() {
  const { state, setStrategyOptimization, setStrategyRule, setStrategyRules, setGateway } = useWizard();
  const gw = state.gateway;
  const portValid = gw.port >= 1024 && gw.port <= 65535;

  const hasLocalModels = state.selectedModels.length > 0;
  const hasCloudProviders = state.cloudProviders.length > 0;
  const hasAnyModels = hasLocalModels || hasCloudProviders;

  // Build a rule lookup for quick access
  const ruleMap = useMemo(() => {
    const map: Record<string, { primary: string; fallback: string }> = {};
    for (const r of state.strategy.rules) {
      map[r.taskCategory] = { primary: r.primaryModel, fallback: r.fallbackModel };
    }
    return map;
  }, [state.strategy.rules]);

  const configuredCount = state.strategy.rules.filter((r) => r.primaryModel !== '').length;

  const handleAutoSuggest = () => {
    const rules = suggestRules(
      state.selectedModels,
      state.cloudProviders,
      state.strategy.optimization,
      MODELS,
    );
    setStrategyRules(rules);
  };

  if (!hasAnyModels) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent mb-4">
          <Scale size={24} />
        </div>
        <h3 className="text-lg font-medium text-text-primary">No Models Available</h3>
        <p className="text-sm text-text-secondary mt-2 max-w-sm">
          Go back to select local models or configure cloud providers first.
          The strategy page maps task types to specific models.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Optimization Preset */}
      <motion.div variants={stagger} initial="initial" animate="animate" className="grid grid-cols-4 gap-3">
        {PRESETS.map((p) => {
          const selected = state.strategy.optimization === p.id;
          return (
            <motion.div key={p.id} variants={fadeInUp}>
              <SelectionCard
                selected={selected}
                onClick={() => setStrategyOptimization(p.id)}
                className="text-center h-full"
              >
                <p.icon size={20} className={`mx-auto ${selected ? 'text-accent' : 'text-text-muted'}`} />
                <h3 className="text-sm font-medium text-text-primary mt-2">{p.name}</h3>
                <p className="text-xs text-text-secondary mt-1">{p.desc}</p>
              </SelectionCard>
            </motion.div>
          );
        })}
      </motion.div>

      {/* Auto-Suggest + Summary */}
      <motion.div variants={fadeIn} initial="initial" animate="animate">
        <div className="rounded-xl border border-border-base bg-surface-1 p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-text-primary">XClaw Optimization Engine</h3>
              <p className="text-xs text-text-muted mt-0.5">
                Auto-configure task routing based on your models and optimization preference.
                {configuredCount > 0 && (
                  <span className="text-accent ml-1">
                    {configuredCount}/{TASK_CATEGORIES.length} tasks configured
                  </span>
                )}
              </p>
            </div>
            <button
              onClick={handleAutoSuggest}
              className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90"
            >
              <Wand2 size={14} />
              Auto-Suggest
            </button>
          </div>

          {/* Available models summary */}
          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border-base">
            {hasLocalModels && (
              <Badge variant="secondary">
                {state.selectedModels.length} local model{state.selectedModels.length > 1 ? 's' : ''}
              </Badge>
            )}
            {state.cloudProviders.map((p) => (
              <Badge key={p} variant="default">
                {p.charAt(0).toUpperCase() + p.slice(1)} ({(CLOUD_MODELS[p] ?? []).length} models)
              </Badge>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Task Routing Rules */}
      <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-3">
        <h3 className="text-sm font-medium text-text-primary">Task Routing</h3>
        <p className="text-xs text-text-muted">
          Map each task type to a primary model and an optional fallback.
          XClaw will route requests to the appropriate model based on task classification.
        </p>
        {TASK_CATEGORIES.map((task) => {
          const rule = ruleMap[task.id];
          return (
            <motion.div key={task.id} variants={fadeInUp}>
              <TaskRuleCard
                task={task}
                primaryModel={rule?.primary ?? ''}
                fallbackModel={rule?.fallback ?? ''}
                selectedModels={state.selectedModels}
                cloudProviders={state.cloudProviders}
                onPrimaryChange={(id) =>
                  setStrategyRule(task.id, id, rule?.fallback ?? '')
                }
                onFallbackChange={(id) =>
                  setStrategyRule(task.id, rule?.primary ?? '', id)
                }
              />
            </motion.div>
          );
        })}
      </motion.div>

      {/* Gateway Settings */}
      <motion.div variants={fadeInUp} initial="initial" animate="animate">
        <div className="rounded-xl border border-border-base bg-surface-1 p-4 space-y-4">
          <div className="flex items-center gap-2">
            <Network size={16} className="text-text-muted" />
            <h3 className="text-sm font-medium text-text-primary">Gateway Settings</h3>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Gateway Port"
              type="number"
              value={String(gw.port)}
              onChange={(e) => setGateway({ port: parseInt(e.target.value) || 0 })}
              error={!portValid ? 'Port must be 1024–65535' : undefined}
              hint="XClaw router listen port"
            />
            <Input
              label="Rate Limit (RPM)"
              type="number"
              value={String(gw.rateLimit)}
              onChange={(e) => setGateway({ rateLimit: Math.max(1, Math.min(10000, parseInt(e.target.value) || 1)) })}
              hint="Max requests per minute"
            />
          </div>
        </div>
      </motion.div>

      {/* Strategy Tips */}
      <div className="rounded-xl border border-border-base bg-surface-1/50 p-4 space-y-2">
        <h4 className="text-xs font-medium text-text-secondary">Strategy Tips</h4>
        <ul className="text-xs text-text-muted space-y-1 list-disc list-inside">
          <li>Use fast/cheap models (Haiku, GPT-4o Mini, small local) for simple chat and translation</li>
          <li>Reserve powerful models (Opus, o1, large local) for reasoning and complex coding</li>
          <li>Mix local + cloud for reliability: local as primary, cloud as fallback (or vice versa)</li>
          <li>XClaw auto-classifies incoming requests and routes to the assigned model</li>
        </ul>
      </div>
    </div>
  );
}
