import { type HTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/cn';

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-[#1a1a2e] text-[#a0a0a0] border border-[#2a2a4e]',
        success: 'bg-[#2ed573]/10 text-[#2ed573] border border-[#2ed573]/20',
        warning: 'bg-[#ffa502]/10 text-[#ffa502] border border-[#ffa502]/20',
        error: 'bg-[#ff4757]/10 text-[#ff4757] border border-[#ff4757]/20',
        accent: 'bg-[#00d4aa]/10 text-[#00d4aa] border border-[#00d4aa]/20',
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
