import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],

  server: {
    port: 3000,
    proxy: {
      '/api/wizard': 'http://localhost:9098',
      '/api/dashboard': 'http://localhost:9098',
    },
  },

  build: {
    outDir: 'dist',

    // ── Code Splitting ────────────────────────────────────────
    // Split vendor libraries into separate chunks for better caching.
    // The wizard app, dashboard, and shared UI land in distinct chunks.
    rollupOptions: {
      output: {
        manualChunks: {
          // React core — changes rarely, cacheable long-term
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Animation library — separate chunk so non-animated pages skip it
          'vendor-motion': ['framer-motion'],
          // Icon library — large but tree-shaken; keeping separate aids caching
          'vendor-icons': ['lucide-react'],
          // UI utilities — small, stable
          'vendor-utils': ['clsx', 'tailwind-merge'],
        },
      },
    },

    // ── Asset Optimization ────────────────────────────────────
    // Inline assets smaller than 8KB as base64 data URIs to reduce HTTP requests.
    assetsInlineLimit: 8192,

    // ── Minification ──────────────────────────────────────────
    // esbuild (default) is the fastest minifier; suitable for production.
    minify: 'esbuild',

    // ── Source Maps ───────────────────────────────────────────
    // Hidden source maps for error tracking without exposing source to users.
    sourcemap: 'hidden',

    // ── Target ────────────────────────────────────────────────
    // ES2020 for modern browsers — enables optional chaining, nullish coalescing
    // without needing polyfills. Matches tsconfig.app.json target.
    target: 'es2020',

    // ── Chunk Size Warnings ───────────────────────────────────
    // Warn if any chunk exceeds 300KB (gzipped it will be ~80-100KB).
    chunkSizeWarningLimit: 300,

    // ── CSS ───────────────────────────────────────────────────
    cssMinify: true,

    // ── Reporting ─────────────────────────────────────────────
    // Report compressed sizes in the build output for accurate bundle analysis.
    reportCompressedSize: true,
  },
});
