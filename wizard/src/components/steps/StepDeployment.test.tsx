/**
 * Tests for the Deployment method step component.
 */
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/render-helpers';
import { StepDeployment } from './StepDeployment';

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

describe('StepDeployment', () => {
  it('renders all four deployment methods', () => {
    renderWithProviders(<StepDeployment />);
    expect(screen.getByText('Docker')).toBeInTheDocument();
    expect(screen.getByText('Vagrant')).toBeInTheDocument();
    expect(screen.getByText('Local')).toBeInTheDocument();
    expect(screen.getByText('SSH Remote')).toBeInTheDocument();
  });

  it('renders method descriptions', () => {
    renderWithProviders(<StepDeployment />);
    expect(screen.getByText('Containerized deployment with Docker Compose')).toBeInTheDocument();
    expect(screen.getByText('Virtual machine deployment with Vagrant')).toBeInTheDocument();
    expect(screen.getByText('Direct installation on the host system')).toBeInTheDocument();
    expect(screen.getByText('Deploy to a remote server over SSH')).toBeInTheDocument();
  });

  it('renders benefits as badges', () => {
    renderWithProviders(<StepDeployment />);
    expect(screen.getByText('Isolated environment')).toBeInTheDocument();
    expect(screen.getByText('Easy scaling')).toBeInTheDocument();
    expect(screen.getByText('Fastest performance')).toBeInTheDocument();
    expect(screen.getByText('Remote deployment')).toBeInTheDocument();
  });

  it('renders requirements text', () => {
    renderWithProviders(<StepDeployment />);
    expect(screen.getByText('Docker Engine 24+')).toBeInTheDocument();
    expect(screen.getByText('Vagrant 2.4+ & VirtualBox')).toBeInTheDocument();
  });

  it('does not show SSH credentials by default (docker selected)', () => {
    renderWithProviders(<StepDeployment />);
    // SSH fields should not be present
    expect(screen.queryByText('SSH Credentials')).not.toBeInTheDocument();
  });

  it('shows SSH credentials when SSH method is selected', () => {
    renderWithProviders(<StepDeployment />);
    // Click the SSH Remote option
    const sshButton = screen.getByText('SSH Remote').closest('[role="button"]');
    if (sshButton) {
      fireEvent.click(sshButton);
    }
    // SSH form fields should now appear
    expect(screen.getByText('SSH Credentials')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('192.168.1.100')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('deploy')).toBeInTheDocument();
  });

  it('SSH form has password and private key toggle', () => {
    renderWithProviders(<StepDeployment />);
    const sshButton = screen.getByText('SSH Remote').closest('[role="button"]');
    if (sshButton) {
      fireEvent.click(sshButton);
    }
    expect(screen.getByText('Password')).toBeInTheDocument();
    expect(screen.getByText('Private Key')).toBeInTheDocument();
  });

  it('SSH form shows private key textarea when Private Key is selected', () => {
    renderWithProviders(<StepDeployment />);
    const sshButton = screen.getByText('SSH Remote').closest('[role="button"]');
    if (sshButton) {
      fireEvent.click(sshButton);
    }
    // Click Private Key auth method
    const pkButton = screen.getByText('Private Key');
    fireEvent.click(pkButton);
    expect(screen.getByPlaceholderText(/BEGIN OPENSSH PRIVATE KEY/)).toBeInTheDocument();
  });
});
