import { ArrowRight, Cpu, Layers, Rocket, Shield } from 'lucide-react';
import { motion } from 'framer-motion';
import { useWizard } from '../../state/context';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { stagger, fadeInUp } from '../../lib/motion';

const features = [
  { icon: Layers, title: '5 Agent Platforms', desc: 'Rust, TypeScript, Go, Node.js, Python' },
  { icon: Cpu, title: 'Hardware Detection', desc: 'Auto-detect CPU, RAM, GPU capabilities' },
  { icon: Rocket, title: 'One-Click Deploy', desc: 'Docker, Vagrant, Local, or SSH Remote' },
  { icon: Shield, title: 'Enterprise Security', desc: 'PII detection, GDPR, HIPAA, PCI-DSS' },
];

export function StepWelcome() {
  const { state, setAgentName, nextStep, canProceedNow } = useWizard();

  return (
    <div className="flex flex-col items-center text-center pt-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="mb-6"
      >
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/10 text-accent">
          <Layers size={32} />
        </div>
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.4 }}
        className="text-3xl font-bold tracking-tight text-text-primary"
      >
        Welcome to XClaw
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.4 }}
        className="mt-3 max-w-md text-sm text-text-secondary leading-relaxed"
      >
        Enterprise AI agent infrastructure in minutes. This wizard will guide you through
        hardware detection, platform selection, LLM configuration, and deployment.
      </motion.p>

      {/* Agent Name Input */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.4 }}
        className="mt-8 w-full max-w-sm"
      >
        <Input
          label="XClaw Name"
          placeholder="deployment-name"
          value={state.agentName}
          onChange={(e) => {
            const v = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '');
            setAgentName(v);
          }}
          hint="Lowercase letters and hyphens only (e.g. my-agent)"
          className="text-center"
        />
      </motion.div>

      <motion.div
        variants={stagger}
        initial="initial"
        animate="animate"
        className="mt-8 grid w-full max-w-lg grid-cols-2 gap-3"
      >
        {features.map((f) => (
          <motion.div
            key={f.title}
            variants={fadeInUp}
            className="rounded-xl border border-border-base bg-surface-1 p-4 text-left"
          >
            <f.icon size={18} className="text-accent mb-2" />
            <p className="text-sm font-medium text-text-primary">{f.title}</p>
            <p className="text-xs text-text-muted mt-0.5">{f.desc}</p>
          </motion.div>
        ))}
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mt-10"
      >
        <Button
          size="lg"
          onClick={nextStep}
          disabled={!canProceedNow}
          iconRight={<ArrowRight size={16} />}
        >
          Begin Setup
        </Button>
      </motion.div>
    </div>
  );
}
