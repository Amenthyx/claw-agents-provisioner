/**
 * Tests for the Input UI component.
 */
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent, render } from '@testing-library/react';
import { Input } from './Input';

describe('Input', () => {
  it('renders an input element', () => {
    render(<Input />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('renders label when provided', () => {
    render(<Input label="Username" />);
    expect(screen.getByText('Username')).toBeInTheDocument();
  });

  it('renders placeholder text', () => {
    render(<Input placeholder="Enter value" />);
    expect(screen.getByPlaceholderText('Enter value')).toBeInTheDocument();
  });

  it('renders hint text', () => {
    render(<Input hint="This is a hint" />);
    expect(screen.getByText('This is a hint')).toBeInTheDocument();
  });

  it('renders error text and hides hint', () => {
    render(<Input hint="Hint" error="This field is required" />);
    expect(screen.getByText('This field is required')).toBeInTheDocument();
    expect(screen.queryByText('Hint')).not.toBeInTheDocument();
  });

  it('applies error border class when error is present', () => {
    render(<Input error="Error" />);
    const input = screen.getByRole('textbox');
    expect(input.className).toContain('border-error');
  });

  it('handles value changes', () => {
    const onChange = vi.fn();
    render(<Input onChange={onChange} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'test' } });
    expect(onChange).toHaveBeenCalledOnce();
  });

  it('renders as password input when isPassword is true', () => {
    render(<Input isPassword data-testid="pwd" />);
    const input = screen.getByTestId('pwd');
    expect(input).toHaveAttribute('type', 'password');
  });

  it('toggles password visibility when eye icon is clicked', () => {
    render(<Input isPassword data-testid="pwd" />);
    const input = screen.getByTestId('pwd');
    expect(input).toHaveAttribute('type', 'password');
    // Click the toggle button
    const toggleButton = screen.getByRole('button');
    fireEvent.click(toggleButton);
    expect(input).toHaveAttribute('type', 'text');
    // Click again to hide
    fireEvent.click(toggleButton);
    expect(input).toHaveAttribute('type', 'password');
  });

  it('renders icon when provided', () => {
    render(<Input icon={<span data-testid="input-icon">I</span>} />);
    expect(screen.getByTestId('input-icon')).toBeInTheDocument();
  });

  it('forwards ref', () => {
    const ref = vi.fn();
    render(<Input ref={ref} />);
    expect(ref).toHaveBeenCalledWith(expect.any(HTMLInputElement));
  });

  it('passes through additional props', () => {
    render(<Input data-testid="custom" maxLength={10} />);
    const input = screen.getByTestId('custom');
    expect(input).toHaveAttribute('maxlength', '10');
  });
});
