import { Container, Server } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';

interface StepDeploymentProps {
  selected: 'docker' | 'vagrant';
  onSelect: (method: 'docker' | 'vagrant') => void;
}

export function StepDeployment({ selected, onSelect }: StepDeploymentProps) {
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-[#e0e0e0] mb-2">Deployment Method</h2>
        <p className="text-[#a0a0a0]">
          Choose how to deploy your agent platform. Docker is recommended for most
          use cases.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl">
        {/* Docker */}
        <Card
          selected={selected === 'docker'}
          hoverable
          onClick={() => onSelect('docker')}
          className="relative"
        >
          {selected === 'docker' && (
            <div className="absolute top-4 right-4">
              <Badge variant="accent">Selected</Badge>
            </div>
          )}
          <CardContent className="pt-8 pb-8">
            <div className={`
              w-16 h-16 rounded-2xl flex items-center justify-center mb-6
              ${selected === 'docker' ? 'bg-[#00d4aa]/20 text-[#00d4aa]' : 'bg-[#1a1a2e] text-[#a0a0a0]'}
              transition-colors
            `}>
              <Container className="w-8 h-8" />
            </div>

            <h3 className="text-xl font-semibold text-[#e0e0e0] mb-2">Docker</h3>
            <p className="text-sm text-[#a0a0a0] mb-6 leading-relaxed">
              Containerized deployment using Docker Compose. Fast startup, minimal
              overhead, and easy scaling. Ideal for development and production.
            </p>

            <div className="space-y-2">
              <Feature text="Fast startup (~30 seconds)" />
              <Feature text="Minimal resource overhead" />
              <Feature text="Easy horizontal scaling" />
              <Feature text="Built-in networking" />
              <Feature text="Volume persistence" />
            </div>

            <div className="mt-6 pt-4 border-t border-[#2a2a4e]">
              <p className="text-xs text-[#666]">
                Requires: Docker Engine 20.10+ and Docker Compose v2
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Vagrant */}
        <Card
          selected={selected === 'vagrant'}
          hoverable
          onClick={() => onSelect('vagrant')}
          className="relative"
        >
          {selected === 'vagrant' && (
            <div className="absolute top-4 right-4">
              <Badge variant="accent">Selected</Badge>
            </div>
          )}
          <CardContent className="pt-8 pb-8">
            <div className={`
              w-16 h-16 rounded-2xl flex items-center justify-center mb-6
              ${selected === 'vagrant' ? 'bg-[#00d4aa]/20 text-[#00d4aa]' : 'bg-[#1a1a2e] text-[#a0a0a0]'}
              transition-colors
            `}>
              <Server className="w-8 h-8" />
            </div>

            <h3 className="text-xl font-semibold text-[#e0e0e0] mb-2">Vagrant</h3>
            <p className="text-sm text-[#a0a0a0] mb-6 leading-relaxed">
              Full virtual machine deployment using Vagrant. Complete isolation with
              dedicated OS. Best for compliance-heavy or air-gapped environments.
            </p>

            <div className="space-y-2">
              <Feature text="Full OS isolation" />
              <Feature text="Hardware-level security" />
              <Feature text="Reproducible environments" />
              <Feature text="Multi-provider support" />
              <Feature text="Snapshot & rollback" />
            </div>

            <div className="mt-6 pt-4 border-t border-[#2a2a4e]">
              <p className="text-xs text-[#666]">
                Requires: Vagrant 2.3+ and VirtualBox/VMware
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Feature({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-[#a0a0a0]">
      <div className="w-1.5 h-1.5 rounded-full bg-[#00d4aa]" />
      {text}
    </div>
  );
}
