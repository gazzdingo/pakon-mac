import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Everything is bundled: the app ships offline and has no network at runtime.
// No CDN, no external fonts — system stacks only (see src/theme.css).
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  build: {
    // `dist` is vite's alone, and `emptyOutDir` wipes it on every build.
    // electron-builder's default output directory is also `dist`, and
    // package.json's `files: ["dist/**/*"]` then globs whatever is in it — so
    // a `vite build` used to delete the packaged app, and a package could
    // scoop up the previous package. package.json now sets
    // build.directories.output to `release`; if you change either name,
    // change it so the two still differ. See docs/62 §5.3.6.
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 2000,
  },
  server: { port: 5273, strictPort: true },
});
