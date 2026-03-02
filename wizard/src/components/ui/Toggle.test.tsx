/**
 * Tests for the Toggle UI component.
 */
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent, render } from '@testing-library/react';
import { Toggle } from './Toggle';

describe('Toggle', () => {
  it('renders as a switch role', () => {
    render(<Toggle enabled={false} onChange={vi.fn()} />);
    expect(screen.getByRole('switch')).toBeInTheDocument();
  });

  it('has aria-checked=false when disabled', () => {
    render(<Toggle enabled={false} onChange={vi.fn()} />);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false');
  });

  it('has aria-checked=true when enabled', () => {
    render(<Toggle enabled={true} onChange={vi.fn()} />);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true');
  });

  it('calls onChange with opposite value when clicked', () => {
    const onChange = vi.fn();
    render(<Toggle enabled={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole('switch'));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('calls onChange with false when toggling off', () => {
    const onChange = vi.fn();
    render(<Toggle enabled={true} onChange={onChange} />);
    fireEvent.click(screen.getByRole('switch'));
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it('renders label when provided', () => {
    render(<Toggle enabled={false} onChange={vi.fn()} label="Enable Feature" />);
    expect(screen.getByText('Enable Feature')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(<Toggle enabled={false} onChange={vi.fn()} description="Some description" />);
    expect(screen.getByText('Some description')).toBeInTheDocument();
  });

  it('renders both label and description', () => {
    render(
      <Toggle enabled={false} onChange={vi.fn()} label="Label" description="Description" />,
    );
    expect(screen.getByText('Label')).toBeInTheDocument();
    expect(screen.getByText('Description')).toBeInTheDocument();
  });

  it('does not render label/description area when neither provided', () => {
    const { container } = render(<Toggle enabled={false} onChange={vi.fn()} />);
    const button = container.querySelector('[role="switch"]');
    // The button should have the toggle track div but no text children
    expect(button?.textContent).toBe('');
  });

  it('is disabled when disabled prop is true', () => {
    render(<Toggle enabled={false} onChange={vi.fn()} disabled />);
    expect(screen.getByRole('switch')).toBeDisabled();
  });

  it('applies accent color when enabled', () => {
    const { container } = render(<Toggle enabled={true} onChange={vi.fn()} />);
    const track = container.querySelector('.bg-accent');
    expect(track).toBeInTheDocument();
  });

  it('does not call onChange when disabled', () => {
    const onChange = vi.fn();
    render(<Toggle enabled={false} onChange={onChange} disabled />);
    fireEvent.click(screen.getByRole('switch'));
    expect(onChange).not.toHaveBeenCalled();
  });
});
