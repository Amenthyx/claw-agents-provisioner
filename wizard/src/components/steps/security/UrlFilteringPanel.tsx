import { useState } from 'react';
import { Plus, X, Shield, Globe } from 'lucide-react';
import { useWizard } from '../../../state/context';
import { DEFAULT_BLOCKED_DOMAINS } from '../../../data/security';
import { Card } from '../../ui/Card';
import { Button } from '../../ui/Button';
import { Badge } from '../../ui/Badge';
import { Toggle } from '../../ui/Toggle';

export function UrlFilteringPanel() {
  const { state, setSecurityConfig } = useWizard();
  const cfg = state.securityConfig.urlFiltering;
  const [newPattern, setNewPattern] = useState('');

  const isAllowlist = cfg.mode === 'allowlist';

  const addPattern = () => {
    const trimmed = newPattern.trim();
    if (trimmed && !cfg.patterns.includes(trimmed)) {
      setSecurityConfig({
        urlFiltering: { ...cfg, patterns: [...cfg.patterns, trimmed] },
      });
      setNewPattern('');
    }
  };

  const removePattern = (pattern: string) => {
    setSecurityConfig({
      urlFiltering: { ...cfg, patterns: cfg.patterns.filter((p) => p !== pattern) },
    });
  };

  const seedDefaults = () => {
    const merged = [...new Set([...cfg.patterns, ...DEFAULT_BLOCKED_DOMAINS])];
    setSecurityConfig({
      urlFiltering: { ...cfg, patterns: merged },
    });
  };

  return (
    <Card className="space-y-5 border-warning/20">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-warning" />
          <h4 className="text-sm font-semibold text-text-primary">URL Filtering</h4>
        </div>
        <Toggle
          enabled={isAllowlist}
          onChange={(val) =>
            setSecurityConfig({
              urlFiltering: { ...cfg, mode: val ? 'allowlist' : 'blocklist' },
            })
          }
          label={isAllowlist ? 'Allowlist-Only' : 'Blocklist'}
        />
      </div>

      <p className="text-xs text-text-muted">
        {isAllowlist
          ? 'Only URLs matching these patterns will be accessible. All others are blocked.'
          : 'URLs matching these patterns will be blocked. All others are allowed.'}
      </p>

      {/* URL input — prominent, large, with icon */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Globe size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="Enter URL pattern: *.example.com or www.site.com/api/*"
            value={newPattern}
            onChange={(e) => setNewPattern(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addPattern()}
            className="w-full rounded-lg border-2 border-accent/40 bg-surface-0 py-3 pl-10 pr-4 text-sm text-text-primary placeholder:text-text-muted/60 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 transition-all font-mono"
          />
        </div>
        <Button size="lg" onClick={addPattern} icon={<Plus size={16} />}>
          Add
        </Button>
      </div>

      {/* Quick examples */}
      <div className="flex flex-wrap gap-2 text-xs">
        <span className="text-text-muted">Quick add:</span>
        {['*.malware-domain.com', '*.onion', 'pastebin.com', '*.tor2web.org'].map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => {
              if (!cfg.patterns.includes(example)) {
                setSecurityConfig({
                  urlFiltering: { ...cfg, patterns: [...cfg.patterns, example] },
                });
              }
            }}
            className="rounded-md border border-border-base bg-surface-1 px-2 py-0.5 font-mono text-text-secondary hover:border-accent hover:text-accent cursor-pointer transition-colors"
          >
            {example}
          </button>
        ))}
      </div>

      {/* Pattern chips */}
      {cfg.patterns.length > 0 ? (
        <div>
          <p className="text-xs text-text-muted mb-2">
            {cfg.patterns.length} pattern{cfg.patterns.length !== 1 ? 's' : ''} configured:
          </p>
          <div className="flex flex-wrap gap-1.5">
            {cfg.patterns.map((p) => (
              <Badge key={p} variant="accent">
                <span className="font-mono text-xs">{p}</span>
                <button
                  type="button"
                  onClick={() => removePattern(p)}
                  className="ml-1.5 hover:text-error cursor-pointer"
                >
                  <X size={10} />
                </button>
              </Badge>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-xs text-text-muted italic">No patterns added yet</p>
      )}

      {/* Seed defaults */}
      {cfg.mode === 'blocklist' && cfg.patterns.length === 0 && (
        <Button variant="ghost" size="sm" onClick={seedDefaults}>
          Load default blocked domains (50+ domains)
        </Button>
      )}

      {/* Wildcard hint */}
      <div className="rounded-lg border border-border-base bg-surface-0 p-3 space-y-1">
        <p className="text-xs font-medium text-text-secondary">Pattern syntax:</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-text-muted">
          <code className="font-mono bg-surface-2 px-1.5 py-0.5 rounded">*.google.com</code>
          <span>Block all subdomains</span>
          <code className="font-mono bg-surface-2 px-1.5 py-0.5 rounded">www.mysite.com/api/*</code>
          <span>Block specific paths</span>
          <code className="font-mono bg-surface-2 px-1.5 py-0.5 rounded">*.onion</code>
          <span>Block TLD</span>
          <code className="font-mono bg-surface-2 px-1.5 py-0.5 rounded">192.168.*</code>
          <span>Block IP range</span>
        </div>
      </div>
    </Card>
  );
}
