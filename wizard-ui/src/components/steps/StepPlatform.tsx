import { Zap, Cpu, Minimize2, Globe, MessageCircle } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { PLATFORMS } from '../../lib/types';
import type { Platform } from '../../lib/types';

const iconMap: Record<string, React.ReactNode> = {
  'zap': <Zap className="w-6 h-6" />,
  'cpu': <Cpu className="w-6 h-6" />,
  'minimize-2': <Minimize2 className="w-6 h-6" />,
  'globe': <Globe className="w-6 h-6" />,
  'message-circle': <MessageCircle className="w-6 h-6" />,
};

interface StepPlatformProps {
  selected: string;
  onSelect: (platformId: string) => void;
}

export function StepPlatform({ selected, onSelect }: StepPlatformProps) {
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-[#e0e0e0] mb-2">Select Agent Platform</h2>
        <p className="text-[#a0a0a0]">
          Choose the AI agent platform that best fits your needs. Each platform has
          different capabilities and resource requirements.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {PLATFORMS.map((platform) => (
          <PlatformCard
            key={platform.id}
            platform={platform}
            isSelected={selected === platform.id}
            onClick={() => onSelect(platform.id)}
          />
        ))}
      </div>
    </div>
  );
}

function PlatformCard({
  platform,
  isSelected,
  onClick,
}: {
  platform: Platform;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <Card
      selected={isSelected}
      hoverable
      onClick={onClick}
      className="relative overflow-hidden"
    >
      {isSelected && (
        <div className="absolute top-3 right-3">
          <Badge variant="accent">Selected</Badge>
        </div>
      )}
      <CardContent className="pt-6">
        <div className="flex items-start gap-4 mb-4">
          <div className={`
            w-12 h-12 rounded-xl flex items-center justify-center transition-colors
            ${isSelected ? 'bg-[#00d4aa]/20 text-[#00d4aa]' : 'bg-[#1a1a2e] text-[#a0a0a0]'}
          `}>
            {iconMap[platform.icon] || <Cpu className="w-6 h-6" />}
          </div>
          <div>
            <h3 className="text-lg font-semibold text-[#e0e0e0]">{platform.name}</h3>
            <div className="flex items-center gap-2 mt-1">
              <Badge>{platform.language}</Badge>
              <Badge>{platform.memory}</Badge>
              <Badge>:{platform.port}</Badge>
            </div>
          </div>
        </div>

        <p className="text-sm text-[#a0a0a0] mb-4 leading-relaxed">
          {platform.description}
        </p>

        <div className="flex flex-wrap gap-1.5">
          {platform.features.map((feature) => (
            <span
              key={feature}
              className="text-xs px-2 py-0.5 rounded bg-[#1a1a2e] text-[#a0a0a0] border border-[#2a2a4e]"
            >
              {feature}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
