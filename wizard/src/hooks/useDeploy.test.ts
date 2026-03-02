/**
 * Tests for the useDeploy hook.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDeploy } from './useDeploy';

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

beforeEach(() => {
  vi.clearAllMocks();
  mockFetch.mockReset();
});

describe('useDeploy', () => {
  it('initializes with correct default state', () => {
    const { result } = renderHook(() => useDeploy());
    expect(result.current.isDeploying).toBe(false);
    expect(result.current.isDone).toBe(false);
    expect(result.current.hasError).toBe(false);
    expect(result.current.logs).toEqual([]);
    expect(result.current.endpoints).toEqual([]);
    expect(result.current.steps.length).toBeGreaterThan(0);
    expect(result.current.healthChecks.length).toBeGreaterThan(0);
  });

  it('all deploy steps start as pending', () => {
    const { result } = renderHook(() => useDeploy());
    for (const step of result.current.steps) {
      expect(step.status).toBe('pending');
    }
  });

  it('all health checks start as pending', () => {
    const { result } = renderHook(() => useDeploy());
    for (const hc of result.current.healthChecks) {
      expect(hc.status).toBe('pending');
    }
  });

  it('health checks include expected services', () => {
    const { result } = renderHook(() => useDeploy());
    const names = result.current.healthChecks.map((h) => h.name);
    expect(names).toContain('Agent Platform');
    expect(names).toContain('Gateway Router');
    expect(names).toContain('Optimizer');
    expect(names).toContain('LLM Runtime');
    expect(names).toContain('Watchdog');
  });

  it('startDeploy sets isDeploying to true', async () => {
    // Mock fetch to reject (triggers local deploy path)
    mockFetch.mockRejectedValue(new Error('no backend'));

    const { result } = renderHook(() => useDeploy());

    // Don't await — just start and check the flag
    act(() => {
      result.current.startDeploy({ agent_name: 'test' });
    });

    // isDeploying should be true after starting
    expect(result.current.isDeploying).toBe(true);
  });

  it('cleanup aborts deploy', () => {
    const { result } = renderHook(() => useDeploy());
    // cleanup should not throw
    expect(() => result.current.cleanup()).not.toThrow();
  });

  it('deploy steps have labels', () => {
    const { result } = renderHook(() => useDeploy());
    for (const step of result.current.steps) {
      expect(step.label).toBeTruthy();
      expect(typeof step.label).toBe('string');
    }
  });

  it('health check endpoints contain URLs', () => {
    const { result } = renderHook(() => useDeploy());
    for (const hc of result.current.healthChecks) {
      expect(hc.endpoint).toMatch(/^http/);
    }
  });
});
