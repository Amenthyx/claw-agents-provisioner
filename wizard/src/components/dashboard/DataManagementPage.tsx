import { useState, useEffect, useCallback } from 'react';
import {
  Database, HardDrive, Table, Shield, Activity, Download,
  RefreshCw, Search, ChevronDown, ChevronRight, Loader2,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { api } from '../../lib/api';
import { stagger, fadeInUp } from '../../lib/motion';

/* eslint-disable @typescript-eslint/no-explicit-any */

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function DataManagementPage() {
  const [overview, setOverview] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [rbac, setRbac] = useState<any>(null);
  const [selectedDb, setSelectedDb] = useState('instance');
  const [, setTables] = useState<any>(null);
  const [selectedTable, setSelectedTable] = useState('');
  const [tableData, setTableData] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedDb, setExpandedDb] = useState<string | null>(null);

  const loadOverview = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, h, r] = await Promise.all([
        api.dashboard.getDataOverview(),
        api.dashboard.getDataHealth(),
        api.dashboard.getRbac(),
      ]);
      setOverview(ov);
      setHealth(h);
      setRbac(r);
    } catch {
      // API not available yet
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadOverview(); }, [loadOverview]);

  const loadTables = useCallback(async (db: string) => {
    try {
      const result = await api.dashboard.getDataTables(db);
      setTables(result);
      setSelectedTable('');
      setTableData(null);
    } catch { /* */ }
  }, []);

  useEffect(() => { loadTables(selectedDb); }, [selectedDb, loadTables]);

  const queryTable = useCallback(async () => {
    if (!selectedTable) return;
    try {
      const result = await api.dashboard.queryData({
        db: selectedDb,
        table: selectedTable,
        limit: 50,
        search: searchQuery,
      });
      setTableData(result);
    } catch { /* */ }
  }, [selectedDb, selectedTable, searchQuery]);

  useEffect(() => { queryTable(); }, [queryTable]);

  const handleExport = async (db: string) => {
    try {
      const blob = await api.dashboard.exportDatabase(db);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${db}_export.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* */ }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-text-muted" />
      </div>
    );
  }

  const databases = overview?.databases ?? [];
  const totalSize = overview?.total_size_bytes ?? 0;
  const totalTables = overview?.total_tables ?? 0;
  const allHealthy = databases.every((d: any) => d.health?.status === 'healthy');

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Data Management</h1>
          <p className="text-sm text-text-secondary mt-1">
            Browse databases, manage RBAC, and monitor storage health
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={loadOverview} icon={<RefreshCw size={14} />}>
          Refresh
        </Button>
      </div>

      {/* Stats Row */}
      <motion.div variants={stagger} initial="initial" animate="animate" className="grid grid-cols-4 gap-3">
        {[
          { label: 'Databases', value: databases.length, icon: Database },
          { label: 'Tables', value: totalTables, icon: Table },
          { label: 'Total Size', value: formatBytes(totalSize), icon: HardDrive },
          { label: 'Status', value: allHealthy ? 'Healthy' : 'Degraded', icon: Activity },
        ].map((stat) => (
          <motion.div key={stat.label} variants={fadeInUp}>
            <Card className="text-center">
              <stat.icon size={18} className="mx-auto text-text-muted mb-2" />
              <p className="text-lg font-semibold text-text-primary">{stat.value}</p>
              <p className="text-xs text-text-secondary">{stat.label}</p>
            </Card>
          </motion.div>
        ))}
      </motion.div>

      {/* Database List */}
      <div className="space-y-2">
        <h2 className="text-sm font-medium text-text-primary">Databases</h2>
        {databases.map((db: any) => (
          <Card key={db.name} className="overflow-hidden">
            <button
              type="button"
              onClick={() => {
                setExpandedDb(expandedDb === db.name ? null : db.name);
                setSelectedDb(db.name);
              }}
              className="flex items-center justify-between w-full text-left cursor-pointer"
            >
              <div className="flex items-center gap-3">
                {expandedDb === db.name ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <Database size={16} className="text-text-muted" />
                <div>
                  <span className="text-sm font-medium text-text-primary">{db.label}</span>
                  <div className="flex gap-1.5 mt-0.5">
                    <Badge variant={db.engine === 'postgresql' ? 'accent' : 'default'}>
                      {db.engine}
                    </Badge>
                    <Badge variant="default">{db.table_count} tables</Badge>
                    {db.health?.size_bytes != null && (
                      <Badge variant="default">{formatBytes(db.health.size_bytes)}</Badge>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={db.health?.status === 'healthy' ? 'accent' : 'warning'}>
                  {db.health?.status ?? 'unknown'}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Download size={14} />}
                  onClick={(e) => { e.stopPropagation(); handleExport(db.name); }}
                >
                  Export
                </Button>
              </div>
            </button>
            {expandedDb === db.name && db.tables && (
              <div className="mt-3 pt-3 border-t border-border-base">
                <div className="flex flex-wrap gap-1.5">
                  {db.tables.map((t: string) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => { setSelectedTable(t); setSelectedDb(db.name); }}
                      className={`rounded-md px-2.5 py-1 text-xs font-mono transition-colors cursor-pointer ${
                        selectedTable === t && selectedDb === db.name
                          ? 'bg-accent/10 text-accent border border-accent/30'
                          : 'bg-surface-2 text-text-secondary hover:bg-surface-3'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>

      {/* Table Browser */}
      {selectedTable && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-text-primary">
              {selectedDb} / {selectedTable}
              {tableData?.total != null && (
                <span className="text-text-muted font-normal ml-2">({tableData.total} rows)</span>
              )}
            </h2>
            <div className="w-64">
              <Input
                placeholder="Search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                icon={<Search size={14} />}
              />
            </div>
          </div>
          {tableData?.rows && tableData.rows.length > 0 ? (
            <div className="overflow-x-auto rounded-lg border border-border-base">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-surface-2">
                    {Object.keys(tableData.rows[0]).map((col) => (
                      <th key={col} className="px-3 py-2 text-left font-medium text-text-secondary whitespace-nowrap">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.rows.map((row: any, i: number) => (
                    <tr key={i} className="border-t border-border-base hover:bg-surface-1">
                      {Object.values(row).map((val: any, j: number) => (
                        <td key={j} className="px-3 py-1.5 text-text-primary whitespace-nowrap max-w-[200px] truncate">
                          {val != null ? String(val) : <span className="text-text-muted">null</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Card>
              <p className="text-sm text-text-muted text-center py-4">
                {tableData?.error ? tableData.error : 'No data in this table'}
              </p>
            </Card>
          )}
        </div>
      )}

      {/* RBAC Management */}
      {rbac?.enabled && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-text-primary flex items-center gap-2">
            <Shield size={14} />
            RBAC Management
          </h2>
          <div className="grid grid-cols-2 gap-3">
            <Card>
              <h3 className="text-xs font-medium text-text-secondary mb-2">Roles</h3>
              <div className="space-y-1.5">
                {(rbac.roles ?? []).map((role: any) => (
                  <div key={role.id} className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-text-primary capitalize">{role.name}</span>
                      <p className="text-xs text-text-muted">{role.description}</p>
                    </div>
                    <Badge variant="default">{Object.keys(role.permissions ?? {}).length} resources</Badge>
                  </div>
                ))}
              </div>
            </Card>
            <Card>
              <h3 className="text-xs font-medium text-text-secondary mb-2">Assignments</h3>
              {(rbac.assignments ?? []).length > 0 ? (
                <div className="space-y-1.5">
                  {rbac.assignments.map((a: any) => (
                    <div key={a.id} className="flex items-center justify-between">
                      <span className="text-sm text-text-primary font-mono">{a.agent_id}</span>
                      <Badge variant="accent">{a.role_name}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-text-muted">No role assignments yet</p>
              )}
            </Card>
          </div>
        </div>
      )}

      {/* Storage Health */}
      {health && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-text-primary flex items-center gap-2">
            <Activity size={14} />
            Storage Health
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(health).map(([name, h]: [string, any]) => (
              <Card key={name}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-text-primary capitalize">{name} DB</span>
                  <Badge variant={h.status === 'healthy' ? 'accent' : 'warning'}>{h.status}</Badge>
                </div>
                <div className="space-y-1 text-xs text-text-secondary">
                  <p>Engine: <span className="text-text-primary">{h.engine}</span></p>
                  <p>Latency: <span className="text-text-primary">{h.latency_ms} ms</span></p>
                  {h.size_bytes != null && (
                    <p>Size: <span className="text-text-primary">{formatBytes(h.size_bytes)}</span></p>
                  )}
                  {h.wal_size_bytes != null && (
                    <p>WAL: <span className="text-text-primary">{formatBytes(h.wal_size_bytes)}</span></p>
                  )}
                  {h.connections != null && (
                    <p>Connections: <span className="text-text-primary">{h.connections}</span></p>
                  )}
                  {h.path && <p className="font-mono truncate">Path: {h.path}</p>}
                  {h.host && <p>Host: <span className="text-text-primary">{h.host}:{h.port}</span></p>}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
/* eslint-enable @typescript-eslint/no-explicit-any */
