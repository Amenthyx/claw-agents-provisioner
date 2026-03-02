/**
 * Tests for the Security step component.
 */
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/render-helpers';
import { StepSecurity } from './StepSecurity';

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

// Mock the security sub-panels to avoid deep dependency chains
vi.mock('./security/UrlFilteringPanel', () => ({
  UrlFilteringPanel: () => <div data-testid="url-filtering-panel">URL Filtering Panel</div>,
}));
vi.mock('./security/ContentRulesPanel', () => ({
  ContentRulesPanel: () => <div data-testid="content-rules-panel">Content Rules Panel</div>,
}));
vi.mock('./security/PiiDetectionPanel', () => ({
  PiiDetectionPanel: () => <div data-testid="pii-detection-panel">PII Detection Panel</div>,
}));
vi.mock('./security/NetworkRulesPanel', () => ({
  NetworkRulesPanel: () => <div data-testid="network-rules-panel">Network Rules Panel</div>,
}));
vi.mock('./security/CompliancePanel', () => ({
  CompliancePanel: () => <div data-testid="compliance-panel">Compliance Panel</div>,
}));

describe('StepSecurity', () => {
  it('renders the master security toggle', () => {
    renderWithProviders(<StepSecurity />);
    expect(screen.getByText('Enable Security Layer')).toBeInTheDocument();
  });

  it('renders toggle description', () => {
    renderWithProviders(<StepSecurity />);
    expect(screen.getByText(/Activate content filtering, PII detection/)).toBeInTheDocument();
  });

  it('does not show security features when disabled', () => {
    renderWithProviders(<StepSecurity />);
    // Master toggle is off by default
    expect(screen.queryByText('Filtering')).not.toBeInTheDocument();
    expect(screen.queryByText('URL Filtering')).not.toBeInTheDocument();
  });

  it('shows security features when toggle is enabled', () => {
    renderWithProviders(<StepSecurity />);
    // Click the master toggle (it is a role=switch button)
    const toggle = screen.getByRole('switch');
    fireEvent.click(toggle);
    // Now the filtering section should appear
    expect(screen.getByText('Filtering')).toBeInTheDocument();
    expect(screen.getByText('URL Filtering')).toBeInTheDocument();
    expect(screen.getByText('Content Rules')).toBeInTheDocument();
    expect(screen.getByText('PII Detection')).toBeInTheDocument();
    expect(screen.getByText('Network Rules')).toBeInTheDocument();
  });

  it('shows compliance panel when security is enabled', () => {
    renderWithProviders(<StepSecurity />);
    const toggle = screen.getByRole('switch');
    fireEvent.click(toggle);
    expect(screen.getByTestId('compliance-panel')).toBeInTheDocument();
  });

  it('toggle has correct aria-checked attribute', () => {
    renderWithProviders(<StepSecurity />);
    const toggle = screen.getByRole('switch');
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'true');
  });
});
