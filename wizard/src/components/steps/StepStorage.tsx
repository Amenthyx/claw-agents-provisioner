import { useState } from 'react';
import { HardDrive, Database, Share2, CheckCircle, XCircle, Loader2, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWizard } from '../../state/context';
import { SelectionCard } from '../ui/Card';
import { Input } from '../ui/Input';
import { Toggle } from '../ui/Toggle';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { stagger, fadeInUp, fadeIn } from '../../lib/motion';
import { api } from '../../lib/api';
import type { StorageEngine } from '../../state/types';

export function StepStorage() {
  const { state, setStorage, setStorageInstance, setStorageShared } = useWizard();
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const instanceEngine = state.storage.instanceDb.engine;
  const sharedEngine = state.storage.sharedDb.engine;

  const handleInstanceEngine = (engine: StorageEngine) => {
    setStorageInstance({ engine });
    setStorage({ engine });
    setTestResult(null);
  };

  const handleSharedEngine = (engine: StorageEngine) => {
    setStorageShared({ engine });
    setTestResult(null);
  };

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const config = instanceEngine === 'sqlite'
        ? { engine: 'sqlite', path: state.storage.instanceDb.sqlite.path }
        : { engine: 'postgresql', ...state.storage.instanceDb.postgresql };
      const result = await api.testStorageConnection(config);
      setTestResult(result);
    } catch {
      setTestResult({ success: false, message: 'Connection test failed' });
    }
    setTesting(false);
  };

  const envNote = () => {
    switch (state.deploymentMethod) {
      case 'docker': return 'Docker: SQLite databases are persisted via named volumes. PostgreSQL can run as a sidecar service.';
      case 'vagrant': return 'Vagrant: Databases are stored in synced folders for persistence across VM restarts.';
      case 'ssh': return 'SSH Remote: PostgreSQL is recommended for multi-instance deployments on remote servers.';
      default: return 'Local: Database files are stored in the ./data/ directory.';
    }
  };

  return (
    <div className="space-y-6">
      {/* Engine Selection */}
      <div>
        <h3 className="text-sm font-medium text-text-primary mb-3">Instance Database Engine</h3>
        <motion.div variants={stagger} initial="initial" animate="animate" className="grid grid-cols-2 gap-3">
          <motion.div variants={fadeInUp}>
            <SelectionCard
              selected={instanceEngine === 'sqlite'}
              onClick={() => handleInstanceEngine('sqlite')}
              className="h-full"
            >
              <HardDrive size={20} className={instanceEngine === 'sqlite' ? 'text-accent' : 'text-text-muted'} />
              <h3 className="text-sm font-medium text-text-primary mt-2">SQLite</h3>
              <p className="text-xs text-text-secondary mt-1">Zero config, embedded database</p>
              <div className="flex flex-wrap gap-1 mt-2">
                <Badge variant="default">No setup</Badge>
                <Badge variant="default">File-based</Badge>
                <Badge variant="default">Fast</Badge>
              </div>
            </SelectionCard>
          </motion.div>
          <motion.div variants={fadeInUp}>
            <SelectionCard
              selected={instanceEngine === 'postgresql'}
              onClick={() => handleInstanceEngine('postgresql')}
              className="h-full"
            >
              <Database size={20} className={instanceEngine === 'postgresql' ? 'text-accent' : 'text-text-muted'} />
              <h3 className="text-sm font-medium text-text-primary mt-2">PostgreSQL</h3>
              <p className="text-xs text-text-secondary mt-1">Multi-user, network accessible</p>
              <div className="flex flex-wrap gap-1 mt-2">
                <Badge variant="default">Scalable</Badge>
                <Badge variant="default">Concurrent</Badge>
                <Badge variant="default">ACID</Badge>
              </div>
            </SelectionCard>
          </motion.div>
        </motion.div>
      </div>

      {/* Instance DB Config */}
      <AnimatePresence mode="wait">
        {instanceEngine === 'sqlite' ? (
          <motion.div key="sqlite-inst" variants={fadeIn} initial="initial" animate="animate" exit="exit"
            className="rounded-xl border border-border-base bg-surface-1 p-5 space-y-3"
          >
            <h3 className="text-sm font-medium text-text-primary">SQLite Path</h3>
            <Input
              label="Database file path"
              placeholder="./data/instance.db"
              value={state.storage.instanceDb.sqlite.path}
              onChange={(e) => setStorageInstance({ sqlite: { path: e.target.value } })}
            />
          </motion.div>
        ) : (
          <motion.div key="pg-inst" variants={fadeIn} initial="initial" animate="animate" exit="exit"
            className="rounded-xl border border-border-base bg-surface-1 p-5 space-y-3"
          >
            <h3 className="text-sm font-medium text-text-primary">PostgreSQL Connection</h3>
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Host"
                placeholder="localhost"
                value={state.storage.instanceDb.postgresql.host}
                onChange={(e) => setStorageInstance({ postgresql: { ...state.storage.instanceDb.postgresql, host: e.target.value } })}
              />
              <Input
                label="Port"
                type="number"
                placeholder="5432"
                value={String(state.storage.instanceDb.postgresql.port)}
                onChange={(e) => setStorageInstance({ postgresql: { ...state.storage.instanceDb.postgresql, port: parseInt(e.target.value) || 5432 } })}
              />
            </div>
            <Input
              label="Database Name"
              placeholder="xclaw"
              value={state.storage.instanceDb.postgresql.dbname}
              onChange={(e) => setStorageInstance({ postgresql: { ...state.storage.instanceDb.postgresql, dbname: e.target.value } })}
            />
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="User"
                placeholder="xclaw"
                value={state.storage.instanceDb.postgresql.user}
                onChange={(e) => setStorageInstance({ postgresql: { ...state.storage.instanceDb.postgresql, user: e.target.value } })}
              />
              <Input
                label="Password"
                isPassword
                placeholder="••••••••"
                value={state.storage.instanceDb.postgresql.password}
                onChange={(e) => setStorageInstance({ postgresql: { ...state.storage.instanceDb.postgresql, password: e.target.value } })}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Shared DB Toggle */}
      <div className="rounded-xl border border-border-base bg-surface-1 p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Share2 size={18} className="text-text-muted" />
            <div>
              <h3 className="text-sm font-medium text-text-primary">Enable Shared Database</h3>
              <p className="text-xs text-text-secondary mt-0.5">
                Cross-claw data: costs, memory sharing, security events, RBAC
              </p>
            </div>
          </div>
          <Toggle
            enabled={state.storage.sharedDb.enabled}
            onChange={(enabled) => setStorageShared({ enabled })}
          />
        </div>
      </div>

      {/* Shared DB Config */}
      <AnimatePresence>
        {state.storage.sharedDb.enabled && (
          <motion.div variants={fadeIn} initial="initial" animate="animate" exit="exit" className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-text-primary mb-3">Shared Database Engine</h3>
              <div className="grid grid-cols-2 gap-3">
                <SelectionCard
                  selected={sharedEngine === 'sqlite'}
                  onClick={() => handleSharedEngine('sqlite')}
                  className="h-full"
                >
                  <HardDrive size={16} className={sharedEngine === 'sqlite' ? 'text-accent' : 'text-text-muted'} />
                  <h3 className="text-sm font-medium text-text-primary mt-1.5">SQLite</h3>
                  <p className="text-xs text-text-secondary mt-0.5">Single-node shared storage</p>
                </SelectionCard>
                <SelectionCard
                  selected={sharedEngine === 'postgresql'}
                  onClick={() => handleSharedEngine('postgresql')}
                  className="h-full"
                >
                  <Database size={16} className={sharedEngine === 'postgresql' ? 'text-accent' : 'text-text-muted'} />
                  <h3 className="text-sm font-medium text-text-primary mt-1.5">PostgreSQL</h3>
                  <p className="text-xs text-text-secondary mt-0.5">Multi-instance network storage</p>
                </SelectionCard>
              </div>
            </div>

            {sharedEngine === 'sqlite' ? (
              <div className="rounded-xl border border-border-base bg-surface-1 p-5">
                <Input
                  label="Shared database path"
                  placeholder="./data/shared/shared.db"
                  value={state.storage.sharedDb.sqlite.path}
                  onChange={(e) => setStorageShared({ sqlite: { path: e.target.value } })}
                />
              </div>
            ) : (
              <div className="rounded-xl border border-border-base bg-surface-1 p-5 space-y-3">
                <h3 className="text-sm font-medium text-text-primary">Shared PostgreSQL Connection</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="Host"
                    placeholder="localhost"
                    value={state.storage.sharedDb.postgresql.host}
                    onChange={(e) => setStorageShared({ postgresql: { ...state.storage.sharedDb.postgresql, host: e.target.value } })}
                  />
                  <Input
                    label="Port"
                    type="number"
                    placeholder="5432"
                    value={String(state.storage.sharedDb.postgresql.port)}
                    onChange={(e) => setStorageShared({ postgresql: { ...state.storage.sharedDb.postgresql, port: parseInt(e.target.value) || 5432 } })}
                  />
                </div>
                <Input
                  label="Database Name"
                  placeholder="xclaw_shared"
                  value={state.storage.sharedDb.postgresql.dbname}
                  onChange={(e) => setStorageShared({ postgresql: { ...state.storage.sharedDb.postgresql, dbname: e.target.value } })}
                />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="User"
                    placeholder="xclaw"
                    value={state.storage.sharedDb.postgresql.user}
                    onChange={(e) => setStorageShared({ postgresql: { ...state.storage.sharedDb.postgresql, user: e.target.value } })}
                  />
                  <Input
                    label="Password"
                    isPassword
                    placeholder="••••••••"
                    value={state.storage.sharedDb.postgresql.password}
                    onChange={(e) => setStorageShared({ postgresql: { ...state.storage.sharedDb.postgresql, password: e.target.value } })}
                  />
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Test Connection */}
      <div className="flex items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={testConnection}
          disabled={testing}
          icon={testing ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}
        >
          {testing ? 'Testing...' : 'Test Connection'}
        </Button>
        {testResult && (
          <div className="flex items-center gap-1.5">
            {testResult.success ? (
              <CheckCircle size={14} className="text-green-500" />
            ) : (
              <XCircle size={14} className="text-red-500" />
            )}
            <span className={`text-xs ${testResult.success ? 'text-green-500' : 'text-red-500'}`}>
              {testResult.message}
            </span>
          </div>
        )}
      </div>

      {/* Environment Note */}
      <div className="flex items-start gap-2.5 rounded-lg border border-border-base bg-surface-2 px-4 py-3">
        <Info size={14} className="text-text-muted mt-0.5 shrink-0" />
        <p className="text-xs text-text-secondary">{envNote()}</p>
      </div>
    </div>
  );
}
