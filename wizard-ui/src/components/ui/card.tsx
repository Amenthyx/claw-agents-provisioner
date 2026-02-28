import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '../../lib/cn';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  selected?: boolean;
  hoverable?: boolean;
}

export function Card({ className, selected, hoverable = false, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border glass-card transition-all duration-200',
        selected
          ? 'border-neon-cyan border-glow-cyan shadow-neon-sm'
          : 'border-cyber-border',
        hoverable && !selected && 'hover:border-neon-cyan/50 hover:shadow-neon-sm hover:scale-[1.01] hover:-translate-y-0.5 cursor-pointer',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('px-6 pt-6 pb-2', className)} {...props}>
      {children}
    </div>
  );
}

export function CardTitle({ className, children, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={cn('text-lg font-semibold text-text-primary', className)} {...props}>
      {children}
    </h3>
  );
}

export function CardDescription({ className, children, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn('text-sm text-text-secondary mt-1', className)} {...props}>
      {children}
    </p>
  );
}

export function CardContent({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('px-6 py-4', className)} {...props}>
      {children}
    </div>
  );
}

export function CardFooter({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('px-6 pb-6 pt-2 flex items-center', className)} {...props}>
      {children}
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string | ReactNode;
  icon?: ReactNode;
  className?: string;
}

export function StatCard({ label, value, icon, className }: StatCardProps) {
  return (
    <Card className={cn('p-4', className)}>
      <div className="flex items-center gap-3">
        {icon && (
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-neon-cyan/10 text-neon-cyan">
            {icon}
          </div>
        )}
        <div>
          <p className="text-xs text-text-secondary uppercase tracking-wider">{label}</p>
          <p className="text-lg font-semibold text-text-primary font-mono mt-0.5">{value}</p>
        </div>
      </div>
    </Card>
  );
}
