/**
 * Vitest test setup — configures jsdom environment, mocks, and global utilities.
 *
 * Runs before every test file.
 */
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// ── Auto-cleanup after each test ────────────────────────────
afterEach(() => {
  cleanup();
});

// ── Mock: window.matchMedia ─────────────────────────────────
// jsdom does not implement matchMedia; many UI components rely on it.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// ── Mock: IntersectionObserver ───────────────────────────────
// Used by framer-motion and lazy loading components.
class MockIntersectionObserver {
  readonly root: Element | null = null;
  readonly rootMargin: string = '';
  readonly thresholds: ReadonlyArray<number> = [];
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  takeRecords = vi.fn().mockReturnValue([]);
}

Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  value: MockIntersectionObserver,
});

// ── Mock: ResizeObserver ────────────────────────────────────
class MockResizeObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: MockResizeObserver,
});

// ── Mock: scrollIntoView ────────────────────────────────────
// jsdom does not implement scrollIntoView.
Element.prototype.scrollIntoView = vi.fn();

// ── Mock: navigator.clipboard ───────────────────────────────
Object.defineProperty(navigator, 'clipboard', {
  writable: true,
  value: {
    writeText: vi.fn().mockResolvedValue(undefined),
    readText: vi.fn().mockResolvedValue(''),
  },
});

// ── Mock: fetch (global default) ────────────────────────────
// Individual tests can override this via vi.spyOn or vi.fn().
if (!globalThis.fetch) {
  globalThis.fetch = vi.fn().mockRejectedValue(new Error('No mock configured for fetch'));
}

// ── Mock: WebGL for hardware detection ──────────────────────
// The wizard's hardware detection tries to create a canvas with WebGL.
HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue(null);
