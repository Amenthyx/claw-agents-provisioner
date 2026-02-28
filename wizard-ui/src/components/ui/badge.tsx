import { type HTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/cn';

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-cyber-bg-surface text-text-secondary border border-cyber-border',
        success: 'bg-status-success/10 text-status-success border border-status-success/20',
        warning: 'bg-status-warning/10 text-status-warning border border-status-warning/20',
        error: 'bg-status-error/10 text-status-error border border-status-error/20',
        accent: 'bg-neon-cyan/10 text-neon-cyan border border-neon-cyan/20',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}
