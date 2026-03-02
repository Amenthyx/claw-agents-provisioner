/**
 * Tests for the LLM Provider step component.
 */
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/render-helpers';
import { StepLLM } from './StepLLM';

// Mock framer-motion
vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<typeof import('framer-motion')>('framer-motion');
  return {
    ...actual,
    motion: {
      div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
        const { variants, initial, animate, exit, transition, whileHover, whileTap, ...rest } = props;
        void variants; void initial; void animate; void exit; void transition; void whileHover; void whileTap;
        return <div {...rest}>{children}</div>;
      },
    },
    AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
  };
});

// Mock the API module
vi.mock('../../lib/api', () => ({
  api: {
    getRuntimes: vi.fn().mockRejectedValue(new Error('no backend')),
  },
}));

describe('StepLLM', () => {
  it('renders all three provider modes', () => {
    renderWithProviders(<StepLLM />);
    expect(screen.getByText('Cloud API')).toBeInTheDocument();
    expect(screen.getByText('Local LLM')).toBeInTheDocument();
    expect(screen.getByText('Hybrid')).toBeInTheDocument();
  });

  it('renders mode descriptions', () => {
    renderWithProviders(<StepLLM />);
    expect(screen.getByText('Use hosted LLM providers via API')).toBeInTheDocument();
    expect(screen.getByText(/Native install on your machine/)).toBeInTheDocument();
    expect(screen.getByText(/Local native \+ cloud fallback/)).toBeInTheDocument();
  });

  it('shows cloud providers by default (cloud is initial provider)', () => {
    renderWithProviders(<StepLLM />);
    // Initial state has llmProvider = 'cloud', so cloud providers should show
    expect(screen.getByText('Cloud Providers')).toBeInTheDocument();
    expect(screen.getByText('Anthropic')).toBeInTheDocument();
    expect(screen.getByText('OpenAI')).toBeInTheDocument();
    expect(screen.getByText('DeepSeek')).toBeInTheDocument();
    expect(screen.getByText('Google')).toBeInTheDocument();
    expect(screen.getByText('Groq')).toBeInTheDocument();
  });

  it('shows local runtimes when Local LLM is selected', () => {
    renderWithProviders(<StepLLM />);
    const localButton = screen.getByText('Local LLM').closest('[role="button"]');
    if (localButton) {
      fireEvent.click(localButton);
    }
    expect(screen.getByText('Local Runtime')).toBeInTheDocument();
    expect(screen.getByText('Ollama')).toBeInTheDocument();
    expect(screen.getByText('llama.cpp')).toBeInTheDocument();
    expect(screen.getByText('vLLM')).toBeInTheDocument();
  });

  it('shows both cloud and local sections for Hybrid mode', () => {
    renderWithProviders(<StepLLM />);
    const hybridButton = screen.getByText('Hybrid').closest('[role="button"]');
    if (hybridButton) {
      fireEvent.click(hybridButton);
    }
    expect(screen.getByText('Cloud Providers')).toBeInTheDocument();
    expect(screen.getByText('Local Runtime')).toBeInTheDocument();
  });

  it('shows Custom Endpoint option in local runtimes', () => {
    renderWithProviders(<StepLLM />);
    const localButton = screen.getByText('Local LLM').closest('[role="button"]');
    if (localButton) {
      fireEvent.click(localButton);
    }
    expect(screen.getByText('Custom Endpoint')).toBeInTheDocument();
  });

  it('shows API key input when a cloud provider is selected', () => {
    renderWithProviders(<StepLLM />);
    // Cloud is default, click on Anthropic to select it
    const anthropicCard = screen.getByText('Anthropic').closest('[role="button"]');
    if (anthropicCard) {
      fireEvent.click(anthropicCard);
    }
    expect(screen.getByText('Anthropic API Key')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('sk-...')).toBeInTheDocument();
  });

  it('displays model descriptions for cloud providers', () => {
    renderWithProviders(<StepLLM />);
    expect(screen.getByText('Claude 4')).toBeInTheDocument();
    expect(screen.getByText('GPT-4o')).toBeInTheDocument();
    expect(screen.getByText('DeepSeek V3')).toBeInTheDocument();
  });
});
