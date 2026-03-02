import type { ModelInfo } from '../state/types';
import type { StrategyRule, OptimizationPreset } from '../state/types';

/* ── Cloud sub-models per provider ─────────────────────────── */

export interface CloudModel {
  id: string;
  name: string;
  tier: 'fast' | 'balanced' | 'quality';
  specialization?: 'coding' | 'reasoning';
}

export const CLOUD_MODELS: Record<string, CloudModel[]> = {
  anthropic: [
    { id: 'anthropic:haiku', name: 'Claude Haiku 4.5', tier: 'fast' },
    { id: 'anthropic:sonnet', name: 'Claude Sonnet 4.6', tier: 'balanced' },
    { id: 'anthropic:opus', name: 'Claude Opus 4.6', tier: 'quality' },
  ],
  openai: [
    { id: 'openai:gpt4o-mini', name: 'GPT-4o Mini', tier: 'fast' },
    { id: 'openai:gpt4o', name: 'GPT-4o', tier: 'balanced' },
    { id: 'openai:o1', name: 'o1', tier: 'quality', specialization: 'reasoning' },
  ],
  deepseek: [
    { id: 'deepseek:chat', name: 'DeepSeek Chat', tier: 'fast' },
    { id: 'deepseek:v3', name: 'DeepSeek V3', tier: 'balanced' },
    { id: 'deepseek:r1', name: 'DeepSeek R1', tier: 'quality', specialization: 'reasoning' },
  ],
  google: [
    { id: 'google:flash', name: 'Gemini Flash', tier: 'fast' },
    { id: 'google:pro', name: 'Gemini Pro', tier: 'balanced' },
  ],
  groq: [
    { id: 'groq:llama70b', name: 'Llama 3 70B (Groq LPU)', tier: 'fast' },
    { id: 'groq:mixtral', name: 'Mixtral 8x7B (Groq LPU)', tier: 'fast' },
  ],
};

/* ── Task categories for routing ───────────────────────────── */

export interface TaskCategory {
  id: string;
  label: string;
  description: string;
  preferredCategory: 'general' | 'coding' | 'reasoning';
}

export const TASK_CATEGORIES: TaskCategory[] = [
  { id: 'chat', label: 'General Chat', description: 'Simple Q&A, conversations, quick responses', preferredCategory: 'general' },
  { id: 'reasoning', label: 'Deep Reasoning', description: 'Complex analysis, multi-step logic, math', preferredCategory: 'reasoning' },
  { id: 'coding', label: 'Code Generation', description: 'Writing code, debugging, code review', preferredCategory: 'coding' },
  { id: 'creative', label: 'Creative Writing', description: 'Content creation, storytelling, copywriting', preferredCategory: 'general' },
  { id: 'analysis', label: 'Data Analysis', description: 'Summarization, extraction, classification', preferredCategory: 'reasoning' },
  { id: 'translation', label: 'Translation', description: 'Language translation and localization', preferredCategory: 'general' },
];

/* ── Suggestion engine ─────────────────────────────────────── */

function parseParamB(s: string | undefined): number {
  if (!s) return 0;
  const m = s.match(/([\d.]+)\s*B/i);
  return m?.[1] ? parseFloat(m[1]) : 0;
}

interface ScoredModel {
  id: string;
  name: string;
  category: string;
  isLocal: boolean;
  paramB: number;
  tier: 'fast' | 'balanced' | 'quality' | 'local';
  specialization?: string;
}

function buildCandidates(
  selectedModels: string[],
  cloudProviders: string[],
  allModels: ModelInfo[],
): ScoredModel[] {
  const locals: ScoredModel[] = selectedModels
    .map((id) => {
      const m = allModels.find((x) => x.id === id);
      if (!m) return null;
      return {
        id: m.id,
        name: m.name,
        category: m.category as string,
        isLocal: true,
        paramB: parseParamB(m.parameters),
        tier: 'local' as const,
      } satisfies ScoredModel;
    })
    .filter((x): x is NonNullable<typeof x> => x !== null);

  const clouds: ScoredModel[] = cloudProviders.flatMap((p) =>
    (CLOUD_MODELS[p] ?? []).map((cm) => ({
      id: cm.id,
      name: cm.name,
      category: cm.specialization ?? 'general',
      isLocal: false,
      paramB: 0,
      tier: cm.tier,
      specialization: cm.specialization,
    })),
  );

  return [...locals, ...clouds];
}

function scoreModel(
  model: ScoredModel,
  task: TaskCategory,
  optimization: OptimizationPreset,
): number {
  let score = 0;

  // Task affinity: prefer models that specialize in this task's category
  if (model.category === task.preferredCategory) score += 20;
  if (model.specialization === task.preferredCategory) score += 15;

  // Optimization alignment
  switch (optimization) {
    case 'cost':
      if (model.isLocal) score += 30;
      if (model.tier === 'fast') score += 10;
      if (model.isLocal && model.paramB <= 8) score += 5;
      break;
    case 'speed':
      if (model.tier === 'fast') score += 30;
      if (model.isLocal && model.paramB <= 8) score += 20;
      if (model.isLocal && model.paramB <= 4) score += 10;
      break;
    case 'quality':
      if (model.tier === 'quality') score += 30;
      if (model.tier === 'balanced') score += 15;
      if (model.isLocal && model.paramB >= 30) score += 10;
      if (model.isLocal && model.paramB >= 70) score += 15;
      break;
    case 'balanced':
      if (model.tier === 'balanced') score += 25;
      if (model.isLocal) score += 10;
      if (model.tier === 'quality') score += 5;
      break;
  }

  return score;
}

/**
 * Auto-suggest strategy rules based on available models and optimization preset.
 * Primary and fallback models are chosen from different pools (local vs cloud)
 * when possible, for better reliability.
 */
export function suggestRules(
  selectedModels: string[],
  cloudProviders: string[],
  optimization: OptimizationPreset,
  allModels: ModelInfo[],
): StrategyRule[] {
  const candidates = buildCandidates(selectedModels, cloudProviders, allModels);
  if (candidates.length === 0) return TASK_CATEGORIES.map((t) => ({ taskCategory: t.id, primaryModel: '', fallbackModel: '' }));

  return TASK_CATEGORIES.map((task) => {
    const scored = candidates
      .map((m) => ({ ...m, score: scoreModel(m, task, optimization) }))
      .sort((a, b) => b.score - a.score);

    const primary = scored[0];
    // For fallback, prefer a different pool (local↔cloud) for reliability
    const fallback = scored.find(
      (m) => m.id !== primary?.id && m.isLocal !== primary?.isLocal,
    ) ?? scored.find((m) => m.id !== primary?.id) ?? null;

    return {
      taskCategory: task.id,
      primaryModel: primary?.id ?? '',
      fallbackModel: fallback?.id ?? '',
    };
  });
}

/**
 * Return a human-readable name for a model ID.
 * Looks up local models in the catalog, cloud models in CLOUD_MODELS.
 */
export function getModelDisplayName(modelId: string, allModels: ModelInfo[]): string {
  if (!modelId) return '—';
  // Cloud model
  if (modelId.includes(':')) {
    for (const models of Object.values(CLOUD_MODELS)) {
      const found = models.find((m) => m.id === modelId);
      if (found) return found.name;
    }
  }
  // Local model
  const local = allModels.find((m) => m.id === modelId);
  if (local) return local.name;
  return modelId;
}
