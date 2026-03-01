import type { Transition, Variants } from 'framer-motion';

export const ease: Transition = {
  type: 'tween',
  ease: [0.25, 0.1, 0.25, 1],
  duration: 0.3,
};

export const easeOut: Transition = {
  type: 'tween',
  ease: [0, 0, 0.2, 1],
  duration: 0.25,
};

export const stagger: Variants = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.05,
    },
  },
};

export const fadeIn: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: ease },
  exit: { opacity: 0, transition: easeOut },
};

export const fadeInUp: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: ease },
  exit: { opacity: 0, y: -8, transition: easeOut },
};

export const fadeInScale: Variants = {
  initial: { opacity: 0, scale: 0.96 },
  animate: { opacity: 1, scale: 1, transition: ease },
  exit: { opacity: 0, scale: 0.96, transition: easeOut },
};

export const slideIn: Variants = {
  initial: { opacity: 0, x: 16 },
  animate: { opacity: 1, x: 0, transition: ease },
  exit: { opacity: 0, x: -16, transition: easeOut },
};
