import { useCallback, useRef, useState } from 'react';
import { api } from '../lib/api';
import type { HardwareProfile, RuntimeRecommendation } from '../state/types';

/**
 * Detect hardware using browser APIs as a real fallback
 * when the backend API is unavailable.
 */
async function detectBrowserHardware(): Promise<HardwareProfile> {
  const cores = navigator.hardwareConcurrency || 4;

  // navigator.deviceMemory is available in Chrome/Edge (returns GB, capped at 8)
  // For real RAM detection we also check the backend profile
  const deviceMemGb = (navigator as unknown as Record<string, number>).deviceMemory ?? 0;

  // Try to read platform info
  let osStr = navigator.platform || 'Unknown';
  let archStr = '';
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const nav = navigator as any;
    const uaData = await nav.userAgentData?.getHighEntropyValues?.(['architecture', 'platform', 'platformVersion']);
    if (uaData) {
      osStr = `${uaData.platform ?? osStr} ${uaData.platformVersion ?? ''}`.trim();
      archStr = uaData.architecture ?? '';
    }
  } catch {
    // Not supported — parse from userAgent
    const ua = navigator.userAgent;
    if (ua.includes('Win64') || ua.includes('x86_64') || ua.includes('x64')) archStr = 'x86_64';
    else if (ua.includes('ARM') || ua.includes('aarch64')) archStr = 'aarch64';
    else archStr = 'x86_64';
    if (ua.includes('Windows')) osStr = 'Windows';
    else if (ua.includes('Mac')) osStr = 'macOS';
    else if (ua.includes('Linux')) osStr = 'Linux';
  }

  // Detect GPU via WebGL
  const gpus: HardwareProfile['gpus'] = [];
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (gl) {
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      if (ext) {
        const renderer = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) as string;
        const vendor = gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) as string;

        // Extract clean GPU name from ANGLE strings like:
        // "ANGLE (Intel, Intel(R) Arc(TM) 140T GPU (16GB) (0x00007D51) Direct3D11 ...)"
        const gpuName = extractGpuName(renderer) || vendor;

        // Estimate VRAM — first try parsing from renderer string, then lookup table
        const vram = estimateVram(renderer);
        const rl = renderer.toLowerCase();
        const apiStr = rl.includes('nvidia') ? 'CUDA'
          : rl.includes('amd') || rl.includes('radeon') ? 'ROCm'
          : rl.includes('apple') ? 'Metal'
          : rl.includes('intel') ? 'OpenCL'
          : 'OpenCL';

        gpus.push({ name: gpuName, vram, api: apiStr });
      }
    }
  } catch {
    // WebGL not available
  }

  // Estimate RAM — deviceMemory is capped at 8GB in browsers.
  // If we detect a powerful GPU, we can infer the system likely has more.
  // Default to a reasonable estimate based on GPU + cores.
  let ramEstimate = deviceMemGb;
  if (ramEstimate <= 0 || ramEstimate <= 8) {
    // Heuristic: high-core systems typically have more RAM
    if (cores >= 32) ramEstimate = 128;
    else if (cores >= 16) ramEstimate = 64;
    else if (cores >= 8) ramEstimate = 32;
    else ramEstimate = 16;

    // If GPU has lots of VRAM, system likely has even more RAM
    const totalVram = gpus.reduce((s, g) => s + g.vram, 0);
    if (totalVram >= 48) ramEstimate = Math.max(ramEstimate, 512);
    else if (totalVram >= 24) ramEstimate = Math.max(ramEstimate, 128);
    else if (totalVram >= 16) ramEstimate = Math.max(ramEstimate, 64);
  }

  // Detect CPU features (we can't detect from browser, but we can infer some basics)
  const features: string[] = [];
  // Most modern x86_64 CPUs support these
  if (archStr === 'x86_64') {
    features.push('SSE4.2', 'AVX2', 'AES-NI');
    if (cores >= 8) features.push('FMA3');
  } else if (archStr === 'aarch64') {
    features.push('NEON', 'AES', 'SHA');
  }

  // Try to get a CPU brand from GPU vendor heuristic
  let cpuBrand = `${cores}-core ${archStr} processor`;
  if (osStr.includes('Mac') || osStr.includes('macOS')) {
    if (archStr === 'aarch64' || archStr === 'arm') {
      cpuBrand = cores >= 10 ? 'Apple M2 Pro/Max' : 'Apple M1/M2';
    }
  }

  return {
    os: osStr,
    arch: archStr || 'x86_64',
    cpu: { brand: cpuBrand, cores, features },
    ram: ramEstimate,
    gpus,
  };
}

/**
 * Extract clean GPU name from ANGLE renderer strings.
 * e.g. "ANGLE (Intel, Intel(R) Arc(TM) 140T GPU (16GB) (0x00007D51) Direct3D11 ...)"
 *   -> "Intel Arc 140T GPU (16GB)"
 */
