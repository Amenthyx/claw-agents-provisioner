import { motion } from 'framer-motion';
import type { WizardState } from '../../state/types';
import { PLATFORMS } from '../../data/platforms';

interface Props {
  state: WizardState;
}

/**
 * Architecture diagram matching the xclaw-ecosystem.drawio schema.
 * Vertical flow: Client -> Security Inbound -> Gateway -> Optimizer Pre ->
 * Agent -> LLM -> Optimizer Post + Logger -> Security Outbound -> Client (return).
 * Shows real ports and URLs from user configuration.
 */
export function ArchitectureDiagram({ state }: Props) {
  const platform = PLATFORMS.find((p) => p.id === state.platform);
  const agentPort = platform?.port ?? 3100;
  const gatewayPort = state.gateway.port || 9095;
  const isLocal = state.llmProvider === 'local' || state.llmProvider === 'hybrid';
  const isCloud = state.llmProvider === 'cloud' || state.llmProvider === 'hybrid';
  const runtimePort = state.runtime === 'ollama' ? 11434
    : state.runtime === 'llama-cpp' ? 8080
    : state.runtime === 'vllm' ? 8000
    : state.runtime === 'localai' ? 8080
    : 11434;

  // Node definitions following draw.io flow
  const nodes = [
    {
      id: 'client',
      step: 1,
      label: 'CLIENT APPLICATION',
      sublabel: 'Telegram / WhatsApp / Any SDK-compatible app',
      detail: `POST /v1/chat/completions | Target: localhost:${gatewayPort}`,
      color: '#3b82f6',
      bgColor: '#0d1520',
    },
    ...(state.securityEnabled ? [{
      id: 'sec-inbound',
      step: 2,
      label: 'SECURITY GATE — INBOUND CHECK',
      sublabel: 'claw_security.py',
      detail: 'check_url() -> check_content() -> detect_pii() | Rate: 120 RPM',
      color: '#ff3355',
      bgColor: '#1a0a0a',
    }] : []),
    {
      id: 'gateway',
      step: state.securityEnabled ? 3 : 2,
      label: 'GATEWAY ROUTER',
      sublabel: `claw_router.py :${gatewayPort}`,
      detail: `Routing: ${state.gateway.routing || 'auto-detect'} | Failover: ${state.gateway.failover || 'local-first'}`,
      color: '#00ffcc',
      bgColor: '#0d1117',
    },
    {
      id: 'optimizer-pre',
      step: state.securityEnabled ? 4 : 3,
      label: 'OPTIMIZER — 11 PRE-CALL RULES',
      sublabel: 'claw_optimizer.py :9091',
      detail: 'Dedup | Cache | Budget | Complexity | Fallback',
      color: '#a855f7',
      bgColor: '#0d1117',
    },
    {
      id: 'agent',
      step: state.securityEnabled ? 5 : 4,
      label: `AGENT — ${platform?.name ?? 'ZeroClaw'}`,
      sublabel: `${platform?.language ?? 'Rust'} :${agentPort} | ${platform?.memory ?? '512MB'}`,
      detail: 'Security rules injected at boot | Real-time I/O validation',
      color: '#22c55e',
      bgColor: '#0d1117',
    },
    {
      id: 'llm',
      step: state.securityEnabled ? 6 : 5,
      label: 'LLM BACKENDS',
      sublabel: [
        isCloud ? 'Cloud: Anthropic | OpenAI | DeepSeek | Google' : '',
        isLocal ? `Local: ${state.runtime || 'Ollama'} :${runtimePort}` : '',
        state.llmProvider === 'hybrid' ? 'Hybrid: local primary + cloud fallback (R11)' : '',
      ].filter(Boolean).join(' | '),
      detail: state.selectedModels.length > 0
        ? `Models: ${state.selectedModels.slice(0, 3).join(', ')}${state.selectedModels.length > 3 ? ` +${state.selectedModels.length - 3} more` : ''}`
        : 'Models configured via provider',
      color: '#f97316',
      bgColor: '#0d1117',
    },
    {
      id: 'optimizer-post',
      step: state.securityEnabled ? 7 : 6,
      label: 'OPTIMIZER — POST-CALL + LOGGER',
      sublabel: 'R12 ResponseQualityGate | R13 CostAttributionLogger',
      detail: 'Log: model, tokens, cost, latency | Storage: SQLite + JSONL',
      color: '#a855f7',
      bgColor: '#0d1117',
    },
    ...(state.securityEnabled ? [{
      id: 'sec-outbound',
      step: 8,
      label: 'SECURITY GATE — OUTBOUND SCAN',
      sublabel: 'mask_secrets() -> detect_pii() -> check_content()',
      detail: '16 secret patterns | 8 PII types | All replaced with ***REDACTED***',
      color: '#ff3355',
      bgColor: '#1a0a0a',
    }] : []),
    {
      id: 'response',
      step: state.securityEnabled ? 9 : 7,
      label: 'RESPONSE DELIVERED TO CLIENT',
      sublabel: 'SSE stream or JSON response',
      detail: 'Secrets redacted | PII masked | Content verified | Cost logged',
      color: '#00ff88',
      bgColor: '#0f1f15',
    },
  ];

  const nodeH = 72;
  const nodeW = 460;
  const gap = 16;
  const arrowGap = 24;
  const padX = 40;
  const padY = 30;
  const totalH = nodes.length * (nodeH + gap + arrowGap) + padY * 2;
  const totalW = nodeW + padX * 2 + 160; // extra for step labels + return arrow

  // Edge labels between consecutive nodes
  const edgeLabels = [
    'HTTPS request',
    ...(state.securityEnabled ? ['request clean, proceed'] : []),
    'routed to optimizer',
    'optimized request -> selected agent',
    'LLM inference call',
    'raw response (may contain secrets)',
    'quality checked, cost logged',
    ...(state.securityEnabled ? ['response enters security scan', 'clean response (secrets redacted)'] : []),
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.3, duration: 0.6 }}
      className="rounded-xl border border-border-base bg-surface-1 p-4 overflow-x-auto"
    >
      <h3 className="text-sm font-medium text-text-primary mb-1">Architecture Diagram</h3>
      <p className="text-xs text-text-muted mb-4">XClaw Runtime Ecosystem — matches draw.io schema</p>
      <svg
        viewBox={`0 0 ${totalW} ${totalH}`}
        className="w-full"
        style={{ minWidth: 580, maxHeight: 1200 }}
      >
        <defs>
          <marker id="arrow-down" markerWidth="8" markerHeight="6" refX="4" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#52525b" />
          </marker>
          <marker id="arrow-up" markerWidth="8" markerHeight="6" refX="4" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#00ff88" />
          </marker>
          <style>{`
            @keyframes dash { to { stroke-dashoffset: -20; } }
            .anim-dash { animation: dash 1s linear infinite; }
            @keyframes pulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }
            .pulse-dot { animation: pulse 2s ease-in-out infinite; }
          `}</style>
        </defs>

        {/* Nodes */}
        {nodes.map((node, i) => {
          const x = padX + 50;
          const y = padY + i * (nodeH + gap + arrowGap);

          return (
            <motion.g
              key={node.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 + i * 0.08, duration: 0.4 }}
            >
              {/* Step number label */}
              <text
                x={x - 12}
                y={y + nodeH / 2}
                textAnchor="end"
                fill={node.color}
                className="text-[10px] font-bold"
                opacity={0.9}
              >
                STEP {node.step}
              </text>

              {/* Node box */}
              <rect
                x={x}
                y={y}
                width={nodeW}
                height={nodeH}
                rx={8}
                fill={node.bgColor}
                stroke={node.color}
                strokeWidth="1.5"
              />

              {/* Health indicator dot */}
              <circle cx={x + nodeW - 14} cy={y + 12} r="4" fill="#22c55e" className="pulse-dot" />

              {/* Label */}
              <text x={x + 14} y={y + 18} fill={node.color} className="text-[11px] font-bold">
                {node.label}
              </text>

              {/* Sublabel */}
              <text x={x + 14} y={y + 34} fill="#888" className="text-[9px]">
                {node.sublabel}
              </text>

              {/* Detail */}
              <text x={x + 14} y={y + 50} fill="#666" className="text-[8px]">
                {node.detail}
              </text>

              {/* Port badge */}
              {node.sublabel.includes(':') && (
                <rect x={x + nodeW - 80} y={y + nodeH - 20} width={66} height={14} rx={3} fill={node.color} opacity={0.15} />
              )}

              {/* Arrow to next node */}
              {i < nodes.length - 1 && (
                <>
                  <line
                    x1={x + nodeW / 2}
                    y1={y + nodeH}
                    x2={x + nodeW / 2}
                    y2={y + nodeH + gap + arrowGap}
                    stroke="#52525b"
                    strokeWidth="1.5"
                    strokeDasharray="6 4"
                    className="anim-dash"
                    markerEnd="url(#arrow-down)"
                  />
                  {/* Edge label */}
                  {edgeLabels[i] && (
                    <text
                      x={x + nodeW / 2 + 10}
                      y={y + nodeH + (gap + arrowGap) / 2 + 3}
                      fill="#666"
                      className="text-[8px]"
                    >
                      {edgeLabels[i]}
                    </text>
                  )}
                  {/* Pulse dot traveling down */}
                  <circle r="3" fill={node.color} opacity={0.8}>
                    <animateMotion
                      dur={`${1.5 + i * 0.2}s`}
                      repeatCount="indefinite"
                      path={`M${x + nodeW / 2},${y + nodeH} L${x + nodeW / 2},${y + nodeH + gap + arrowGap}`}
                    />
                  </circle>
                </>
              )}
            </motion.g>
          );
        })}

        {/* Return arrow: Security Outbound / Response -> Client (right side, going up) */}
        {(() => {
          const firstY = padY + nodeH / 2;
          const lastY = padY + (nodes.length - 1) * (nodeH + gap + arrowGap) + nodeH / 2;
          const returnX = padX + 50 + nodeW + 80;

          return (
            <motion.g
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.2, duration: 0.6 }}
            >
              {/* Vertical line going up on the right side */}
              <line
                x1={returnX}
                y1={lastY}
                x2={returnX}
                y2={firstY}
                stroke="#00ff88"
                strokeWidth="2"
                strokeDasharray="8 4"
                className="anim-dash"
                markerEnd="url(#arrow-up)"
              />
              {/* Horizontal connector from last node to vertical line */}
              <line
                x1={padX + 50 + nodeW}
                y1={lastY}
                x2={returnX}
                y2={lastY}
                stroke="#00ff88"
                strokeWidth="2"
                strokeDasharray="8 4"
              />
              {/* Horizontal connector from vertical line to first node */}
              <line
                x1={returnX}
                y1={firstY}
                x2={padX + 50 + nodeW}
                y2={firstY}
                stroke="#00ff88"
                strokeWidth="2"
                strokeDasharray="8 4"
                markerEnd="url(#arrow-up)"
              />
              {/* Label on return path */}
              <text
                x={returnX + 6}
                y={(firstY + lastY) / 2}
                fill="#00ff88"
                className="text-[9px] font-medium"
                transform={`rotate(-90, ${returnX + 6}, ${(firstY + lastY) / 2})`}
                textAnchor="middle"
              >
                Response returned to client (clean)
              </text>
              {/* Pulse dot going up */}
              <circle r="3" fill="#00ff88" opacity={0.8}>
                <animateMotion
                  dur="3s"
                  repeatCount="indefinite"
                  path={`M${returnX},${lastY} L${returnX},${firstY}`}
                />
              </circle>
            </motion.g>
          );
        })()}
      </svg>
    </motion.div>
  );
}
