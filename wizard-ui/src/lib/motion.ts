import type { Variants, Transition } from 'framer-motion';

export const pageVariants: Variants = {
  initial: {
    opacity: 0,
    x: 20,
    filter: 'blur(4px)',
  },
  animate: {
    opacity: 1,
    x: 0,
    filter: 'blur(0px)',
  },
  exit: {
    opacity: 0,
    x: -20,
    filter: 'blur(4px)',
  },
};

export const pageTransition: Transition = {
  duration: 0.35,
  ease: 'easeOut',
};

export const staggerContainer: Variants = {
  animate: {
    transition: {
      staggerChildren: 0.08,
    },
  },
};

export const cardVariant: Variants = {
  initial: {
    opacity: 0,
    y: 16,
    scale: 0.97,
  },
  animate: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.35,
      ease: 'easeOut',
    },
  },
};

export const fadeInUp: Variants = {
  initial: {
    opacity: 0,
    y: 12,
  },
  animate: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.4,
      ease: 'easeOut',
    },
  },
};

export const glowPulse: Variants = {
  animate: {
    boxShadow: [
      '0 0 4px #00ffcc20, 0 0 8px #00ffcc10',
      '0 0 12px #00ffcc40, 0 0 24px #00ffcc20, 0 0 4px #00ffcc',
      '0 0 4px #00ffcc20, 0 0 8px #00ffcc10',
    ],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
};
