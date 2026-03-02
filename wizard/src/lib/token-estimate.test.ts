/**
 * Tests for token estimation logic — pure functions, no DOM needed.
 */
import { describe, it, expect } from 'vitest';
import { estimateTokensPerSecond } from './token-estimate';
import type { HardwareProfile, ModelInfo } from '../state/types';

function makeModel(overrides: Partial<ModelInfo> = {}): ModelInfo {
  return {
    id: 'test-model',
    name: 'Test Model',
    parameters: '7B',
    diskSize: '4.1 GB',
    vramRequired: 8,
    category: 'general',
    ...overrides,
  };
}

function makeHardware(overrides: Partial<HardwareProfile> = {}): HardwareProfile {
  return {
    os: 'Linux',
    arch: 'x86_64',
    cpu: { brand: 'Intel i7', cores: 8, features: ['AVX2'] },
    ram: 32,
    gpus: [{ name: 'RTX 4070', vram: 12, api: 'CUDA' }],
    ...overrides,
  };
}

describe('estimateTokensPerSecond', () => {
  it('returns null when hardware is null', () => {
    const result = estimateTokensPerSecond(makeModel(), null);
    expect(result).toBeNull();
  });

  it('returns null for model with unparsable parameters', () => {
    const result = estimateTokensPerSecond(
      makeModel({ parameters: 'unknown' }),
      makeHardware(),
    );
    expect(result).toBeNull();
  });

  it('returns gpu mode when model fits in VRAM', () => {
    const result = estimateTokensPerSecond(
      makeModel({ parameters: '7B', vramRequired: 8 }),
      makeHardware({ gpus: [{ name: 'RTX 4070', vram: 12, api: 'CUDA' }] }),
    );
    expect(result).not.toBeNull();
    expect(result!.mode).toBe('gpu');
    expect(result!.tokensPerSecond).toBeGreaterThan(0);
  });

  it('returns partial mode when model exceeds VRAM but system has some GPU', () => {
    const result = estimateTokensPerSecond(
      makeModel({ parameters: '70B', vramRequired: 48 }),
      makeHardware({
        gpus: [{ name: 'RTX 4070', vram: 12, api: 'CUDA' }],
        ram: 64,
      }),
    );
    expect(result).not.toBeNull();
    expect(result!.mode).toBe('partial');
    expect(result!.tokensPerSecond).toBeGreaterThan(0);
  });

  it('returns cpu mode when no GPU available', () => {
    const result = estimateTokensPerSecond(
      makeModel({ parameters: '7B', vramRequired: 8 }),
      makeHardware({ gpus: [], ram: 32 }),
    );
    expect(result).not.toBeNull();
    expect(result!.mode).toBe('cpu');
    expect(result!.tokensPerSecond).toBeGreaterThan(0);
  });

  it('handles MoE models with active parameter count', () => {
    const result = estimateTokensPerSecond(
      makeModel({ parameters: '671B (37B active)', vramRequired: 400 }),
      makeHardware({
        gpus: [{ name: 'H100', vram: 80, api: 'CUDA' }],
        ram: 512,
      }),
    );
    expect(result).not.toBeNull();
    // Uses 37B active params for calculation, not 671B
    expect(result!.tokensPerSecond).toBeGreaterThan(0);
  });

  it('caps tokens per second at 250', () => {
    // Tiny model on powerful hardware
    const result = estimateTokensPerSecond(
      makeModel({ parameters: '0.6B', vramRequired: 1 }),
      makeHardware({ gpus: [{ name: 'H100', vram: 80, api: 'CUDA' }] }),
    );
    expect(result).not.toBeNull();
    expect(result!.tokensPerSecond).toBeLessThanOrEqual(250);
  });

  it('returns at least 1 token per second for partial/cpu modes', () => {
    const result = estimateTokensPerSecond(
      makeModel({ parameters: '405B', vramRequired: 256 }),
      makeHardware({ gpus: [], ram: 16 }),
    );
    expect(result).not.toBeNull();
    expect(result!.tokensPerSecond).toBeGreaterThanOrEqual(1);
  });

  it('produces higher throughput for small models vs large', () => {
    const hw = makeHardware({ gpus: [{ name: 'RTX 4070', vram: 12, api: 'CUDA' }] });
    const small = estimateTokensPerSecond(makeModel({ parameters: '3B', vramRequired: 4 }), hw);
    const large = estimateTokensPerSecond(makeModel({ parameters: '70B', vramRequired: 48 }), hw);
    expect(small).not.toBeNull();
    expect(large).not.toBeNull();
    expect(small!.tokensPerSecond).toBeGreaterThan(large!.tokensPerSecond);
  });

  it('uses higher RAM bandwidth estimate for systems with 64+ GB', () => {
    const lowRam = estimateTokensPerSecond(
      makeModel({ parameters: '7B', vramRequired: 8 }),
      makeHardware({ gpus: [], ram: 32 }),
    );
    const highRam = estimateTokensPerSecond(
      makeModel({ parameters: '7B', vramRequired: 8 }),
      makeHardware({ gpus: [], ram: 128 }),
    );
    expect(lowRam).not.toBeNull();
    expect(highRam).not.toBeNull();
    // Higher RAM means higher bandwidth estimate, so higher tok/s
    expect(highRam!.tokensPerSecond).toBeGreaterThanOrEqual(lowRam!.tokensPerSecond);
  });
});
