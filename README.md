# ARK Nexus — Local-first Multi-AI Hub

## White Space UI base

Overviewを白い宇宙・中央のWhite Singularity・6個の星ナビへ刷新しました。他の主要画面も同じ明るいシェルを使用します。CSS/SVGのみ、追加依存なし。デザイン・操作・証跡の仕様は[White Space UI](docs/white-space-ui.md)。UI刷新は実形式AdapterやユーザーWindows実機の未検証Gateを解除しません。

**V1 development build. Real provider formats are not verified; V1 is not officially PASS.**

Independent repository: Iam-2squared/ark-nexus. ARK AI and ARK Terminal code, CI and roadmaps are separate.

V1 accepts **synthetic-v1 fixtures only** for ChatGPT and Claude. It provides provenance-preserving import, incremental deduplication, projects, offline search, import receipts, integrity checks and a six-screen React dashboard. All external AI connectors and task execution remain disabled.

## Windows quickstart

Python 3.12/3.13 and Node.js 22.12+ are supported.

    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -e ".[dev]"
    python -m pytest -q
    python -m uvicorn nexus.api:app --host 127.0.0.1 --port 8788 --no-access-log --no-proxy-headers

In a separate terminal, from apps/web:

    npm ci --no-audit --no-fund
    npm test
    npm run build
    npm run dev

Open http://127.0.0.1:5173. The workspace starts locked. Copy the locally generated key from **%LOCALAPPDATA%/ARK-Nexus/nexus-access.key** into the dashboard's Local access key field. The key stays in that tab's session storage and is removed when you lock the workspace. Do not send it to other AIs or commit it.

Default Linux key/database directory: ~/.local/share/ark-nexus. NEXUS_DATA_DIR overrides the data directory. An optional NEXUS_API_TOKEN supplies a 32–256-character ASCII token instead of generating a key file. Use a randomly generated secret for an actual installation; the public synthetic test tokens in tests are not installation credentials.

Health: http://127.0.0.1:8788/api/v1/health exposes fixed service metadata without a key. Every other HTTP route requires Authorization: Bearer YOUR_LOCAL_KEY. POST/PATCH/PUT/DELETE also require X-Nexus-Request: 1. Host/Origin/peer checks apply even to health. The UI proxy adds the bearer and write headers; other localhost ports are not authorized.

## Validation and browser tests

CI runs Linux/Windows x Python 3.12/3.13, Ruff, TypeScript/Vite, frontend DOM regressions and Chromium tests against the actual local API/UI. Browser fixtures are synthetic and isolated from normal data; test tokens never authorize external AI execution.

To run browser tests locally, first stop your own Nexus development servers. From apps/web with the Python environment activated:

    npx playwright install --with-deps chromium
    npm run test:e2e

A second run requires a fresh dedicated tmp/e2e-data test directory because first-import count assertions are intentionally fixed. Do not remove or overwrite a normal user database to rerun these tests.

## Data and security

- Real ChatGPT/Claude exports are rejected until owner-approved anonymized samples establish the actual format.
- ZIP/JSON limits and checks reject traversal, symlinks, archive bombs, corrupted/ambiguous JSON and duplicate source identities.
- Changed message content, role or source time rolls back the entire import. Titles and source time ranges update incrementally.
- Stored-record integrity checks and SQLite backup/restore-to-new-location preserve provenance. Existing destinations are never overwritten.
- Local bearer authentication is separate from Host/Origin and browser CSRF controls. No external account login, OAuth, paid API, scraping, task dispatch or live sync is implemented.
- Data defaults outside the source repository; SQLite is plaintext. POSIX files are owner-only; Windows ACLs and owner-machine offline/browser behavior still need evidence before private-data use.
- No destructive deletion endpoint or automatic retention cleanup is enabled.

Public repo: **do not commit actual chats, archives, keys, credentials or databases**.

See [architecture](docs/architecture.md), [roadmap](docs/roadmap.md), [capabilities](docs/capability-matrix.md), [format gate](docs/provider-format-validation.md), [security/data policy](docs/security-and-data.md), and [fixed evaluations](docs/validation.md).
## Windows実機・実形式の検証準備

[Windows実機検証手順](docs/windows-machine-validation.md)に、合成データだけを使うローカルprobeと手動Gateを記載しています。ユーザーPCはNOT RUN、ChatGPT/Claude実形式はBLOCKED、V1公式判定はBLOCKEDです。[実形式の受入れ手順](docs/real-format-acceptance.md)と[保持・削除・暗号化設計](docs/retention-and-deletion-design.md)も参照してください。実際の会話・DB・キーを公開GitHubへ追加しないでください。

実機で行う最小コマンドと共有する6 Gateは[所有者チェックリスト](docs/windows-owner-checklist.md)。中断/権限不足/占有ポートは機密を含まないFAIL、未実施はNOT RUNです。通常profileはprobeの対象外。[データ保護の候補・停止条件](docs/data-protection-decisions.md)は方式選定前の設計で、暗号化や削除を有効化しません。
