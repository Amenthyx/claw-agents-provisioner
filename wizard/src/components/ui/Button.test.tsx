/**
 * Tests for the Button UI component.
 */
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent, render } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('renders button text', () => {
    render(<Button>Click Me</Button>);
    expect(screen.getByRole('button', { name: 'Click Me' })).toBeInTheDocument();
  });

  it('calls onClick handler when clicked', () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('is disabled when loading prop is true', () => {
    render(<Button loading>Loading</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('shows spinner when loading', () => {
    render(<Button loading>Loading</Button>);
    const button = screen.getByRole('button');
    const spinner = button.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  it('renders icon when provided', () => {
    render(<Button icon={<span data-testid="icon">I</span>}>With Icon</Button>);
    expect(screen.getByTestId('icon')).toBeInTheDocument();
  });

  it('renders iconRight when provided', () => {
    render(<Button iconRight={<span data-testid="icon-right">R</span>}>With Right Icon</Button>);
    expect(screen.getByTestId('icon-right')).toBeInTheDocument();
  });

  it('applies primary variant classes by default', () => {
    render(<Button>Primary</Button>);
    const button = screen.getByRole('button');
    expect(button.className).toContain('bg-accent');
  });

  it('applies ghost variant classes', () => {
    render(<Button variant="ghost">Ghost</Button>);
    const button = screen.getByRole('button');
    expect(button.className).toContain('bg-transparent');
  });

  it('applies outline variant classes', () => {
    render(<Button variant="outline">Outline</Button>);
    const button = screen.getByRole('button');
    expect(button.className).toContain('border');
  });

  it('applies size classes', () => {
    render(<Button size="lg">Large</Button>);
    const button = screen.getByRole('button');
    expect(button.className).toContain('h-10');
  });

  it('applies sm size classes', () => {
    render(<Button size="sm">Small</Button>);
    const button = screen.getByRole('button');
    expect(button.className).toContain('h-8');
  });

  it('does not call onClick when disabled', () => {
    const onClick = vi.fn();
    render(<Button disabled onClick={onClick}>Disabled</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('forwards ref', () => {
    const ref = vi.fn();
    render(<Button ref={ref}>Ref</Button>);
    expect(ref).toHaveBeenCalledWith(expect.any(HTMLButtonElement));
  });

  it('accepts additional className', () => {
    render(<Button className="extra-class">Custom</Button>);
    const button = screen.getByRole('button');
    expect(button.className).toContain('extra-class');
  });
});
