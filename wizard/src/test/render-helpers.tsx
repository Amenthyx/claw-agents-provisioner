/**
 * Test render helpers — wraps components with required providers.
 */
import { type ReactNode } from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { WizardProvider } from '../state/context';

/**
 * Wraps children with WizardProvider + MemoryRouter for test rendering.
 */
function AllProviders({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter>
      <WizardProvider>
        {children}
      </WizardProvider>
    </MemoryRouter>
  );
}

/**
 * Custom render that wraps components in all required providers.
 * Use this instead of `render` from @testing-library/react.
 */
export function renderWithProviders(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

/**
 * Wraps children only with MemoryRouter (no wizard state).
 * Useful for testing isolated UI components.
 */
function RouterOnly({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

export function renderWithRouter(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
) {
  return render(ui, { wrapper: RouterOnly, ...options });
}

export { render };
