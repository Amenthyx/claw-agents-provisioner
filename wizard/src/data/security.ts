import type { SecurityOption } from '../state/types';

export const SECURITY_OPTIONS: SecurityOption[] = [
  {
    id: 'url-filtering',
    name: 'URL Filtering',
    description: 'Block access to malicious or unauthorized URLs and domains',
    category: 'filtering',
    icon: 'Link',
  },
  {
    id: 'content-rules',
    name: 'Content Rules',
    description: 'Enforce content policies and block prohibited patterns',
    category: 'filtering',
    icon: 'FileText',
  },
  {
    id: 'pii-detection',
    name: 'PII Detection',
    description: 'Automatically detect and redact personally identifiable information',
    category: 'filtering',
    icon: 'Eye',
  },
  {
    id: 'network-rules',
    name: 'Network Rules',
    description: 'IP allowlisting, rate limiting, and network isolation',
    category: 'filtering',
    icon: 'Globe',
  },
  {
    id: 'gdpr',
    name: 'GDPR',
    description: 'EU General Data Protection Regulation compliance controls',
    category: 'compliance',
    icon: 'Scale',
  },
  {
    id: 'hipaa',
    name: 'HIPAA',
    description: 'Health Insurance Portability and Accountability Act safeguards',
    category: 'compliance',
    icon: 'Heart',
  },
  {
    id: 'pci-dss',
    name: 'PCI-DSS',
    description: 'Payment Card Industry Data Security Standard compliance',
    category: 'compliance',
    icon: 'CreditCard',
  },
  {
    id: 'soc2',
    name: 'SOC 2',
    description: 'Service Organization Control 2 — trust services criteria',
    category: 'compliance',
    icon: 'ShieldCheck',
  },
];

/* ── PII Types ────────────────────────────────────────────── */

export const PII_TYPES = [
  { id: 'email', label: 'Email Address' },
  { id: 'phone', label: 'Phone Number' },
  { id: 'ssn', label: 'SSN / National ID' },
  { id: 'creditCard', label: 'Credit Card Number' },
  { id: 'address', label: 'Physical Address' },
  { id: 'ipAddress', label: 'IP Address' },
  { id: 'name', label: 'Person Name' },
] as const;

export const PII_ACTIONS = [
  { id: 'redact', label: 'Redact', description: 'Replace with [REDACTED]' },
  { id: 'mask', label: 'Mask', description: 'Partially mask (e.g. ****1234)' },
  { id: 'block', label: 'Block', description: 'Reject the entire request' },
  { id: 'log', label: 'Log Only', description: 'Log detection without modifying' },
] as const;

/* ── Forbidden Content Categories ─────────────────────────── */

export const FORBIDDEN_CONTENT_CATEGORIES = [
  { id: 'malware_creation', label: 'Malware Creation' },
  { id: 'credential_harvesting', label: 'Credential Harvesting' },
  { id: 'pii_exfiltration', label: 'PII Exfiltration' },
  { id: 'csam', label: 'CSAM / Illegal Content' },
  { id: 'weapons_manufacturing', label: 'Weapons Manufacturing' },
  { id: 'harassment', label: 'Harassment / Threats' },
  { id: 'fraud_instructions', label: 'Fraud Instructions' },
  { id: 'privacy_violation', label: 'Privacy Violation' },
  { id: 'safety_bypass', label: 'Safety Bypass Attempts' },
  { id: 'illegal_services', label: 'Illegal Services' },
] as const;

/* ── Default Blocked Domains (from security_rules.json) ──── */

export const DEFAULT_BLOCKED_DOMAINS = [
  '*.malware-domain.com',
  '*.phishing-site.net',
  'pastebin.com',
  '*.tor2web.org',
  '*.onion.ws',
  '*.darkweb.link',
];

/* ── Default Network Rules (from security_rules.json) ────── */

export const DEFAULT_FORBIDDEN_IP_RANGES = [
  '10.0.0.0/8',
  '172.16.0.0/12',
  '192.168.0.0/16',
  '127.0.0.0/8',
  '169.254.0.0/16',
  '0.0.0.0/8',
];

export const DEFAULT_ALLOWED_API_HOSTS = [
  'api.openai.com',
  'api.anthropic.com',
  'api.deepseek.com',
  'generativelanguage.googleapis.com',
  'api.groq.com',
];

/* ── Compliance Rule Definitions ──────────────────────────── */

export interface ComplianceRule {
  id: string;
  description: string;
}

export const COMPLIANCE_RULES: Record<string, ComplianceRule[]> = {
  gdpr: [
    { id: 'gdpr-1', description: 'Data minimization — only process data strictly necessary for the task' },
    { id: 'gdpr-2', description: 'Right to erasure — support data deletion requests within 30 days' },
    { id: 'gdpr-3', description: 'Data portability — export user data in machine-readable format' },
    { id: 'gdpr-4', description: 'Consent management — obtain explicit consent before processing personal data' },
    { id: 'gdpr-5', description: 'Breach notification — notify authorities within 72 hours of a data breach' },
    { id: 'gdpr-6', description: 'Data Protection Impact Assessment for high-risk processing' },
  ],
  hipaa: [
    { id: 'hipaa-1', description: 'PHI encryption — encrypt all protected health information at rest and in transit' },
    { id: 'hipaa-2', description: 'Access controls — implement role-based access to health records' },
    { id: 'hipaa-3', description: 'Audit logging — maintain detailed logs of all PHI access' },
    { id: 'hipaa-4', description: 'Minimum necessary — limit PHI disclosure to the minimum required' },
    { id: 'hipaa-5', description: 'Business Associate Agreements with all third-party processors' },
    { id: 'hipaa-6', description: 'Security incident procedures — document and respond to security incidents' },
  ],
  'pci-dss': [
    { id: 'pci-1', description: 'Cardholder data encryption — encrypt cardholder data using AES-256' },
    { id: 'pci-2', description: 'Never store CVV/CVC codes or full magnetic stripe data' },
    { id: 'pci-3', description: 'Restrict access to cardholder data on a need-to-know basis' },
    { id: 'pci-4', description: 'Quarterly vulnerability scans by an approved scanning vendor' },
    { id: 'pci-5', description: 'Maintain a firewall configuration to protect cardholder data' },
    { id: 'pci-6', description: 'Track and monitor all access to network resources and cardholder data' },
  ],
  soc2: [
    { id: 'soc2-1', description: 'Security — protect against unauthorized access (logical and physical)' },
    { id: 'soc2-2', description: 'Availability — ensure systems are available for operation as committed' },
    { id: 'soc2-3', description: 'Processing integrity — ensure system processing is complete and accurate' },
    { id: 'soc2-4', description: 'Confidentiality — protect designated confidential information' },
    { id: 'soc2-5', description: 'Privacy — collect, use, retain, and dispose of personal information properly' },
    { id: 'soc2-6', description: 'Change management — test and approve all system changes before deployment' },
  ],
};
