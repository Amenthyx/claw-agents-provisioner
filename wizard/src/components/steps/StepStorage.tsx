import { useState, useEffect, useCallback, useRef } from 'react';
import {
  HardDrive, Database, Share2, CheckCircle, XCircle, Loader2, Info,
  Container, Terminal, AlertTriangle, ArrowRight,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWizard } from '../../state/context';
import { SelectionCard } from '../ui/Card';
import { Card } from '../ui/Card';
import { Input } from '../ui/Input';
import { Toggle } from '../ui/Toggle';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { stagger, fadeInUp, fadeIn } from '../../lib/motion';
import { api } from '../../lib/api';
import type { StorageEngine } from '../../state/types';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface PgReadiness {
  driver_installed: boolean;
  server_reachable: boolean;
  connection_ok: boolean;
  connection_message: string;
  db_exists?: boolean;
  docker_available: boolean;
  host?: string;
  port?: number;
  ready: boolean;
}

export function StepStorage() {
  const { state, setStorage, setStorageInstance, setStorageShared } = useWizard();

  // Connection test
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  // PostgreSQL readiness
  const [pgCheck, setPgCheck] = useState<PgReadiness | null>(null);
  const [pgChecking, setPgChecking] = useState(false);
  const [pgSetupMode, setPgSetupMode] = useState<'docker' | 'local' | null>(null);
  const [pgSetting, setPgSetting] = useState(false);
  const [pgSetupResult, setPgSetupResult] = useState<{ success: boolean; message: string } | null>(null);

  const instanceEngine = state.storage.instanceDb.engine;
  const sharedEngine = state.storage.sharedDb.engine;

  // Dynamic default paths based on claw name
  const clawName = state.agentName || 'default';
  const defaultInstancePath = `./data/${clawName}/instance.db`;
  const defaultSharedPath = `./data/${clawName}/shared.db`;
  const instanceSqlitePath = state.storage.instanceDb.sqlite.path || defaultInstancePath;
  const sharedSqlitePath = state.storage.sharedDb.sqlite.path || defaultSharedPath;

  // Whether anything on this page uses PostgreSQL
  const needsPostgres = instanceEngine === 'postgresql'
    || (state.storage.sharedDb.enabled && sharedEngine === 'postgresql');

  // ── PostgreSQL readiness check ────────────────────────────
  // Use a ref to read current config without re-creating the callback on every keystroke
  const pgConfigRef = useRef(state.storage);
  pgConfigRef.current = state.storage;

  const checkPostgres = useCallback(async () => {
    if (!needsPostgres) return;
    setPgChecking(true);
    setPgSetupResult(null);
    try {
      const storage = pgConfigRef.current;
      const cfg = instanceEngine === 'postgresql'
        ? storage.instanceDb.postgresql
        : storage.sharedDb.postgresql;
      const result = await api.checkPostgresReadiness(cfg);
      setPgCheck(result);
    } catch {
      setPgCheck(null);
    }
    setPgChecking(false);
  }, [needsPostgres, instanceEngine]);

  // Auto-check only when PostgreSQL engine is first selected (not on every keystroke)
  useEffect(() => {
    if (needsPostgres) {
      checkPostgres();
    } else {
      setPgCheck(null);
      setPgSetupResult(null);
      setPgSetupMode(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsPostgres]);

  // ── Engine selection ──────────────────────────────────────
  const handleInstanceEngine = (engine: StorageEngine) => {
    setStorageInstance({ engine });
    setStorage({ engine });
    setTestResult(null);
    setPgCheck(null);
  };

  const handleSharedEngine = (engine: StorageEngine) => {
    setStorageShared({ engine });
    setTestResult(null);
    setPgCheck(null);
  };

  // ── Test connection (instance + shared) ──────────────────
  const [sharedTestResult, setSharedTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    setSharedTestResult(null);
    try {
      // Test instance DB
      const instConfig = instanceEngine === 'sqlite'
        ? { engine: 'sqlite' as const, path: instanceSqlitePath }
        : { engine: 'postgresql' as const, ...state.storage.instanceDb.postgresql };
      const instResult = await api.testStorageConnection(instConfig);
      setTestResult(instResult);

      // Test shared DB if enabled
      if (state.storage.sharedDb.enabled) {
        const sharedConfig = sharedEngine === 'sqlite'
          ? { engine: 'sqlite' as const, path: sharedSqlitePath }
          : { engine: 'postgresql' as const, ...state.storage.sharedDb.postgresql };
        const shResult = await api.testStorageConnection(sharedConfig);
        setSharedTestResult(shResult);
      }
    } catch {
      setTestResult({ success: false, message: 'Connection test failed' });
    }
    setTesting(false);
  };

  // ── Create PostgreSQL database ─────────────────────────────
  const [creatingDb, setCreatingDb] = useState(false);
  const [createDbResult, setCreateDbResult] = useState<{ success: boolean; message: string } | null>(null);

  const createDatabase = async () => {
    setCreatingDb(true);
    setCreateDbResult(null);
    try {
      const cfg = instanceEngine === 'postgresql'
        ? state.storage.instanceDb.postgresql
        : state.storage.sharedDb.postgresql;
      const result = await api.createPostgresDatabase(cfg);
      setCreateDbResult(result);
      if (result.success) {
        setTimeout(() => checkPostgres(), 1000);
      }
    } catch {
      setCreateDbResult({ success: false, message: 'Failed to create database' });
    }
    setCreatingDb(false);
  };

  // ── Setup PostgreSQL (Docker or Local) ────────────────────
  const setupPostgres = async (mode: 'docker' | 'local') => {
    setPgSetting(true);
    setPgSetupResult(null);
    setPgSetupMode(mode);
    try {
      const cfg = instanceEngine === 'postgresql'
        ? state.storage.instanceDb.postgresql
        : state.storage.sharedDb.postgresql;
      const result = await api.setupPostgres(mode, cfg);
      setPgSetupResult(result);

      // If Docker setup succeeded, populate the connection fields
      if (result.success && mode === 'docker' && result.host) {
        const pg = {
          host: result.host,
          port: result.port ?? 5432,
          dbname: (cfg as any).dbname || 'xclaw',
          user: (cfg as any).user || 'xclaw',
          password: (cfg as any).password || 'xclaw',
        };
        if (instanceEngine === 'postgresql') {
          setStorageInstance({ postgresql: pg });
        } else {
          setStorageShared({ postgresql: pg });
        }
      }

      // Re-check readiness after setup
      setTimeout(() => checkPostgres(), 1500);
    } catch {
      setPgSetupResult({ success: false, message: 'Setup request failed' });
    }
    setPgSetting(false);
  };

  // ── Environment note ──────────────────────────────────────
  const envNote = () => {
    switch (state.deploymentMethod) {
      case 'docker': return 'Docker: SQLite databases persist via named volumes. PostgreSQL can run as a sidecar service alongside your XClaw containers.';
      case 'vagrant': return 'Vagrant: Databases are stored in synced folders for persistence across VM restarts.';
      case 'ssh': return 'SSH Remote: PostgreSQL is recommended for multi-instance deployments on remote servers.';
      default: return 'Local: Database files are stored in the ./data/ directory.';
    }
  };

  // ── Readiness status items ────────────────────────────────
  const StatusItem = ({ ok, label, detail }: { ok: boolean; label: string; detail?: string }) => (
    <div className="flex items-start gap-2.5 py-1.5">
      {ok ? (
        <CheckCircle size={15} className="text-green-500 mt-0.5 shrink-0" />
      ) : (
        <XCircle size={15} className="text-red-400 mt-0.5 shrink-0" />
      )}
      <div>
        <span className="text-sm text-text-primary">{label}</span>
        {detail && <p className="text-xs text-text-muted mt-0.5">{detail}</p>}
      </div>
    </div>
  );

  // ── PostgreSQL fields (reusable) ──────────────────────────
  const PgFields = ({ prefix, pg, onChange }: {
    prefix: string;
    pg: { host: string; port: number; dbname: string; user: string; password: string };
    onChange: (v: any) => void;
  }) => (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Input label="Host" placeholder="localhost" value={pg.host}
          onChange={(e) => onChange({ postgresql: { ...pg, host: e.target.value } })} />
        <Input label="Port" type="number" placeholder="5432" value={String(pg.port)}
          onChange={(e) => onChange({ postgresql: { ...pg, port: parseInt(e.target.value) || 5432 } })} />
      </div>
      <Input label="Database Name" placeholder={prefix === 'shared' ? 'xclaw_shared' : 'xclaw'} value={pg.dbname}
        onChange={(e) => onChange({ postgresql: { ...pg, dbname: e.target.value } })} />
      <div className="grid grid-cols-2 gap-3">
        <Input label="User" placeholder="xclaw" value={pg.user}
          onChange={(e) => onChange({ postgresql: { ...pg, user: e.target.value } })} />
        <Input label="Password" isPassword placeholder="••••••••" value={pg.password}
          onChange={(e) => onChange({ postgresql: { ...pg, password: e.target.value } })} />
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* ── Engine Selection ─────────────────────────────────── */}
      <div>
        <h3 className="text-sm font-medium text-text-primary mb-3">Instance Database Engine</h3>
        <motion.div variants={stagger} initial="initial" animate="animate" className="grid grid-cols-2 gap-3">
          <motion.div variants={fadeInUp}>
            <SelectionCard selected={instanceEngine === 'sqlite'}
              onClick={() => handleInstanceEngine('sqlite')} className="h-full">
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
            <SelectionCard selected={instanceEngine === 'postgresql'}
              onClick={() => handleInstanceEngine('postgresql')} className="h-full">
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

      {/* ── Instance DB Config ───────────────────────────────── */}
      <AnimatePresence mode="wait">
        {instanceEngine === 'sqlite' ? (
          <motion.div key="sqlite-inst" variants={fadeIn} initial="initial" animate="animate" exit="exit"
            className="rounded-xl border border-border-base bg-surface-1 p-5 space-y-3">
            <h3 className="text-sm font-medium text-text-primary">SQLite Path</h3>
            <Input label="Database file path" placeholder={defaultInstancePath}
              value={instanceSqlitePath}
              onChange={(e) => setStorageInstance({ sqlite: { path: e.target.value } })} />
          </motion.div>
        ) : (
          <motion.div key="pg-inst" variants={fadeIn} initial="initial" animate="animate" exit="exit"
            className="rounded-xl border border-border-base bg-surface-1 p-5 space-y-3">
            <h3 className="text-sm font-medium text-text-primary">PostgreSQL Connection</h3>
            <PgFields prefix="instance" pg={state.storage.instanceDb.postgresql} onChange={setStorageInstance} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── PostgreSQL Readiness Panel ────────────────────────── */}
      <AnimatePresence>
        {needsPostgres && (
          <motion.div key="pg-readiness" variants={fadeIn} initial="initial" animate="animate" exit="exit"
            className="rounded-xl border border-border-base bg-surface-1 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-text-primary">PostgreSQL Readiness</h3>
              <Button variant="ghost" size="sm" onClick={checkPostgres} disabled={pgChecking}
                icon={pgChecking ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}>
                {pgChecking ? 'Checking...' : 'Re-check'}
              </Button>
            </div>

            {pgChecking && !pgCheck && (
              <div className="flex items-center gap-2 text-sm text-text-muted py-2">
                <Loader2 size={14} className="animate-spin" />
                Detecting PostgreSQL environment...
              </div>
            )}

            {pgCheck && (
              <div className="space-y-1">
                <StatusItem ok={pgCheck.driver_installed}
                  label="Python driver (psycopg2)"
                  detail={pgCheck.driver_installed ? 'Installed' : 'Will be installed automatically'} />
                <StatusItem ok={pgCheck.server_reachable}
                  label={`PostgreSQL server (${pgCheck.host ?? 'localhost'}:${pgCheck.port ?? 5432})`}
                  detail={pgCheck.server_reachable ? 'Server is responding' : 'No PostgreSQL server detected'} />
                {pgCheck.server_reachable && (
                  <StatusItem ok={pgCheck.connection_ok}
                    label="Database connection"
                    detail={pgCheck.connection_ok
                      ? pgCheck.connection_message
                      : (!pgCheck.db_exists
                        ? 'Database does not exist — you can create it below'
                        : pgCheck.connection_message || 'Authentication failed')} />
                )}
              </div>
            )}

            {/* If all good, show green banner */}
            {pgCheck?.ready && (
              <div className="flex items-center gap-2 rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-2.5">
                <CheckCircle size={16} className="text-green-500 shrink-0" />
                <p className="text-sm text-green-400">PostgreSQL is ready to use</p>
              </div>
            )}

            {/* If server not reachable, offer install options */}
            {pgCheck && !pgCheck.server_reachable && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-4 py-2.5">
                  <AlertTriangle size={16} className="text-amber-400 shrink-0" />
                  <p className="text-sm text-amber-300">
                    PostgreSQL is not running. Choose how to set it up:
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {/* Docker option */}
                  <Card className={`cursor-pointer transition-all ${pgSetupMode === 'docker' ? 'ring-1 ring-accent' : ''}`}>
                    <button type="button" className="w-full text-left" onClick={() => setPgSetupMode('docker')}>
                      <div className="flex items-center gap-2 mb-2">
                        <Container size={18} className="text-accent" />
                        <span className="text-sm font-medium text-text-primary">Docker Container</span>
                        <Badge variant="accent">Recommended</Badge>
                      </div>
                      <p className="text-xs text-text-secondary">
                        Starts a PostgreSQL 16 container automatically via Docker Compose.
                        Zero configuration needed.
                      </p>
                      {!pgCheck.docker_available && (
                        <p className="text-xs text-amber-400 mt-1.5">Docker not detected — it will be installed and started automatically</p>
                      )}
                    </button>
                  </Card>

                  {/* Local option */}
                  <Card className={`cursor-pointer transition-all ${pgSetupMode === 'local' ? 'ring-1 ring-accent' : ''}`}>
                    <button type="button" className="w-full text-left" onClick={() => setPgSetupMode('local')}>
                      <div className="flex items-center gap-2 mb-2">
                        <Terminal size={18} className="text-text-muted" />
                        <span className="text-sm font-medium text-text-primary">Local Install</span>
                      </div>
                      <p className="text-xs text-text-secondary">
                        Install PostgreSQL on your system manually, then connect.
                        The Python driver will be installed automatically.
                      </p>
                    </button>
                  </Card>
                </div>

                {/* Setup action button */}
                {pgSetupMode && (
                  <motion.div variants={fadeIn} initial="initial" animate="animate">
                    <Button
                      onClick={() => setupPostgres(pgSetupMode)}
                      disabled={pgSetting}
                      icon={pgSetting
                        ? <Loader2 size={14} className="animate-spin" />
                        : <ArrowRight size={14} />}
                    >
                      {pgSetting
                        ? (pgSetupMode === 'docker' ? 'Starting PostgreSQL container...' : 'Installing driver...')
                        : (pgSetupMode === 'docker' ? 'Start PostgreSQL via Docker' : 'Install Python driver')}
                    </Button>
                  </motion.div>
                )}

                {/* Setup result */}
                {pgSetupResult && (
                  <div className={`flex items-start gap-2 rounded-lg px-4 py-2.5 ${
                    pgSetupResult.success
                      ? 'bg-green-500/10 border border-green-500/20'
                      : 'bg-red-500/10 border border-red-500/20'
                  }`}>
                    {pgSetupResult.success
                      ? <CheckCircle size={15} className="text-green-500 mt-0.5 shrink-0" />
                      : <XCircle size={15} className="text-red-400 mt-0.5 shrink-0" />}
                    <p className={`text-sm ${pgSetupResult.success ? 'text-green-400' : 'text-red-400'}`}>
                      {pgSetupResult.message}
                    </p>
                  </div>
                )}

                {/* Local install instructions */}
                {pgSetupMode === 'local' && (
                  <div className="rounded-lg border border-border-base bg-surface-2 p-4 space-y-2">
                    <p className="text-xs font-medium text-text-secondary">Install PostgreSQL locally:</p>
                    <div className="text-xs font-mono text-text-muted space-y-1">
                      <p className="text-text-secondary"># Windows (installer)</p>
                      <p>Download from https://www.postgresql.org/download/windows/</p>
                      <p className="text-text-secondary mt-2"># macOS (Homebrew)</p>
                      <p>brew install postgresql@16 && brew services start postgresql@16</p>
                      <p className="text-text-secondary mt-2"># Ubuntu / Debian</p>
                      <p>sudo apt install postgresql && sudo systemctl start postgresql</p>
                    </div>
                    <p className="text-xs text-text-muted mt-2">
                      After installing, create a database and user, then fill in the connection fields above and click Re-check.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Driver not installed but server is reachable (unlikely, but handle) */}
            {pgCheck && !pgCheck.driver_installed && pgCheck.server_reachable && (
              <div className="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-4 py-2.5">
                <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-amber-300">Python driver (psycopg2) is missing</p>
                  <p className="text-xs text-text-muted mt-1">
                    It will be installed automatically when you proceed, or click Re-check to install now.
                  </p>
                </div>
              </div>
            )}

            {/* Server reachable but database doesn't exist — offer to create */}
            {pgCheck && pgCheck.driver_installed && pgCheck.server_reachable && !pgCheck.connection_ok && !pgCheck.db_exists && (
              <div className="space-y-3">
                <div className="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-4 py-2.5">
                  <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm text-amber-300">Database does not exist</p>
                    <p className="text-xs text-text-muted mt-1">
                      {pgCheck.connection_message}
                    </p>
                  </div>
                </div>
                <Button variant="secondary" size="sm" onClick={createDatabase} disabled={creatingDb}
                  icon={creatingDb ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}>
                  {creatingDb ? 'Creating...' : 'Create Database'}
                </Button>
                {createDbResult && (
                  <div className={`flex items-start gap-2 rounded-lg px-4 py-2.5 ${
                    createDbResult.success
                      ? 'bg-green-500/10 border border-green-500/20'
                      : 'bg-red-500/10 border border-red-500/20'
                  }`}>
                    {createDbResult.success
                      ? <CheckCircle size={15} className="text-green-500 mt-0.5 shrink-0" />
                      : <XCircle size={15} className="text-red-400 mt-0.5 shrink-0" />}
                    <p className={`text-sm ${createDbResult.success ? 'text-green-400' : 'text-red-400'}`}>
                      {createDbResult.message}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Connection failed (driver + server OK, db exists but auth error) */}
            {pgCheck && pgCheck.driver_installed && pgCheck.server_reachable && !pgCheck.connection_ok && pgCheck.db_exists !== false && (
              <div className="flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2.5">
                <XCircle size={16} className="text-red-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-red-400">Connection failed</p>
                  <p className="text-xs text-text-muted mt-1">
                    {pgCheck.connection_message || 'Check your credentials and database name above.'}
                  </p>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Shared DB Toggle ─────────────────────────────────── */}
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

      {/* ── Shared DB Config ─────────────────────────────────── */}
      <AnimatePresence>
        {state.storage.sharedDb.enabled && (
          <motion.div variants={fadeIn} initial="initial" animate="animate" exit="exit" className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-text-primary mb-3">Shared Database Engine</h3>
              <div className="grid grid-cols-2 gap-3">
                <SelectionCard selected={sharedEngine === 'sqlite'}
                  onClick={() => handleSharedEngine('sqlite')} className="h-full">
                  <HardDrive size={16} className={sharedEngine === 'sqlite' ? 'text-accent' : 'text-text-muted'} />
                  <h3 className="text-sm font-medium text-text-primary mt-1.5">SQLite</h3>
                  <p className="text-xs text-text-secondary mt-0.5">Single-node shared storage</p>
                </SelectionCard>
                <SelectionCard selected={sharedEngine === 'postgresql'}
                  onClick={() => handleSharedEngine('postgresql')} className="h-full">
                  <Database size={16} className={sharedEngine === 'postgresql' ? 'text-accent' : 'text-text-muted'} />
                  <h3 className="text-sm font-medium text-text-primary mt-1.5">PostgreSQL</h3>
                  <p className="text-xs text-text-secondary mt-0.5">Multi-instance network storage</p>
                </SelectionCard>
              </div>
            </div>

            {sharedEngine === 'sqlite' ? (
              <div className="rounded-xl border border-border-base bg-surface-1 p-5">
                <Input label="Shared database path" placeholder={defaultSharedPath}
                  value={sharedSqlitePath}
                  onChange={(e) => setStorageShared({ sqlite: { path: e.target.value } })} />
              </div>
            ) : (
              <div className="rounded-xl border border-border-base bg-surface-1 p-5 space-y-3">
                <h3 className="text-sm font-medium text-text-primary">Shared PostgreSQL Connection</h3>
                <PgFields prefix="shared" pg={state.storage.sharedDb.postgresql} onChange={setStorageShared} />
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Test Connection ───────────────────────────────────── */}
      <div className="space-y-2">
        <Button variant="secondary" size="sm" onClick={testConnection} disabled={testing}
          icon={testing ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}>
          {testing ? 'Testing...' : 'Test Connection'}
        </Button>
        {testResult && (
          <div className="flex items-center gap-1.5">
            {testResult.success
              ? <CheckCircle size={14} className="text-green-500" />
              : <XCircle size={14} className="text-red-500" />}
            <span className={`text-xs ${testResult.success ? 'text-green-500' : 'text-red-500'}`}>
              Instance DB: {testResult.message}
            </span>
          </div>
        )}
        {sharedTestResult && (
          <div className="flex items-center gap-1.5">
            {sharedTestResult.success
              ? <CheckCircle size={14} className="text-green-500" />
              : <XCircle size={14} className="text-red-500" />}
            <span className={`text-xs ${sharedTestResult.success ? 'text-green-500' : 'text-red-500'}`}>
              Shared DB: {sharedTestResult.message}
            </span>
          </div>
        )}
      </div>

      {/* ── Environment Note ─────────────────────────────────── */}
      <div className="flex items-start gap-2.5 rounded-lg border border-border-base bg-surface-2 px-4 py-3">
        <Info size={14} className="text-text-muted mt-0.5 shrink-0" />
        <p className="text-xs text-text-secondary">{envNote()}</p>
      </div>
    </div>
  );
}
/* eslint-enable @typescript-eslint/no-explicit-any */
