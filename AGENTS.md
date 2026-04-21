# AGENTS.md

## Project overview

Chinese lottery statistics app (双色球 unionLotto + 大乐透 superLotto). Two separate packages, no monorepo tooling — each has its own `yarn.lock`. Root `package.json` holds shared deps (`axios`, `cheerio`, `fs-extra`) used only by the server.

## Dev commands

Both servers must run simultaneously. Start server first (frontend proxies `/api` to it).

```bash
cd server  && yarn dev    # port 5005, nodemon with --ignore db/db.json
cd frontend && yarn dev   # port 8080, Vite dev server
```

Each package needs its own `yarn install`. Root `package.json` has no scripts.

Ports are configured in root `config.json`:

```json
{ "server": { "port": 5005 }, "frontend": { "port": 8080 } }
```

Both `server/index.mjs` and `frontend/vite.config.js` read this config at startup.

## Architecture

### server/

Koa app using ESM (`.mjs` files). Database is `server/db/db.json` (plain JSON via `fs-extra`). API prefix `/api`.

**Entry:** `server/index.mjs` — reads `config.json`, creates Koa app, mounts API router.

**API routes** (`server/api/index.mjs`):
- `GET /api/getLotteryData/:lotteryType` — returns stored data for `superLotto` or `unionLotto`
- `POST /api/crawlLotteryData` — scrapes 500.com via axios + cheerio, upserts into db.json

**Data flow:**
- `crawl-lottery-data.mjs` — two crawler functions:
  - `crawlSuperLotto()` — fetches from `datachart.500.com/dlt/history/newinc/history.php?limit=100&sort=1`, parses HTML table (`#tdata tr`), extracts issue number, 7 numbers (5 ordinary + 2 special), and date from td[14]
  - `crawlUnionLotto()` — fetches from `datachart.500.com/ssq/history/newinc/history.php?limit=100&sort=1`, parses similarly, 7 numbers (6 ordinary + 1 special), date from td[15]
- `db/index.mjs` — lazy-inits from `db.json`, parses stringified inner objects on read; `insert()` deduplicates by `issue`, sorts by issue ascending, writes back as stringified objects with 2-space indent

### frontend/

Vue 3 + Vite + Element Plus + ECharts (via `vue-echarts`). `@` alias → `src/`. Vite proxies `/api` → `http://localhost:5005`.

**Entry:** `frontend/src/main.js` → `App.vue`

**Router** (`frontend/src/router.js`):
- `/union-lotto` → `pages/union-lotto.vue`
- `/super-lotto` → `pages/super-lotto.vue`
- Default redirect → `/union-lotto`

**Pages:**
- `union-lotto.vue` — 双色球: 6 ordinary numbers (1-33) + 1 special (1-16). Shows min/max probability combos, bar charts for each number group, sortable table, update button
- `super-lotto.vue` — 大乐透: 5 ordinary numbers (1-35) + 2 special (1-12). Same layout as union-lotto

**Components:**
- `number-bar-chart.vue` — ECharts bar chart comparing real data vs randomly generated data, with markPoint (max/min) and markLine (average)
- `update-button.vue` — Fixed-position button (bottom-right) that triggers `POST /api/crawlLotteryData`

**App.vue** — Navigation bar with two router-links (双色球 / 超级大乐透), wraps router-view in `<suspense>`

## Key facts

- No tests, linter, or typechecker configured. Don't add them unless asked.
- `server/db/db.json` is the only data store. It's hand-edited JSON with stringified inner objects (the `db/index.mjs` module parses them on read).
- Lottery types in code: `superLotto`, `unionLotto`.
- Both pages call the same `POST /api/crawlLotteryData` endpoint which crawls **both** lottery types simultaneously.
- ECharts uses tree-shaking imports — only `BarChart`, `LineChart`, and used components are registered in `number-bar-chart.vue`.
- `assets/` contains static images (`ordinary-numbers.png`, `special-numbers.png`).