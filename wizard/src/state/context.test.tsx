/**
 * Tests for the WizardProvider context and useWizard hook.
 */
import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { type ReactNode } from 'react';
import { WizardProvider, useWizard } from './context';
import { TOTAL_STEPS } from './reducer';

// Mock framer-motion to avoid issues
vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<typeof import('framer-motion')>('framer-motion');
  return {
    ...actual,
    motion: {
      div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
        const { variants, initial, animate, exit, transition, ...rest } = props;
        void variants; void initial; void animate; void exit; void transition;
        return <div {...rest}>{children}</div>;
      },
    },
    AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
  };
});

// Mock the API to prevent actual fetches
vi.mock('../lib/api', () => ({
  api: {
    getPlatforms: vi.fn().mockRejectedValue(new Error('no backend')),
    getRuntimes: vi.fn().mockRejectedValue(new Error('no backend')),
    getModels: vi.fn().mockRejectedValue(new Error('no backend')),
    getHardware: vi.fn().mockRejectedValue(new Error('no backend')),
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  return <WizardProvider>{children}</WizardProvider>;
}

describe('useWizard', () => {
  it('throws when used outside WizardProvider', () => {
    // Suppress console.error for this test
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => {
      renderHook(() => useWizard());
    }).toThrow('useWizard must be used within WizardProvider');
    spy.mockRestore();
  });

  it('provides initial state', () => {
    const { result } = renderHook(() => useWizard(), { wrapper });
    expect(result.current.state.currentStep).toBe(0);
    expect(result.current.state.agentName).toBe('');
    expect(result.current.state.platform).toBe('');
    expect(result.current.state.deploymentMethod).toBe('docker');
    expect(result.current.state.llmProvider).toBe('cloud');
  });

  it('provides totalSteps', () => {
    const { result } = renderHook(() => useWizard(), { wrapper });
    expect(result.current.totalSteps).toBe(TOTAL_STEPS);
  });

  it('provides stepLabel', () => {
    const { result } = renderHook(() => useWizard(), { wrapper });
    expect(result.current.stepLabel).toBe('Welcome');
  });

  it('provides progress as percentage', () => {
    const { result } = renderHook(() => useWizard(), { wrapper });
    const expectedProgress = (1 / TOTAL_STEPS) * 100;
    expect(result.current.progress).toBeCloseTo(expectedProgress, 1);
  });

  it('canProceedNow is false at start (empty agent name)', () => {
    const { result } = renderHook(() => useWizard(), { wrapper });
    expect(result.current.canProceedNow).toBe(false);
  });

  describe('action dispatchers', () => {
    it('nextStep advances current step', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.nextStep();
      });
      expect(result.current.state.currentStep).toBe(1);
    });

    it('prevStep goes back', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.nextStep();
        result.current.nextStep();
      });
      expect(result.current.state.currentStep).toBe(2);
      act(() => {
        result.current.prevStep();
      });
      expect(result.current.state.currentStep).toBe(1);
    });

    it('goToStep jumps to specific step', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.goToStep(5);
      });
      expect(result.current.state.currentStep).toBe(5);
    });

    it('setAgentName updates name', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setAgentName('test-agent');
      });
      expect(result.current.state.agentName).toBe('test-agent');
    });

    it('setPlatform updates platform', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setPlatform('zeroclaw');
      });
      expect(result.current.state.platform).toBe('zeroclaw');
    });

    it('setDeploymentMethod updates method', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setDeploymentMethod('vagrant');
      });
      expect(result.current.state.deploymentMethod).toBe('vagrant');
    });

    it('setLlmProvider updates provider', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setLlmProvider('local');
      });
      expect(result.current.state.llmProvider).toBe('local');
    });

    it('setRuntime updates runtime', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setRuntime('vllm');
      });
      expect(result.current.state.runtime).toBe('vllm');
    });

    it('toggleModel adds and removes models', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.toggleModel('mistral:7b');
      });
      expect(result.current.state.selectedModels).toContain('mistral:7b');
      act(() => {
        result.current.toggleModel('mistral:7b');
      });
      expect(result.current.state.selectedModels).not.toContain('mistral:7b');
    });

    it('setSecurityEnabled toggles security', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setSecurityEnabled(true);
      });
      expect(result.current.state.securityEnabled).toBe(true);
    });

    it('toggleSecurityFeature toggles feature', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.toggleSecurityFeature('pii-detection');
      });
      expect(result.current.state.securityFeatures).toContain('pii-detection');
    });

    it('setCloudProviders updates providers', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setCloudProviders(['openai', 'anthropic']);
      });
      expect(result.current.state.cloudProviders).toEqual(['openai', 'anthropic']);
    });

    it('setApiKey stores key', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setApiKey('openai', 'sk-test');
      });
      expect(result.current.state.apiKeys.openai).toBe('sk-test');
    });

    it('setGateway merges config', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setGateway({ port: 8080 });
      });
      expect(result.current.state.gateway.port).toBe(8080);
    });

    it('setChannel configures a channel', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setChannel('telegram', { enabled: true, config: { token: 'abc' } });
      });
      expect(result.current.state.channels.telegram).toEqual({
        enabled: true,
        config: { token: 'abc' },
      });
    });

    it('setPortConfig updates port config', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setPortConfig({ mode: 'manual', agentPort: 4000 });
      });
      expect(result.current.state.portConfig.mode).toBe('manual');
      expect(result.current.state.portConfig.agentPort).toBe(4000);
    });
  });

  describe('derived values', () => {
    it('canProceedNow becomes true when agent name is set', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      expect(result.current.canProceedNow).toBe(false);
      act(() => {
        result.current.setAgentName('my-agent');
      });
      expect(result.current.canProceedNow).toBe(true);
    });

    it('assessmentJSON includes agent_name', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      act(() => {
        result.current.setAgentName('test');
      });
      expect(result.current.assessmentJSON.agent_name).toBe('test');
    });

    it('progress increases as steps advance', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      const initialProgress = result.current.progress;
      act(() => {
        result.current.nextStep();
      });
      expect(result.current.progress).toBeGreaterThan(initialProgress);
    });

    it('stepLabel updates when step changes', () => {
      const { result } = renderHook(() => useWizard(), { wrapper });
      expect(result.current.stepLabel).toBe('Welcome');
      act(() => {
        result.current.nextStep();
      });
      expect(result.current.stepLabel).toBe('Hardware');
    });
  });
});
