import { Container, Server, MonitorCog } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { staggerContainer, cardVariant, fadeInUp } from '../../lib/motion';

interface StepDeploymentProps {
  selected: 'docker' | 'vagrant' | 'local';
  onSelect: (method: 'docker' | 'vagrant' | 'local') => void;
}

export function StepDeployment({ selected, onSelect }: StepDeploymentProps) {
  return (
    <div>
      <motion.div className="mb-8" variants={fadeInUp} initial="initial" animate="animate">
        <h2 className="text-2xl font-bold text-text-primary mb-2">Deployment Method</h2>
        <p className="text-text-secondary">
          Choose how to deploy your agent platform. Docker is recommended for most
          use cases.
        </p>
      </motion.div>

      <motion.div
        className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        {/* Docker */}
        <motion.div variants={cardVariant}>
          <Card
            selected={selected === 'docker'}
            hoverable
            onClick={() => onSelect('docker')}
            className="relative h-full"
          >
            {selected === 'docker' && (
              <div className="absolute top-4 right-4">
                <Badge variant="accent">Selected</Badge>
              </div>
            )}
            <CardContent className="pt-8 pb-8">
              <div className={`
                w-16 h-16 rounded-2xl flex items-center justify-center mb-6
                ${selected === 'docker' ? 'bg-neon-cyan/20 text-neon-cyan' : 'bg-cyber-bg-surface text-text-secondary'}
                transition-colors
              `}>
                <Container className="w-8 h-8" />
              </div>

              <h3 className="text-xl font-semibold text-text-primary mb-2">Docker</h3>
              <p className="text-sm text-text-secondary mb-6 leading-relaxed">
                Containerized deployment using Docker Compose. Fast startup, minimal
                overhead, and easy scaling.
              </p>

              <div className="space-y-2">
                <Feature text="Fast startup (~30 seconds)" />
                <Feature text="Minimal resource overhead" />
                <Feature text="Easy horizontal scaling" />
                <Feature text="Built-in networking" />
                <Feature text="Volume persistence" />
              </div>

              <div className="mt-6 pt-4 border-t border-cyber-border">
                <p className="text-xs text-text-muted font-mono">
                  Requires: Docker Engine 20.10+ and Docker Compose v2
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Vagrant */}
        <motion.div variants={cardVariant}>
          <Card
            selected={selected === 'vagrant'}
            hoverable
            onClick={() => onSelect('vagrant')}
            className="relative h-full"
          >
            {selected === 'vagrant' && (
              <div className="absolute top-4 right-4">
                <Badge variant="accent">Selected</Badge>
              </div>
            )}
            <CardContent className="pt-8 pb-8">
              <div className={`
                w-16 h-16 rounded-2xl flex items-center justify-center mb-6
                ${selected === 'vagrant' ? 'bg-neon-cyan/20 text-neon-cyan' : 'bg-cyber-bg-surface text-text-secondary'}
                transition-colors
              `}>
                <Server className="w-8 h-8" />
              </div>

              <h3 className="text-xl font-semibold text-text-primary mb-2">Vagrant</h3>
              <p className="text-sm text-text-secondary mb-6 leading-relaxed">
                Full virtual machine deployment using Vagrant. Complete isolation with
                dedicated OS.
              </p>

              <div className="space-y-2">
                <Feature text="Full OS isolation" />
                <Feature text="Hardware-level security" />
                <Feature text="Reproducible environments" />
                <Feature text="Multi-provider support" />
                <Feature text="Snapshot & rollback" />
              </div>

              <div className="mt-6 pt-4 border-t border-cyber-border">
                <p className="text-xs text-text-muted font-mono">
                  Requires: Vagrant 2.3+ and VirtualBox/VMware
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Local Hardware */}
        <motion.div variants={cardVariant}>
          <Card
            selected={selected === 'local'}
            hoverable
            onClick={() => onSelect('local')}
            className="relative h-full"
          >
            {selected === 'local' && (
              <div className="absolute top-4 right-4">
                <Badge variant="accent">Selected</Badge>
              </div>
            )}
            <CardContent className="pt-8 pb-8">
              <div className={`
                w-16 h-16 rounded-2xl flex items-center justify-center mb-6
                ${selected === 'local' ? 'bg-neon-cyan/20 text-neon-cyan' : 'bg-cyber-bg-surface text-text-secondary'}
                transition-colors
              `}>
                <MonitorCog className="w-8 h-8" />
              </div>

              <h3 className="text-xl font-semibold text-text-primary mb-2">Local Hardware</h3>
              <p className="text-sm text-text-secondary mb-6 leading-relaxed">
                Install directly on your machine. No virtualization layer — maximum
                performance with native hardware access.
              </p>

              <div className="space-y-2">
                <Feature text="Native performance" />
                <Feature text="Direct hardware access" />
                <Feature text="No virtualization overhead" />
                <Feature text="Full system integration" />
                <Feature text="Custom environment control" />
              </div>

              <div className="mt-6 pt-4 border-t border-cyber-border">
                <p className="text-xs text-text-muted font-mono">
                  Requires: Language runtime (Rust, Go, Node.js, or Python)
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </div>
  );
}

function Feature({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-text-secondary font-mono">
      <div className="w-1.5 h-1.5 rounded-full bg-neon-cyan" />
      {text}
    </div>
  );
}
