import { useState, useEffect, useRef, useCallback } from 'react';
import { Trash2, RefreshCw } from 'lucide-react';
import { api } from '../../lib/api';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

type LogLevel = 'info' | 'warn' | 'error' | 'debug';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  source: string;
}

const LEVEL_COLORS: Record<LogLevel, 'default' | 'warning' | 'error' | 'accent'> = {
  info: 'default',
  warn: 'warning',
  error: 'error',
  debug: 'accent',
};

const DEMO_LOGS: LogEntry[] = [
  { timestamp: new Date().toISOString(), level: 'info', message: 'Dashboard started', source: 'system' },
  { timestamp: new Date().toISOString(), level: 'info', message: 'Agent fleet health check complete', source: 'monitor' },
  { timestamp: new Date().toISOString(), level: 'debug', message: 'Security rules loaded (453 lines)', source: 'security' },
  { timestamp: new Date().toISOString(), level: 'warn', message: 'No agents currently running', source: 'monitor' },
  { timestamp: new Date().toISOString(), level: 'info', message: 'Strategy routing table cached', source: 'strategy' },
];

export function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>(DEMO_LOGS);
  const [filter, setFilter] = useState<LogLevel | 'all'>('all');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [backendAvailable, setBackendAvailable] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const fetchLogs = useCallback(async () => {
    try {
      const data = await api.dashboard.getLogs();
      if (data.logs && data.logs.length > 0) {
        setLogs(data.logs);
        setBackendAvailable(true);
      }
    } catch {
      setBackendAvailable(false);
      // Keep demo logs as fallback
    }
  }, []);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  // Auto-poll every 5 seconds
  useEffect(() => {
    if (!autoRefresh) return;
    const iv = setInterval(fetchLogs, 5000);
    return () => clearInterval(iv);
  }, [autoRefresh, fetchLogs]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const filtered = filter === 'all' ? logs : logs.filter((l) => l.level === filter);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">System Logs</h1>
          <p className="text-sm text-text-secondary mt-1">
            {backendAvailable ? 'Live log stream from wizard API' : 'Demo logs (backend unavailable)'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={autoRefresh ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
            icon={<RefreshCw size={14} />}
          >
            {autoRefresh ? 'Auto' : 'Paused'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            icon={<Trash2 size={14} />}
            onClick={() => setLogs([])}
          >
            Clear
          </Button>
        </div>
      </div>

      {/* Filter buttons */}
      <div className="flex gap-2">
        {(['all', 'info', 'warn', 'error', 'debug'] as const).map((level) => (
          <Button
            key={level}
            variant={filter === level ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setFilter(level)}
          >
            {level.charAt(0).toUpperCase() + level.slice(1)}
            {level !== 'all' && (
              <Badge variant="muted" className="ml-1">
                {logs.filter((l) => l.level === level).length}
              </Badge>
            )}
          </Button>
        ))}
      </div>

      <Card className="p-0 overflow-hidden">
        <div className="h-[500px] overflow-y-auto p-4 font-mono text-xs text-text-secondary leading-relaxed">
          {filtered.length === 0 ? (
            <p className="text-text-muted text-center py-8">No logs to display</p>
          ) : (
            filtered.map((log, i) => (
              <div key={i} className="flex gap-3 py-1 border-b border-border-subtle last:border-0">
                <span className="text-text-muted shrink-0 w-[180px]">
                  {new Date(log.timestamp).toLocaleTimeString('en-US', { hour12: false })}
                </span>
                <Badge variant={LEVEL_COLORS[log.level]} className="shrink-0 w-[50px] text-center justify-center">
                  {log.level}
                </Badge>
                <span className="text-text-muted shrink-0 w-[80px]">[{log.source}]</span>
                <span className="text-text-primary">{log.message}</span>
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </Card>
    </div>
  );
}
