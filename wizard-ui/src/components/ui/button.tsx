import { type ButtonHTMLAttributes, forwardRef } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0a0a0f]',
  {
    variants: {
      variant: {
        primary:
          'bg-[#00d4aa] text-[#0a0a0f] hover:bg-[#00f5c4] focus:ring-[#00d4aa] font-semibold',
        secondary:
          'bg-[#1a1a2e] text-[#e0e0e0] border border-[#2a2a4e] hover:bg-[#2a2a4e] hover:border-[#00d4aa]/30 focus:ring-[#00d4aa]',
        outline:
          'bg-transparent text-[#e0e0e0] border border-[#2a2a4e] hover:border-[#00d4aa] hover:text-[#00d4aa] focus:ring-[#00d4aa]',
        danger:
          'bg-[#ff4757] text-white hover:bg-[#ff6b7a] focus:ring-[#ff4757]',
        ghost:
          'bg-transparent text-[#a0a0a0] hover:text-[#e0e0e0] hover:bg-[#1a1a2e] focus:ring-[#00d4aa]',
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
