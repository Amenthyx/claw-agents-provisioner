/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    // ── Environment ──────────────────────────────────────────
    environment: 'jsdom',
    globals: true,

    // ── Setup ────────────────────────────────────────────────
    setupFiles: ['./src/test/setup.ts'],

    // ── Include / Exclude ────────────────────────────────────
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist'],

    // ── Coverage ─────────────────────────────────────────────
    coverage: {
      provider: 'istanbul',
      reporter: ['text', 'text-summary', 'lcov', 'html'],
      reportsDirectory: './coverage',
      include: [
        'src/state/**/*.{ts,tsx}',
        'src/hooks/**/*.{ts,tsx}',
        'src/lib/**/*.{ts,tsx}',
        'src/components/steps/**/*.{ts,tsx}',
        'src/components/ui/**/*.{ts,tsx}',
        'src/components/layout/**/*.{ts,tsx}',
      ],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/**/*.spec.{ts,tsx}',
        'src/test/**',
        'src/vite-env.d.ts',
        'src/main.tsx',
      ],
      thresholds: {
        statements: 70,
        branches: 70,
        functions: 70,
        lines: 70,
      },
    },

    // ── CSS handling ─────────────────────────────────────────
    css: false,
  },
});
