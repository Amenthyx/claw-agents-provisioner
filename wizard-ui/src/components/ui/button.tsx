import { type ButtonHTMLAttributes, forwardRef } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-cyber-bg',
  {
    variants: {
      variant: {
        primary:
          'bg-neon-cyan text-cyber-bg hover:bg-neon-cyan-dim hover:shadow-neon-sm active:scale-[0.97] focus:ring-neon-cyan font-semibold',
        secondary:
          'bg-cyber-bg-surface text-text-primary border border-cyber-border hover:bg-cyber-bg-hover hover:border-neon-cyan/30 focus:ring-neon-cyan',
        outline:
          'bg-transparent text-text-primary border border-cyber-border hover:border-neon-cyan hover:text-neon-cyan hover:shadow-neon-sm focus:ring-neon-cyan',
        danger:
          'bg-status-error text-white hover:bg-status-error/80 focus:ring-status-error',
        ghost:
          'bg-transparent text-text-secondary hover:text-text-primary hover:bg-cyber-bg-surface focus:ring-neon-cyan',
      },
      size: {
        sm: 'px-3 py-1.5 text-sm',
        md: 'px-5 py-2.5 text-sm',
        lg: 'px-8 py-3 text-base',
        xl: 'px-10 py-4 text-lg',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';
