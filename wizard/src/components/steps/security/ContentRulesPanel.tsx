import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { useWizard } from '../../../state/context';
import { FORBIDDEN_CONTENT_CATEGORIES } from '../../../data/security';
import { Card } from '../../ui/Card';
import { Input } from '../../ui/Input';
import { Button } from '../../ui/Button';
import { Badge } from '../../ui/Badge';
import { Checkbox } from '../../ui/Checkbox';
import { Toggle } from '../../ui/Toggle';

export function ContentRulesPanel() {
  const { state, setSecurityConfig } = useWizard();
  const cfg = state.securityConfig.contentRules;
  const [newBlocked, setNewBlocked] = useState('');
  const [newAllowed, setNewAllowed] = useState('');

  const addBlockedKeyword = () => {
    const trimmed = newBlocked.trim();
    if (trimmed && !cfg.blockedKeywords.includes(trimmed)) {
      setSecurityConfig({
        contentRules: { ...cfg, blockedKeywords: [...cfg.blockedKeywords, trimmed] },
      });
      setNewBlocked('');
    }
  };

  const removeBlockedKeyword = (kw: string) => {
    setSecurityConfig({
      contentRules: { ...cfg, blockedKeywords: cfg.blockedKeywords.filter((k) => k !== kw) },
    });
  };

  const addAllowedKeyword = () => {
    const trimmed = newAllowed.trim();
    if (trimmed && !cfg.allowedKeywords.includes(trimmed)) {
      setSecurityConfig({
        contentRules: { ...cfg, allowedKeywords: [...cfg.allowedKeywords, trimmed] },
      });
      setNewAllowed('');
    }
  };

  const removeAllowedKeyword = (kw: string) => {
    setSecurityConfig({
      contentRules: { ...cfg, allowedKeywords: cfg.allowedKeywords.filter((k) => k !== kw) },
    });
  };

  const toggleCategory = (catId: string) => {
    const next = cfg.forbiddenCategories.includes(catId)
      ? cfg.forbiddenCategories.filter((c) => c !== catId)
      : [...cfg.forbiddenCategories, catId];
    setSecurityConfig({
      contentRules: { ...cfg, forbiddenCategories: next },
    });
  };

  return (
    <Card className="space-y-4">
      <h4 className="text-sm font-medium text-text-primary">Content Rules</h4>

      {/* Blocked Keywords */}
      <div className="space-y-2">
        <label className="block text-xs font-medium text-text-secondary">Blocked Keywords</label>
        <div className="flex gap-2">
          <Input
            placeholder="Add blocked keyword..."
            value={newBlocked}
            onChange={(e) => setNewBlocked(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addBlockedKeyword()}
            className="flex-1"
          />
          <Button size="sm" onClick={addBlockedKeyword} icon={<Plus size={14} />}>
            Add
          </Button>
        </div>
        {cfg.blockedKeywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {cfg.blockedKeywords.map((kw) => (
              <Badge key={kw} variant="error">
                {kw}
                <button type="button" onClick={() => removeBlockedKeyword(kw)} className="ml-1 cursor-pointer">
                  <X size={10} />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Allowed Keywords */}
      <div className="space-y-2">
        <label className="block text-xs font-medium text-text-secondary">Allowed Keywords</label>
        <div className="flex gap-2">
          <Input
            placeholder="Add allowed keyword..."
            value={newAllowed}
            onChange={(e) => setNewAllowed(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addAllowedKeyword()}
            className="flex-1"
          />
          <Button size="sm" onClick={addAllowedKeyword} icon={<Plus size={14} />}>
            Add
          </Button>
        </div>
        {cfg.allowedKeywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {cfg.allowedKeywords.map((kw) => (
              <Badge key={kw} variant="success">
                {kw}
                <button type="button" onClick={() => removeAllowedKeyword(kw)} className="ml-1 cursor-pointer">
                  <X size={10} />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Forbidden Content Categories */}
      <div className="space-y-2">
        <label className="block text-xs font-medium text-text-secondary">
          Forbidden Content Categories ({cfg.forbiddenCategories.length}/{FORBIDDEN_CONTENT_CATEGORIES.length})
        </label>
        <div className="grid grid-cols-2 gap-2">
          {FORBIDDEN_CONTENT_CATEGORIES.map((cat) => (
            <Checkbox
              key={cat.id}
              checked={cfg.forbiddenCategories.includes(cat.id)}
              onChange={() => toggleCategory(cat.id)}
              label={cat.label}
            />
          ))}
        </div>
      </div>

      {/* Response Injection Protection */}
      <Toggle
        enabled={cfg.responseInjectionProtection}
        onChange={(val) =>
          setSecurityConfig({
            contentRules: { ...cfg, responseInjectionProtection: val },
          })
        }
        label="Response Injection Protection"
        description="Detect and block prompt injection attempts in LLM responses"
      />
    </Card>
  );
}
