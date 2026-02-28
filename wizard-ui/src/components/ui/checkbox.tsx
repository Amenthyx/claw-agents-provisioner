import { type InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../lib/cn';
import { Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  description?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, description, checked, onChange, ...props }, ref) => {
    return (
      <label
        className={cn(
          'flex items-start gap-3 cursor-pointer group',
          className
        )}
      >
        <div className="relative mt-0.5">
          <input
            ref={ref}
            type="checkbox"
            className="sr-only peer"
            checked={checked}
            onChange={onChange}
            {...props}
          />
          <div
            className={cn(
              'w-5 h-5 rounded border-2 flex items-center justify-center transition-all duration-200',
              checked
                ? 'bg-neon-cyan border-neon-cyan shadow-neon-sm'
                : 'bg-transparent border-cyber-border group-hover:border-neon-cyan/50'
            )}
          >
            <AnimatePresence>
              {checked && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  exit={{ scale: 0 }}
                  transition={{ duration: 0.15, ease: 'easeOut' }}
                >
                  <Check className="w-3 h-3 text-cyber-bg" strokeWidth={3} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
        {(label || description) && (
          <div className="flex flex-col">
            {label && (
              <span className="text-sm font-medium text-text-primary">{label}</span>
            )}
            {description && (
              <span className="text-xs text-text-secondary mt-0.5">{description}</span>
            )}
          </div>
        )}
      </label>
    );
  }
);

Checkbox.displayName = 'Checkbox';
