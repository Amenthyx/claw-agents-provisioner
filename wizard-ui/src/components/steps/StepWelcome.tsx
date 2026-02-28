import { Rocket, Shield, Cpu, Boxes } from 'lucide-react';
import { motion } from 'framer-motion';
import { Button } from '../ui/button';
import { TypewriterText } from '../ui/typewriter-text';
import { staggerContainer, cardVariant, fadeInUp } from '../../lib/motion';

interface StepWelcomeProps {
  onNext: () => void;
}

export function StepWelcome({ onNext }: StepWelcomeProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      {/* Logo */}
      <motion.div
        className="w-20 h-20 rounded-2xl bg-gradient-to-br from-neon-cyan to-neon-cyan-dim flex items-center justify-center mb-8 shadow-neon-lg"
        initial={{ scale: 0, rotate: -180 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
      >
        <motion.span
          className="text-cyber-bg font-bold text-3xl"
          animate={{
            textShadow: [
              '0 0 4px #06060b',
              '0 0 8px #06060b',
              '0 0 4px #06060b',
            ],
          }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          X
        </motion.span>
      </motion.div>

      <motion.h1
        className="text-4xl sm:text-5xl font-bold text-text-primary mb-4"
        variants={fadeInUp}
        initial="initial"
        animate="animate"
      >
        Welcome to{' '}
        <TypewriterText
          text="XClaw"
          speed={80}
          className="text-neon-cyan text-glow-cyan"
        />
      </motion.h1>

      <motion.p
        className="text-xl text-text-secondary max-w-2xl mb-3"
        variants={fadeInUp}
        initial="initial"
        animate="animate"
      >
        One-command deployment of enterprise AI agents
      </motion.p>

      <motion.p
        className="text-sm text-text-muted max-w-xl mb-10"
        variants={fadeInUp}
        initial="initial"
        animate="animate"
      >
        This wizard will guide you through configuring and deploying your AI agent
        platform. Select your agent, configure hardware, choose your LLM strategy,
        and deploy in minutes.
      </motion.p>

      {/* Feature highlights */}
      <motion.div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 max-w-4xl mb-12"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        <FeatureCard
          icon={<Boxes className="w-5 h-5" />}
          title="5 Agent Platforms"
          description="From ultra-light to full enterprise"
        />
        <FeatureCard
          icon={<Cpu className="w-5 h-5" />}
          title="Smart Hardware Detection"
          description="Auto-optimized for your system"
        />
        <FeatureCard
          icon={<Rocket className="w-5 h-5" />}
          title="One-Click Deploy"
          description="Docker or Vagrant deployment"
        />
        <FeatureCard
          icon={<Shield className="w-5 h-5" />}
          title="Enterprise Security"
          description="PII detection, compliance, filtering"
        />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6, duration: 0.4 }}
      >
        <Button
          size="xl"
          onClick={onNext}
          className="bg-gradient-to-r from-neon-cyan to-neon-magenta text-cyber-bg font-semibold shadow-neon-lg hover:shadow-neon-lg active:scale-[0.97]"
        >
          Get Started
          <Rocket className="w-5 h-5" />
        </Button>
      </motion.div>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <motion.div
      className="flex flex-col items-center p-5 rounded-xl border border-cyber-border glass-card hover:border-neon-cyan/30 hover:shadow-neon-sm transition-all"
      variants={cardVariant}
    >
      <div className="w-10 h-10 rounded-lg bg-neon-cyan/10 text-neon-cyan flex items-center justify-center mb-3">
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-text-primary mb-1">{title}</h3>
      <p className="text-xs text-text-secondary">{description}</p>
    </motion.div>
  );
}
