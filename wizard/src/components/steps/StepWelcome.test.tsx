/**
 * Tests for the Welcome step component.
 */
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/render-helpers';
import { StepWelcome } from './StepWelcome';

// Mock framer-motion to avoid animation issues in tests
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
      h1: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
        const { variants, initial, animate, exit, transition, ...rest } = props;
        void variants; void initial; void animate; void exit; void transition;
        return <h1 {...rest}>{children}</h1>;
      },
      p: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
        const { variants, initial, animate, exit, transition, ...rest } = props;
        void variants; void initial; void animate; void exit; void transition;
        return <p {...rest}>{children}</p>;
      },
    },
    AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
  };
});

describe('StepWelcome', () => {
  it('renders the welcome heading', () => {
    renderWithProviders(<StepWelcome />);
    expect(screen.getByText('Welcome to XClaw')).toBeInTheDocument();
  });

  it('renders the description text', () => {
    renderWithProviders(<StepWelcome />);
    expect(screen.getByText(/Enterprise AI agent infrastructure/)).toBeInTheDocument();
  });

  it('renders agent name input', () => {
    renderWithProviders(<StepWelcome />);
    const input = screen.getByPlaceholderText('deployment-name');
    expect(input).toBeInTheDocument();
  });

  it('renders feature cards', () => {
    renderWithProviders(<StepWelcome />);
    expect(screen.getByText('5 Agent Platforms')).toBeInTheDocument();
    expect(screen.getByText('Hardware Detection')).toBeInTheDocument();
    expect(screen.getByText('One-Click Deploy')).toBeInTheDocument();
    expect(screen.getByText('Enterprise Security')).toBeInTheDocument();
  });

  it('renders Begin Setup button', () => {
    renderWithProviders(<StepWelcome />);
    const button = screen.getByRole('button', { name: /begin setup/i });
    expect(button).toBeInTheDocument();
  });

  it('Begin Setup button is disabled when agent name is empty', () => {
    renderWithProviders(<StepWelcome />);
    const button = screen.getByRole('button', { name: /begin setup/i });
    expect(button).toBeDisabled();
  });

  it('input filters out invalid characters (only lowercase and hyphens)', () => {
    renderWithProviders(<StepWelcome />);
    const input = screen.getByPlaceholderText('deployment-name') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'My-Agent_123!' } });
    // The onChange handler converts to lowercase and removes invalid chars
    // It should keep: m, y, -, a, g, e, n, t, 1, 2, 3
    expect(input.value).toMatch(/^[a-z0-9-]*$/);
  });

  it('shows hint text for naming rules', () => {
    renderWithProviders(<StepWelcome />);
    expect(screen.getByText(/Lowercase letters and hyphens only/)).toBeInTheDocument();
  });
});
