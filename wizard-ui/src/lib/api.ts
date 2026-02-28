import type { Platform, HardwareProfile, ModelInfo } from './types';

const API_BASE = '/api/wizard';

export async function fetchPlatforms(): Promise<Platform[]> {
  const res = await fetch(`${API_BASE}/platforms`);
  if (!res.ok) throw new Error(`Failed to fetch platforms: ${res.statusText}`);
  return res.json();
}

export async function fetchHardware(): Promise<{
  hardware: HardwareProfile;
  recommendation: { primary: { id: string; name: string; port: number }; fallback: { id: string; name: string; port: number }; reason: string };
}> {
  const res = await fetch(`${API_BASE}/hardware`);
  if (!res.ok) throw new Error(`Failed to fetch hardware: ${res.statusText}`);
  return res.json();
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) throw new Error(`Failed to fetch models: ${res.statusText}`);
  return res.json();
}

export async function validateAssessment(data: Record<string, unknown>): Promise<{ valid: boolean; errors?: string[] }> {
  const res = await fetch(`${API_BASE}/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Validation failed: ${res.statusText}`);
  return res.json();
}

export async function startDeploy(assessment: Record<string, unknown>): Promise<EventSource> {
  const res = await fetch(`${API_BASE}/deploy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(assessment),
  });
  if (!res.ok) throw new Error(`Deploy start failed: ${res.statusText}`);
  return new EventSource(`${API_BASE}/deploy/stream`);
}

export async function fetchStatus(): Promise<{ status: string; services: Record<string, string> }> {
  const res = await fetch(`${API_BASE}/status`);
  if (!res.ok) throw new Error(`Status check failed: ${res.statusText}`);
  return res.json();
}
