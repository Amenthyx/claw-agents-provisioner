import { useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWizard } from '../../state/context';
import { SECURITY_OPTIONS, FORBIDDEN_CONTENT_CATEGORIES, PII_TYPES } from '../../data/security';
import { Toggle } from '../ui/Toggle';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { fadeIn, stagger, fadeInUp } from '../../lib/motion';
import { UrlFilteringPanel } from './security/UrlFilteringPanel';
import { ContentRulesPanel } from './security/ContentRulesPanel';
import { PiiDetectionPanel } from './security/PiiDetectionPanel';
import { NetworkRulesPanel } from './security/NetworkRulesPanel';
import { CompliancePanel } from './security/CompliancePanel';

const DETAIL_PANELS: Record<string, React.FC> = {
  'url-filtering': UrlFilteringPanel,
  'content-rules': ContentRulesPanel,
  'pii-detection': PiiDetectionPanel,
  'network-rules': NetworkRulesPanel,
};

export function StepSecurity() {
  const { state, setSecurityEnabled, toggleSecurityFeature, setSecurityConfig } = useWizard();
  const [expandedPanel, setExpandedPanel] = useState<string | null>(null);
  const prevFeaturesRef = useRef<string[]>(state.securityFeatures);

  const handleToggleFeature = (featureId: string) => {
    const isBeingEnabled = !state.securityFeatures.includes(featureId);
    toggleSecurityFeature(featureId);

    if (isBeingEnabled) {
      if (featureId === 'content-rules') {
        setSecurityConfig({
          contentRules: {
            ...state.securityConfig.contentRules,
            forbiddenCategories: FORBIDDEN_CONTENT_CATEGORIES.map((c) => c.id),
            responseInjectionProtection: true,
          },
        });
      } else if (featureId === 'pii-detection') {
        const allTypes: Record<string, boolean> = {};
        PII_TYPES.forEach((t) => { allTypes[t.id] = true; });
        setSecurityConfig({
          piiDetection: {
            ...state.securityConfig.piiDetection,
            types: allTypes,
          },
        });
      }
    }
  };

  // Auto-expand detail panel when a feature is toggled ON
  useEffect(() => {
    const prev = prevFeaturesRef.current;
    const curr = state.securityFeatures;
    // Find newly added feature
    const added = curr.find((f) => !prev.includes(f));
    if (added && added in DETAIL_PANELS) {
      setExpandedPanel(added);
    }
    prevFeaturesRef.current = curr;
  }, [state.securityFeatures]);

  const filtering = SECURITY_OPTIONS.filter((o) => o.category === 'filtering');
  const active = SECURITY_OPTIONS.filter((o) => state.securityFeatures.includes(o.id));

  return (
    <div className="space-y-6">
      {/* Master Toggle */}
      <Card>
        <Toggle
          enabled={state.securityEnabled}
          onChange={setSecurityEnabled}
          label="Enable Security Layer"
          description="Activate content filtering, PII detection, and compliance controls"
        />
      </Card>

      <AnimatePresence>
        {state.securityEnabled && (
          <motion.div variants={fadeIn} initial="initial" animate="animate" exit="exit" className="space-y-6">
            {/* Filtering Features with Detail Panels */}
            <div>
              <h3 className="text-sm font-medium text-text-primary mb-3">Filtering</h3>
              <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-2">
                {filtering.map((opt) => {
                  const isEnabled = state.securityFeatures.includes(opt.id);
                  const hasPanel = opt.id in DETAIL_PANELS;
                  const isExpanded = expandedPanel === opt.id;
                  const DetailPanel = hasPanel ? DETAIL_PANELS[opt.id] : null;

                  return (
                    <motion.div key={opt.id} variants={fadeInUp} className="space-y-0">
                      <Card className="py-3 px-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3 flex-1">
                            <Toggle
                              enabled={isEnabled}
                              onChange={() => handleToggleFeature(opt.id)}
                            />
                            <div>
                              <p className="text-sm font-medium text-text-primary">{opt.name}</p>
                              <p className="text-xs text-text-muted">{opt.description}</p>
                            </div>
                          </div>
                          {isEnabled && hasPanel && (
                            <button
                              type="button"
                              onClick={() => setExpandedPanel(isExpanded ? null : opt.id)}
                              className="text-text-muted hover:text-text-primary cursor-pointer p-1"
                            >
                              {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                            </button>
                          )}
                        </div>
                      </Card>
                      <AnimatePresence>
                        {isEnabled && isExpanded && DetailPanel && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="pt-2">
                              <DetailPanel />
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  );
                })}
              </motion.div>
            </div>

            {/* Compliance */}
            <CompliancePanel />

            {/* Active Summary */}
            {active.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {active.map((a) => (
                  <Badge key={a.id} variant="accent">{a.name}</Badge>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
