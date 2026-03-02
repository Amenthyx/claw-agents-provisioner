/**
 * Tests for Card, SelectionCard, and StatCard UI components.
 */
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent, render } from '@testing-library/react';
import { Card, SelectionCard, StatCard } from './Card';

describe('Card', () => {
  it('renders children', () => {
    render(<Card>Card Content</Card>);
    expect(screen.getByText('Card Content')).toBeInTheDocument();
  });

  it('applies base classes', () => {
    const { container } = render(<Card>Content</Card>);
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('rounded-xl');
    expect(card.className).toContain('border');
  });

  it('accepts additional className', () => {
    const { container } = render(<Card className="extra-class">Content</Card>);
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('extra-class');
  });

  it('forwards ref', () => {
    const ref = vi.fn();
    render(<Card ref={ref}>Content</Card>);
    expect(ref).toHaveBeenCalledWith(expect.any(HTMLDivElement));
  });
});

describe('SelectionCard', () => {
  it('renders children', () => {
    render(<SelectionCard>Selection Content</SelectionCard>);
    expect(screen.getByText('Selection Content')).toBeInTheDocument();
  });

  it('has role=button', () => {
    render(<SelectionCard>Content</SelectionCard>);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('is focusable with tabIndex=0', () => {
    render(<SelectionCard>Content</SelectionCard>);
    expect(screen.getByRole('button')).toHaveAttribute('tabindex', '0');
  });

  it('calls onClick when clicked', () => {
    const onClick = vi.fn();
    render(<SelectionCard onClick={onClick}>Content</SelectionCard>);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('does not call onClick when disabled', () => {
    const onClick = vi.fn();
    render(<SelectionCard disabled onClick={onClick}>Content</SelectionCard>);
    fireEvent.click(screen.getByText('Content'));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('has tabIndex=-1 when disabled', () => {
    render(<SelectionCard disabled>Content</SelectionCard>);
    const el = screen.getByText('Content').closest('[role="button"]');
    expect(el).toHaveAttribute('tabindex', '-1');
  });

  it('applies accent border when selected', () => {
    render(<SelectionCard selected>Content</SelectionCard>);
    const button = screen.getByRole('button');
    expect(button.className).toContain('border-accent');
  });

  it('supports keyboard activation with Enter', () => {
    const onClick = vi.fn();
    render(<SelectionCard onClick={onClick}>Content</SelectionCard>);
    fireEvent.keyDown(screen.getByRole('button'), { key: 'Enter' });
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('supports keyboard activation with Space', () => {
    const onClick = vi.fn();
    render(<SelectionCard onClick={onClick}>Content</SelectionCard>);
    fireEvent.keyDown(screen.getByRole('button'), { key: ' ' });
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('does not activate on other keys', () => {
    const onClick = vi.fn();
    render(<SelectionCard onClick={onClick}>Content</SelectionCard>);
    fireEvent.keyDown(screen.getByRole('button'), { key: 'Tab' });
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe('StatCard', () => {
  it('renders label and value', () => {
    render(<StatCard icon={<span>I</span>} label="CPU" value="8 cores" />);
    expect(screen.getByText('CPU')).toBeInTheDocument();
    expect(screen.getByText('8 cores')).toBeInTheDocument();
  });

  it('renders icon', () => {
    render(<StatCard icon={<span data-testid="stat-icon">I</span>} label="RAM" value="32 GB" />);
    expect(screen.getByTestId('stat-icon')).toBeInTheDocument();
  });

  it('accepts additional className', () => {
    const { container } = render(
      <StatCard icon={<span>I</span>} label="L" value="V" className="my-class" />,
    );
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('my-class');
  });
});
