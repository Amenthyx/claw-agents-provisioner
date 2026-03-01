import { AnimatePresence, motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { fadeInUp } from '../../lib/motion';

interface StepTransitionProps {
  stepKey: number;
  children: ReactNode;
}

export function StepTransition({ stepKey, children }: StepTransitionProps) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={stepKey}
        variants={fadeInUp}
        initial="initial"
        animate="animate"
        exit="exit"
        className="flex-1"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
