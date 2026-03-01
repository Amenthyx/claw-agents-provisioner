import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { useWizard } from '../../../state/context';
import { PII_TYPES, PII_ACTIONS } from '../../../data/security';
import { Card } from '../../ui/Card';
import { Input } from '../../ui/Input';
import { Button } from '../../ui/Button';
import { Badge } from '../../ui/Badge';
import { Toggle } from '../../ui/Toggle';
import { SelectionCard } from '../../ui/Card';
import type { PiiAction } from '../../../state/types';

export function PiiDetectionPanel() {
  const { state, setSecurityConfig } = useWizard();
  const cfg = state.securityConfig.piiDetection;
  const [newPattern, setNewPattern] = useState('');

  const togglePiiType = (typeId: string) => {
    setSecurityConfig({
      piiDetection: {
        ...cfg,
        types: { ...cfg.types, [typeId]: !cfg.types[typeId] },
      },
    });
  };

  const setAction = (action: PiiAction) => {
    setSecurityConfig({
      piiDetection: { ...cfg, action },
    });
  };

  const addPattern = () => {
    const trimmed = newPattern.trim();
    if (trimmed && !cfg.customPatterns.includes(trimmed)) {
      setSecurityConfig({
        piiDetection: { ...cfg, customPatterns: [...cfg.customPatterns, trimmed] },
      });
      setNewPattern('');
    }
  };

  const removePattern = (pattern: string) => {
    setSecurityConfig({
      piiDetection: { ...cfg, customPatterns: cfg.customPatterns.filter((p) => p !== pattern) },
    });
  };

  return (
    <Card className="space-y-4">
      <h4 className="text-sm font-medium text-text-primary">PII Detection</h4>

      {/* PII Type Toggles */}
      <div className="space-y-2">
        <label className="block text-xs font-medium text-text-secondary">Detected PII Types</label>
        <div className="grid grid-cols-2 gap-2">
          {PII_TYPES.map((pii) => (
            <Toggle
              key={pii.id}
              enabled={cfg.types[pii.id] ?? false}
              onChange={() => togglePiiType(pii.id)}
              label={pii.label}
            />
          ))}
        </div>
      </div>

      {/* Detection Action */}
      <div className="space-y-2">
        <label className="block text-xs font-medium text-text-secondary">Detection Action</label>
        <div className="grid grid-cols-2 gap-2">
          {PII_ACTIONS.map((a) => (
            <SelectionCard
              key={a.id}
              selected={cfg.action === a.id}
              onClick={() => setAction(a.id as PiiAction)}
              className="py-3 px-3"
            >
              <p className="text-sm font-medium text-text-primary">{a.label}</p>
              <p className="text-xs text-text-muted mt-0.5">{a.description}</p>
            </SelectionCard>
          ))}
        </div>
      </div>

      {/* Custom Regex Patterns */}
      <div className="space-y-2">
        <label className="block text-xs font-medium text-text-secondary">Custom Regex Patterns</label>
        <div className="flex gap-2">
          <Input
            placeholder="\b\d{3}-\d{2}-\d{4}\b"
            value={newPattern}
            onChange={(e) => setNewPattern(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addPattern()}
            className="flex-1 font-mono"
          />
          <Button size="sm" onClick={addPattern} icon={<Plus size={14} />}>
            Add
          </Button>
        </div>
        {cfg.customPatterns.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {cfg.customPatterns.map((p) => (
              <Badge key={p} variant="accent">
                <span className="font-mono text-xs">{p}</span>
                <button type="button" onClick={() => removePattern(p)} className="ml-1 cursor-pointer">
                  <X size={10} />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
