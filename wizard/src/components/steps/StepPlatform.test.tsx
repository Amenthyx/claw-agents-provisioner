/**
 * Tests for the Platform selection step component.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/render-helpers';
import { StepPlatform } from './StepPlatform';

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
    getPlatforms: vi.fn().mockRejectedValue(new Error('no backend')),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('StepPlatform', () => {
  it('renders all fallback platforms', () => {
    renderWithProviders(<StepPlatform />);
    expect(screen.getByText('ZeroClaw')).toBeInTheDocument();
    expect(screen.getByText('NanoClaw')).toBeInTheDocument();
    expect(screen.getByText('PicoClaw')).toBeInTheDocument();
    expect(screen.getByText('OpenClaw')).toBeInTheDocument();
    expect(screen.getByText('Parlant')).toBeInTheDocument();
  });

  it('renders platform languages', () => {
    renderWithProviders(<StepPlatform />);
    expect(screen.getByText('Rust')).toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
    expect(screen.getByText('Go')).toBeInTheDocument();
    expect(screen.getByText('Node.js')).toBeInTheDocument();
    expect(screen.getByText('Python')).toBeInTheDocument();
  });

  it('renders platform descriptions', () => {
    renderWithProviders(<StepPlatform />);
    expect(screen.getByText('High-performance minimal agent')).toBeInTheDocument();
    expect(screen.getByText('Ultra-lightweight data agent')).toBeInTheDocument();
  });

  it('renders platform tiers', () => {
    renderWithProviders(<StepPlatform />);
    const lightweightBadges = screen.getAllByText('lightweight');
    expect(lightweightBadges.length).toBeGreaterThanOrEqual(2); // zeroclaw + picoclaw
    const standardBadges = screen.getAllByText('standard');
    expect(standardBadges.length).toBeGreaterThanOrEqual(2);
  });

  it('renders platform features as badges', () => {
    renderWithProviders(<StepPlatform />);
    expect(screen.getByText('Minimal footprint')).toBeInTheDocument();
    expect(screen.getByText('Claude-native')).toBeInTheDocument();
    expect(screen.getByText('50+ integrations')).toBeInTheDocument();
    expect(screen.getByText('Guidelines engine')).toBeInTheDocument();
  });

  it('renders memory and port info', () => {
    renderWithProviders(<StepPlatform />);
    expect(screen.getByText('Memory: 512 MB')).toBeInTheDocument();
    expect(screen.getByText('Port: 3100')).toBeInTheDocument();
  });

  it('platforms have selectable role=button', () => {
    renderWithProviders(<StepPlatform />);
    const buttons = screen.getAllByRole('button');
    // Each platform card should be a button
    expect(buttons.length).toBeGreaterThanOrEqual(5);
  });
});
