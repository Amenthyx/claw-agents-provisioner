import type { HardwareProfile, ModelInfo } from '../state/types';

/**
 * GPU memory bandwidth lookup (GB/s) — keyed by regex patterns matched against GPU names.
 * More specific patterns come first so they match before generic ones.
 */
const GPU_BANDWIDTH: [RegExp, number][] = [
  // ── NVIDIA Data Center / Professional ──
  [/H200/i, 4800],
  [/H100/i, 3350],
  [/A100.*80/i, 2039],
  [/A100/i, 1555],
  [/L40S/i, 864],
  [/L40\b/i, 864],
  [/A6000/i, 768],
  [/A5000/i, 768],
  [/A4000/i, 448],

  // ── NVIDIA RTX 50 series ──
  [/5090/i, 1792],
  [/5080/i, 960],
  [/5070\s*Ti/i, 896],
  [/5070\b/i, 672],
  [/5060\s*Ti/i, 448],
  [/5060\b/i, 336],

  // ── NVIDIA RTX 40 series ──
  [/4090/i, 1008],
  [/4080\s*S/i, 736],
  [/4080/i, 717],
  [/4070\s*Ti\s*S/i, 672],
  [/4070\s*Ti/i, 504],
  [/4070\s*S/i, 504],
  [/4070\b/i, 504],
  [/4060\s*Ti/i, 288],
  [/4060\b/i, 272],

  // ── NVIDIA RTX 30 series ──
  [/3090\s*Ti/i, 1008],
  [/3090/i, 936],
  [/3080\s*Ti/i, 912],
  [/3080/i, 760],
  [/3070\s*Ti/i, 608],
  [/3070\b/i, 448],
  [/3060\s*Ti/i, 448],
  [/3060\b/i, 360],

  // ── NVIDIA RTX 20 series ──
  [/2080\s*Ti/i, 616],
  [/2080\s*S/i, 496],
  [/2080\b/i, 448],
  [/2070\s*S/i, 448],
  [/2070\b/i, 448],
  [/2060\s*S/i, 448],
  [/2060\b/i, 336],

  // ── AMD Radeon ──
  [/7900\s*XTX/i, 960],
  [/7900\s*XT\b/i, 800],
  [/7900\s*GRE/i, 624],
  [/7800\s*XT/i, 624],
  [/7700\s*XT/i, 432],
  [/7600/i, 288],
  [/MI300X/i, 5300],
  [/MI250/i, 3277],
  [/MI210/i, 1638],

  // ── Intel Arc ──
  [/A770/i, 560],
  [/A750/i, 512],
  [/A580/i, 512],
  [/A380/i, 186],

  // ── Apple Silicon (unified memory) ──
  [/M4\s*Ultra/i, 819],
  [/M4\s*Max/i, 546],
  [/M4\s*Pro/i, 273],
  [/M4\b/i, 120],
  [/M3\s*Ultra/i, 800],
  [/M3\s*Max/i, 400],
  [/M3\s*Pro/i, 150],
  [/M3\b/i, 100],
  [/M2\s*Ultra/i, 800],
  [/M2\s*Max/i, 400],
  [/M2\s*Pro/i, 200],
  [/M2\b/i, 100],
  [/M1\s*Ultra/i, 800],
  [/M1\s*Max/i, 400],
  [/M1\s*Pro/i, 200],
  [/M1\b/i, 68],
];

/** Estimate GPU memory bandwidth in GB/s from the GPU name string */
function getGpuBandwidth(gpuName: string): number {
  if (!gpuName) return 0;
  for (const [pattern, bw] of GPU_BANDWIDTH) {
    if (pattern.test(gpuName)) return bw;
  }
  if (/nvidia|geforce|rtx|gtx|quadro|tesla/i.test(gpuName)) return 400;
  if (/radeon|amd/i.test(gpuName)) return 400;
  if (/intel.*arc/i.test(gpuName)) return 300;
  if (/apple|m\d/i.test(gpuName)) return 150;
  return 0;
}

/**
 * Parse active parameter count in billions from model parameter strings.
 * - "671B (37B active)" → 37
 * - "30B (3B active)" → 3
 * - "70B" → 70
 */
function parseActiveParams(parameters: string): number {
  const moeMatch = parameters.match(/\((\d+(?:\.\d+)?)\s*B\s*active\)/i);
  if (moeMatch?.[1]) return parseFloat(moeMatch[1]);
  const regular = parameters.match(/([\d.]+)\s*B/i);
  if (regular?.[1]) return parseFloat(regular[1]);
  return 0;
}

export type InferenceMode = 'gpu' | 'partial' | 'cpu';

export interface TokenEstimate {
  tokensPerSecond: number;
  mode: InferenceMode;
}

/**
 * Estimate output tokens/s for a model on the detected hardware.
 *
 * Based on the memory-bandwidth-bound nature of autoregressive LLM inference:
 *   tok/s ≈ bandwidth / (bytes_per_param × active_params) × overhead
 *
 * The overhead factor is model-size dependent:
 * - Large models (30B+): ~0.8 — truly memory-bound, formula is accurate
 * - Small models (<10B): ~0.3-0.5 — partially compute-bound
 *
 * Q4 quantization: ~0.5 bytes per parameter.
 */
export function estimateTokensPerSecond(
  model: ModelInfo,
  hardware: HardwareProfile | null,
): TokenEstimate | null {
  if (!hardware) return null;

  const activeParams = parseActiveParams(model.parameters);
  if (activeParams <= 0) return null;

  const totalVram = hardware.gpus.reduce((sum, g) => sum + (g.vram ?? 0), 0);
  const totalGpuBandwidth = hardware.gpus.reduce(
    (sum, g) => sum + getGpuBandwidth(g.name ?? ''), 0,
  );

  const bytesPerParam = 0.5; // Q4 quantization
  const modelSizeGB = bytesPerParam * activeParams;

  // Dynamic overhead: scales from ~0.2 (tiny models, compute-bound) to 0.8 (large, memory-bound)
  const overhead = Math.min(0.8, 0.2 + 0.6 * Math.min(1, activeParams / 30));

  // ── GPU: model fits entirely in VRAM ──
  if (totalVram > 0 && model.vramRequired <= totalVram && totalGpuBandwidth > 0) {
    const raw = (totalGpuBandwidth / modelSizeGB) * overhead;
    return { tokensPerSecond: Math.min(Math.round(raw), 250), mode: 'gpu' };
  }

  // RAM bandwidth heuristic: DDR5 ~80 GB/s, DDR4 ~50 GB/s
  const ramBandwidth = hardware.ram >= 64 ? 80 : 50;

  // ── Partial offload: some layers GPU, rest CPU ──
  if (totalVram > 0 && totalGpuBandwidth > 0 && model.vramRequired > totalVram) {
    const gpuFraction = Math.min(totalVram / model.vramRequired, 0.95);
    const cpuFraction = 1 - gpuFraction;
    // Harmonic blend — bottlenecked by the slower component
    const effectiveBandwidth = 1 / (gpuFraction / totalGpuBandwidth + cpuFraction / ramBandwidth);
    const raw = (effectiveBandwidth / modelSizeGB) * overhead;
    return { tokensPerSecond: Math.max(1, Math.round(raw)), mode: 'partial' };
  }

  // ── Pure CPU ──
  const raw = (ramBandwidth / modelSizeGB) * overhead;
  return { tokensPerSecond: Math.max(1, Math.round(raw)), mode: 'cpu' };
}
