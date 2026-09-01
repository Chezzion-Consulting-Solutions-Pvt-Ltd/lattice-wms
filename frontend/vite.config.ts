import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

type ProxyWithRequestHook = {
  on(
    event: 'proxyReq',
    listener: (proxyReq: { setHeader(name: string, value: string | string[]): void }, req: { headers: { host?: string | string[] } }) => void,
  ): void;
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        configure: (proxy) => {
          (proxy as unknown as ProxyWithRequestHook).on('proxyReq', (proxyReq, req) => {
            if (req.headers.host) {
              proxyReq.setHeader('host', req.headers.host);
            }
          });
        },
      },
      '/health': 'http://backend:8000',
    },
  },
});
