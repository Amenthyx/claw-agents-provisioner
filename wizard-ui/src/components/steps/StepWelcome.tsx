import { Rocket, Shield, Cpu, Boxes } from 'lucide-react';
import { Button } from '../ui/button';

interface StepWelcomeProps {
  onNext: () => void;
}

export function StepWelcome({ onNext }: StepWelcomeProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      {/* Logo */}
      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#00d4aa] to-[#00f5c4] flex items-center justify-center mb-8 shadow-2xl shadow-[#00d4aa]/20">
        <span className="text-[#0a0a0f] font-bold text-3xl">X</span>
      </div>

      <h1 className="text-4xl sm:text-5xl font-bold text-[#e0e0e0] mb-4">
        Welcome to <span className="text-[#00d4aa]">XClaw</span>
      </h1>

      <p className="text-xl text-[#a0a0a0] max-w-2xl mb-3">
        One-command deployment of enterprise AI agents
      </p>

      <p className="text-sm text-[#666] max-w-xl mb-10">
        This wizard will guide you through configuring and deploying your AI agent
        platform. Select your agent, configure hardware, choose your LLM strategy,
        and deploy in minutes.
      </p>

      {/* Feature highlights */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 max-w-4xl mb-12">
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
      </div>

      <Button size="xl" onClick={onNext}>
        Get Started
        <Rocket className="w-5 h-5" />
      </Button>
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
    <div className="flex flex-col items-center p-5 rounded-xl border border-[#2a2a4e] bg-[#16213e]/50 hover:border-[#00d4aa]/30 transition-colors">
      <div className="w-10 h-10 rounded-lg bg-[#00d4aa]/10 text-[#00d4aa] flex items-center justify-center mb-3">
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-[#e0e0e0] mb-1">{title}</h3>
      <p className="text-xs text-[#a0a0a0]">{description}</p>
    </div>
  );
}
