import { ArrowRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWizard } from '../../state/context';
import { FAILOVER_STRATEGIES, ROUTING_MODES } from '../../data/gateway';
import { Card, SelectionCard } from '../ui/Card';
import { Input } from '../ui/Input';
import { Badge } from '../ui/Badge';
import { stagger, fadeInUp, fadeIn } from '../../lib/motion';
import { ManualRoutingEditor } from './gateway/ManualRoutingEditor';

export function StepGateway() {
  const { state, setGateway } = useWizard();
  const gw = state.gateway;
  const portValid = gw.port >= 1024 && gw.port <= 65535;

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-6">
      {/* Port & Rate Limit */}
      <motion.div variants={fadeInUp} className="grid grid-cols-2 gap-4">
        <Input
          label="Port"
          type="number"
          value={String(gw.port)}
          onChange={(e) => setGateway({ port: parseInt(e.target.value) || 0 })}
          error={!portValid ? 'Port must be 1024–65535' : undefined}
          hint="Gateway listen port"
        />
        <Input
          label="Rate Limit (RPM)"
          type="number"
          value={String(gw.rateLimit)}
          onChange={(e) => setGateway({ rateLimit: Math.max(1, Math.min(10000, parseInt(e.target.value) || 1)) })}
          hint="Requests per minute"
        />
      </motion.div>

      {/* Failover Strategy */}
      <motion.div variants={fadeInUp}>
        <h3 className="text-sm font-medium text-text-primary mb-3">Failover Strategy</h3>
        <div className="grid grid-cols-3 gap-3">
          {FAILOVER_STRATEGIES.map((s) => (
            <SelectionCard
              key={s.id}
              selected={gw.failover === s.id}
              onClick={() => setGateway({ failover: s.id })}
              className="text-center"
            >
              <h4 className="text-sm font-medium text-text-primary">{s.label}</h4>
              <p className="text-xs text-text-muted mt-1">{s.description}</p>
            </SelectionCard>
          ))}
        </div>
      </motion.div>

      {/* Routing Mode */}
      <motion.div variants={fadeInUp}>
        <h3 className="text-sm font-medium text-text-primary mb-3">Routing Mode</h3>
        <div className="grid grid-cols-2 gap-3">
          {ROUTING_MODES.map((r) => (
            <SelectionCard
              key={r.id}
              selected={gw.routing === r.id}
              onClick={() => setGateway({ routing: r.id })}
            >
              <h4 className="text-sm font-medium text-text-primary">{r.label}</h4>
              <p className="text-xs text-text-muted mt-1">{r.description}</p>
            </SelectionCard>
          ))}
        </div>
      </motion.div>

      {/* Manual Routing Editor */}
      <AnimatePresence>
        {gw.routing === 'manual' && (
          <motion.div variants={fadeIn} initial="initial" animate="animate" exit="exit">
            <ManualRoutingEditor />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Request Flow Visualization */}
      <motion.div variants={fadeInUp}>
        <Card className="flex items-center justify-center gap-3 py-4 flex-wrap">
          <Badge variant="secondary">Client</Badge>
          <ArrowRight size={14} className="text-text-muted" />
          <Badge variant="accent">XClaw Router :{gw.port}</Badge>
          <ArrowRight size={14} className="text-text-muted" />
          {gw.routing === 'manual' && gw.routes.length > 0 ? (
            <>
              <div className="flex flex-col gap-1">
                {gw.routes.slice(0, 3).map((r, i) => (
                  <Badge key={i} variant="muted" className="text-xs">
                    {r.pattern} → {r.target}
                  </Badge>
                ))}
                {gw.routes.length > 3 && (
                  <Badge variant="muted" className="text-xs">
                    +{gw.routes.length - 3} more
                  </Badge>
                )}
              </div>
              <ArrowRight size={14} className="text-text-muted" />
            </>
          ) : null}
          <Badge variant="secondary">Agent Platform</Badge>
        </Card>
      </motion.div>
    </motion.div>
  );
}