function extractGpuName(renderer: string): string {
  // Try to extract from ANGLE format: "ANGLE (Vendor, GPU_NAME (extras) Direct3D...)"
  const angleMatch = renderer.match(/ANGLE\s*\([^,]+,\s*(.+?)(?:\s*\(0x[\da-fA-F]+\))?\s*Direct3D/);
  if (angleMatch?.[1]) {
    // Clean up trademark symbols
    return angleMatch[1].replace(/\(R\)/g, '').replace(/\(TM\)/g, '').replace(/\s+/g, ' ').trim();
  }
  // Fallback: return as-is but trim ANGLE wrapper if present
  const simpleAngle = renderer.match(/ANGLE\s*\([^,]+,\s*(.+?)\s*\)/);
  if (simpleAngle?.[1]) {
    return simpleAngle[1].replace(/\(R\)/g, '').replace(/\(TM\)/g, '').replace(/\s+/g, ' ').trim();
  }
  return renderer;
}

function estimateVram(renderer: string): number {
  const r = renderer.toLowerCase();

  // First: try to parse VRAM directly from the renderer string.
  // Many ANGLE strings include it: "Intel(R) Arc(TM) 140T GPU (16GB)"
  const vramMatch = renderer.match(/\((\d+)\s*GB\)/i);
  if (vramMatch?.[1]) {
    return parseInt(vramMatch[1], 10);
  }

  // Fallback: lookup table for known GPUs
  // NVIDIA
  if (r.includes('4090')) return 24;
  if (r.includes('4080 super')) return 16;
  if (r.includes('4080')) return 16;
  if (r.includes('4070 ti super')) return 16;
  if (r.includes('4070 ti')) return 12;
  if (r.includes('4070 super')) return 12;
  if (r.includes('4070')) return 12;
  if (r.includes('4060 ti')) return 16;
  if (r.includes('4060')) return 8;
  if (r.includes('3090 ti')) return 24;
  if (r.includes('3090')) return 24;
  if (r.includes('3080 ti')) return 12;
  if (r.includes('3080')) return 10;
  if (r.includes('3070 ti')) return 8;
  if (r.includes('3070')) return 8;
  if (r.includes('3060 ti')) return 8;
  if (r.includes('3060')) return 12;
  if (r.includes('a100')) return 80;
  if (r.includes('a6000')) return 48;
  if (r.includes('a40')) return 48;
  if (r.includes('h100')) return 80;
  if (r.includes('h200')) return 141;
  if (r.includes('l40s')) return 48;
  if (r.includes('l40')) return 48;
  if (r.includes('a10g')) return 24;
  if (r.includes('a10')) return 24;
  if (r.includes('t4')) return 16;
  if (r.includes('5090')) return 32;
  if (r.includes('5080')) return 16;
  // AMD
  if (r.includes('7900 xtx')) return 24;
  if (r.includes('7900 xt')) return 20;
  if (r.includes('7800 xt')) return 16;
  if (r.includes('7700 xt')) return 12;
  if (r.includes('7600')) return 8;
  if (r.includes('mi300')) return 192;
  if (r.includes('mi250')) return 128;
  if (r.includes('mi100')) return 32;
  // Apple — unified memory, counted as RAM
  if (r.includes('apple')) return 0;
  // Intel Arc
  if (r.includes('arc a770')) return 16;
  if (r.includes('arc a750')) return 8;
  if (r.includes('arc a580')) return 8;
  if (r.includes('arc 140')) return 16;  // Arc 140T / 140V
  if (r.includes('arc 130')) return 8;
  if (r.includes('arc b580')) return 12;
  if (r.includes('arc')) return 8; // other Arc GPUs
  // Intel integrated
  if (r.includes('iris') || r.includes('uhd')) return 2;
  // Unknown — conservative default
  return 4;
}

function generateRecommendation(hw: HardwareProfile): RuntimeRecommendation {
  const totalVram = hw.gpus.reduce((s, g) => s + g.vram, 0);
  const totalRam = hw.ram;
  const hasNvidia = hw.gpus.some((g) =>
    typeof g.name === 'string' && (g.name.toLowerCase().includes('nvidia') || g.api === 'CUDA')
  );
  const hasAmd = hw.gpus.some((g) =>
    typeof g.name === 'string' && (g.name.toLowerCase().includes('amd') || g.name.toLowerCase().includes('radeon'))
  );
  const isApple = typeof hw.os === 'string' && (hw.os.includes('Mac') || hw.os.includes('macOS'));

  // 600B+ models need ~300GB+ RAM or multi-GPU
  if (totalRam >= 512 || totalVram >= 80) {
    return {
      primary: 'vLLM',
      fallback: 'Ollama',
      reason: `Extreme hardware detected (${totalRam}GB RAM, ${totalVram}GB VRAM) — vLLM enables tensor parallelism for 70B-600B+ parameter models with optimal throughput.`,
    };
  }

  if (totalVram >= 48) {
    return {
      primary: 'vLLM',
      fallback: 'Ollama',
      reason: `High VRAM (${totalVram}GB) — vLLM recommended for 70B+ models with multi-GPU support.`,
    };
  }

  if (hasNvidia && totalVram >= 24) {
    return {
      primary: 'Ollama',
      fallback: 'llama.cpp',
      reason: `NVIDIA GPU with ${totalVram}GB VRAM — Ollama provides automatic CUDA acceleration and easy model management.`,
    };
  }

  if (hasNvidia) {
    return {
      primary: 'Ollama',
      fallback: 'llama.cpp',
      reason: `NVIDIA GPU detected — Ollama provides CUDA acceleration for smaller models.`,
    };
  }

  const hasIntelArc = hw.gpus.some((g) =>
    typeof g.name === 'string' && g.name.toLowerCase().includes('arc') && g.name.toLowerCase().includes('intel')
  );

  if (hasIntelArc) {
    return {
      primary: 'Ollama',
      fallback: 'llama.cpp',
      reason: `Intel Arc GPU with ${totalVram}GB VRAM detected — Ollama supports Intel Arc via SYCL/oneAPI acceleration. Good for 7B-14B models natively, larger models with CPU offload.`,
    };
  }

  if (hasAmd) {
    return {
      primary: 'llama.cpp',
      fallback: 'Ollama',
      reason: `AMD GPU detected — llama.cpp has the best ROCm support for AMD GPUs.`,
    };
  }

  if (isApple) {
    return {
      primary: 'Ollama',
      fallback: 'llama.cpp',
      reason: `Apple Silicon detected — Ollama leverages Metal acceleration with unified memory.`,
    };
  }

  if (totalRam >= 64) {
    return {
      primary: 'llama.cpp',
      fallback: 'Ollama',
      reason: `No discrete GPU detected but ${totalRam}GB RAM available — llama.cpp can run models in CPU mode with large context.`,
    };
  }

  return {
    primary: 'Ollama',
    fallback: 'LocalAI',
    reason: `Standard hardware detected — Ollama is the easiest starting point with automatic optimizations.`,
  };
}

/**
 * Normalize the raw API response into our internal shape.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeHardware(raw: any): HardwareProfile {
  return {
    os: raw.os,
    arch: raw.arch ?? raw.cpu?.arch ?? raw.os?.arch ?? '',
    cpu: {
      brand: raw.cpu?.brand ?? '',
      cores: raw.cpu?.cores ?? 0,
      features: raw.cpu?.features ?? [],
    },
    ram: raw.ram ?? raw.ram_gb ?? 0,
    gpus: (raw.gpus ?? []).map((g: Record<string, unknown>) => ({
      name: g.name ?? '',
      vram: g.vram ?? g.vram_gb ?? 0,
      api: g.api ?? '',
    })),
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeRecommendation(raw: any): RuntimeRecommendation {
  return {
    primary: raw.primary,
    fallback: raw.fallback,
    reason: raw.reason ?? '',
  };
}

export function useHardwareDetection() {
  const [hardware, setHardware] = useState<HardwareProfile | null>(null);
  const [recommendation, setRecommendation] = useState<RuntimeRecommendation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasRun = useRef(false);

  const detect = useCallback(async () => {
    if (hasRun.current) return;
    hasRun.current = true;
    setLoading(true);
    setError(null);

    try {
      const data = await api.getHardware();
      const hw = normalizeHardware(data.hardware);
      const rec = normalizeRecommendation(data.recommendation);
      setHardware(hw);
      setRecommendation(rec);
      return { hardware: hw, recommendation: rec };
    } catch {
      // Backend unavailable — detect from browser APIs
      try {
        const hw = await detectBrowserHardware();
        const rec = generateRecommendation(hw);
        setHardware(hw);
        setRecommendation(rec);
        setError('Hardware detected via browser APIs (connect backend for full profile)');
        return { hardware: hw, recommendation: rec };
      } catch {
        // Final fallback — minimal profile
        const fallback: HardwareProfile = {
          os: navigator.platform || 'Unknown',
          arch: 'x86_64',
          cpu: { brand: 'Unknown CPU', cores: navigator.hardwareConcurrency || 4, features: [] },
          ram: 16,
          gpus: [],
        };
        const rec = generateRecommendation(fallback);
        setHardware(fallback);
        setRecommendation(rec);
        setError('Could not detect hardware — using minimal profile');
        return { hardware: fallback, recommendation: rec };
      }
    } finally {
      setLoading(false);
    }
  }, []);

  return { hardware, recommendation, loading, error, detect };
}
