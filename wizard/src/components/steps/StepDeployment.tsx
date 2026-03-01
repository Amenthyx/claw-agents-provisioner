import { Container, Monitor, Server, Terminal } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWizard } from '../../state/context';
import { SelectionCard } from '../ui/Card';
import { Input } from '../ui/Input';
import { Badge } from '../ui/Badge';
import { stagger, fadeInUp, fadeIn } from '../../lib/motion';

const METHODS = [
  {
    id: 'docker',
    name: 'Docker',
    icon: Container,
    description: 'Containerized deployment with Docker Compose',
    benefits: ['Isolated environment', 'Easy scaling', 'Reproducible builds'],
    requirements: 'Docker Engine 24+',
  },
  {
    id: 'vagrant',
    name: 'Vagrant',
    icon: Monitor,
    description: 'Virtual machine deployment with Vagrant',
    benefits: ['Full OS isolation', 'Portable VMs', 'Multi-provider support'],
    requirements: 'Vagrant 2.4+ & VirtualBox',
  },
  {
    id: 'local',
    name: 'Local',
    icon: Terminal,
    description: 'Direct installation on the host system',
    benefits: ['Fastest performance', 'Direct GPU access', 'No overhead'],
    requirements: 'Node.js 20+ or Python 3.11+',
  },
  {
    id: 'ssh',
    name: 'SSH Remote',
    icon: Server,
    description: 'Deploy to a remote server over SSH',
    benefits: ['Remote deployment', 'Cloud-ready', 'Centralized management'],
    requirements: 'SSH access to target server',
  },
] as const;

export function StepDeployment() {
  const { state, setDeploymentMethod, setSshCredentials } = useWizard();

  return (
    <div className="space-y-4">
      <motion.div variants={stagger} initial="initial" animate="animate" className="grid grid-cols-2 gap-3">
        {METHODS.map((m) => {
          const selected = state.deploymentMethod === m.id;
          return (
            <motion.div key={m.id} variants={fadeInUp}>
              <SelectionCard
                selected={selected}
                onClick={() => setDeploymentMethod(m.id)}
                className="h-full"
              >
                <m.icon size={20} className={selected ? 'text-accent' : 'text-text-muted'} />
                <h3 className="text-sm font-medium text-text-primary mt-2">{m.name}</h3>
                <p className="text-xs text-text-secondary mt-1">{m.description}</p>
                <div className="flex flex-wrap gap-1 mt-2">
                  {m.benefits.map((b) => (
                    <Badge key={b} variant="default">{b}</Badge>
                  ))}
                </div>
                <p className="text-xs text-text-muted mt-2">{m.requirements}</p>
              </SelectionCard>
            </motion.div>
          );
        })}
      </motion.div>

      {/* SSH Credentials */}
      <AnimatePresence>
        {state.deploymentMethod === 'ssh' && (
          <motion.div
            variants={fadeIn}
            initial="initial"
            animate="animate"
            exit="exit"
            className="rounded-xl border border-border-base bg-surface-1 p-5 space-y-4"
          >
            <h3 className="text-sm font-medium text-text-primary">SSH Credentials</h3>
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Host"
                placeholder="192.168.1.100"
                value={state.sshCredentials.host}
                onChange={(e) => setSshCredentials({ host: e.target.value })}
              />
              <Input
                label="Port"
                type="number"
                placeholder="22"
                value={String(state.sshCredentials.port)}
                onChange={(e) => setSshCredentials({ port: parseInt(e.target.value) || 22 })}
              />
            </div>
            <Input
              label="Username"
              placeholder="deploy"
              value={state.sshCredentials.username}
              onChange={(e) => setSshCredentials({ username: e.target.value })}
            />
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setSshCredentials({ authMethod: 'password' })}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                  state.sshCredentials.authMethod === 'password'
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border-base text-text-secondary hover:bg-surface-2'
                }`}
              >
                Password
              </button>
              <button
                type="button"
                onClick={() => setSshCredentials({ authMethod: 'key' })}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                  state.sshCredentials.authMethod === 'key'
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border-base text-text-secondary hover:bg-surface-2'
                }`}
              >
                Private Key
              </button>
            </div>
            {state.sshCredentials.authMethod === 'password' ? (
              <Input
                label="Password"
                isPassword
                placeholder="••••••••"
                value={state.sshCredentials.password}
                onChange={(e) => setSshCredentials({ password: e.target.value })}
              />
            ) : (
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">Private Key (PEM)</label>
                <textarea
                  rows={4}
                  placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                  value={state.sshCredentials.privateKey}
                  onChange={(e) => setSshCredentials({ privateKey: e.target.value })}
                  className="w-full rounded-lg border border-border-base bg-surface-2 px-3 py-2 text-xs font-mono text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/30"
                />
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
