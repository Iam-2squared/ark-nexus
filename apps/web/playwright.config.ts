import { defineConfig } from '@playwright/test'
import { resolve } from 'node:path'

const repositoryRoot = resolve(import.meta.dirname,'../..')
// Deliberately public synthetic CI fixture token. Never use it with private data.
export const syntheticKey = 'synthetic-e2e-token-not-a-real-secret'

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.ts',
  workers: 1,
  retries: 0,
  use: {
    baseURL:'http://127.0.0.1:5173',viewport:{width:1440,height:1000},
    // Synthetic local test content only. No GPU is available on the Actions runner.
    // These Chromium test flags are never recommended for an owner's private browser.
    launchOptions:{args:['--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader']},
  },
  webServer: [
    {
      command:'python -m uvicorn nexus.api:app --host 127.0.0.1 --port 8788 --no-access-log --no-proxy-headers',
      cwd:repositoryRoot,
      url:'http://127.0.0.1:8788/api/v1/health',
      env:{NEXUS_DATA_DIR:resolve(repositoryRoot,'tmp/e2e-data'),NEXUS_API_TOKEN:syntheticKey},
      reuseExistingServer:false,
    },
    {command:'npm run dev',url:'http://127.0.0.1:5173',reuseExistingServer:false},
  ],
})
