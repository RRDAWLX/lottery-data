# AGENTS.md

## Project overview

Chinese lottery statistics app (双色球 unionLotto + 大乐透 superLotto) with AI prediction. Three independent services: frontend (Vue3), server (Koa), llm-prediction (Flask). No monorepo tooling — each has its own lockfile. Root `package.json` holds shared deps (`axios`, `cheerio`, `fs-extra`) used only by the server.

## Dev commands

Three services must run simultaneously. Start llm-prediction first (server will auto-retry connection).

```bash
cd llm-prediction && uv run server.py  # port 5006
cd server  && yarn dev                  # port 5005, nodemon with --ignore db/db.json
cd frontend && yarn dev                 # port 8080, Vite dev server
```

Each package needs its own install:
- `cd server && yarn install`
- `cd frontend && yarn install`
- `cd llm-prediction && uv sync`

Root `package.json` has no scripts.

Ports are configured in root `config.json`:

```json
{ "server": { "port": 5005 }, "frontend": { "port": 8080 }, "prediction": { "port": 5006 } }
```

Both `server/index.mjs` and `frontend/vite.config.js` read this config at startup.

## Architecture

### llm-prediction/

Flask app (Python, managed by uv). Runs independently, starts training on startup. Exposes REST API + SSE event stream.

**Entry:** `llm-prediction/server.py` — reads `config.json`, creates Flask app, auto-trains on startup.

**API routes:**
- `GET /api/health` — health check
- `GET /api/predict/<lotteryType>` — returns prediction for `superLotto` or `unionLotto`
- `POST /api/train/<lotteryType>?forceFull=true` — triggers async training
- `GET /api/status/<lotteryType>` — current training status
- `GET /api/events?observerId=xxx` — SSE stream of training status changes. `observerId` is used for deduplication — same id replaces the old observer queue.

**Observer pattern:** `observers` is a dict keyed by `observerId`. `notify_observers()` pushes events to all observer queues. SSE endpoint creates a `queue.Queue` per connection; on disconnect, removes itself only if the queue hasn't been replaced.

**Model files:**
- `model/transformer.py` — Custom Transformer (`nn.TransformerEncoder` + per-position output heads). Input: `(batch, n_periods, 7)`. Output: list of 7 logit tensors (ordinary heads output `ordinary_range` classes, special heads output `special_range` classes).
- `model/dataset.py` — `LotteryDataset` wrapping sliding-window samples
- `model/trainer.py` — training loop with incremental support (loads existing `model_state_dict`)
- `data/processor.py` — loads `db.json`, creates sliding windows, incremental window detection, greedy decoding
- `train.py` — orchestrates training (full/incremental auto-detect) and prediction. `run_training()`, `run_prediction()`, checkpoint management.
- `checkpoint/<lotteryType>/model.pt` — model weights
- `checkpoint/<lotteryType>/latest.json` — training state (`n`, `latest_trained_issue`, `total_periods_used`, `model_updated_at`)

**Lottery configs** (in `data/processor.py`):
- unionLotto: 6 ordinary (1-33) + 1 special (1-16)
- superLotto: 5 ordinary (1-35) + 2 special (1-12)

### server/

Koa app using ESM (`.mjs` files). Database is `server/db/db.json` (plain JSON via `fs-extra`). API prefix `/api`. Uses `koa-bodyparser`.

**Entry:** `server/index.mjs` — reads `config.json`, creates Koa app, mounts API routers, starts SSE connection to llm-prediction.

**API routes** (`server/api/index.mjs`):
- `GET /api/getLotteryData/:lotteryType` — returns stored data for `superLotto` or `unionLotto`
- `POST /api/crawlLotteryData` — scrapes 500.com via axios + cheerio, upserts into db.json, then triggers incremental training via HTTP POST to llm-prediction

**Prediction routes** (`server/api/prediction-routes.mjs`):
- `GET /api/predictionStatus/:lotteryType` — proxies to llm-prediction `/api/predict/`, returns `{status, prediction}`. Falls back to `{status:'offline'}` if llm-prediction is down.
- `POST /api/trainModel/:lotteryType` — proxies training trigger to llm-prediction
- `GET /api/predictionSSE` — SSE stream to frontend, forwards events from llm-prediction

**Prediction module** (`server/api/prediction.mjs`):
- Generates a unique `OBSERVER_ID` via `crypto.randomUUID()` on startup
- `connectSSE()` — connects to llm-prediction `/api/events?observerId=<id>`. On disconnect, retries every 2s. Same observerId ensures no duplicate observers.
- `handlePredictionEvent()` — updates in-memory `trainingStatus`/`predictionResults`, emits to SSE clients
- `getPrediction()` — HTTP fetch to llm-prediction, handles offline/training/ready/error states
- `triggerTraining()` — HTTP POST to llm-prediction

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
- `union-lotto.vue` — 双色球: 6 ordinary numbers (1-33) + 1 special (1-16). Shows prediction panel, min/max probability combos, bar charts for each number group, sortable table, update button
- `super-lotto.vue` — 大乐透: 5 ordinary numbers (1-35) + 2 special (1-12). Same layout as union-lotto

**Components:**
- `prediction-panel.vue` — Shows prediction based on status: `ready` → blue/orange number balls, `training` → "模型更新中...", `offline` → "预测服务未启动", `error` → "模型训练失败", `idle` → "加载中...". Connects to `/api/predictionSSE` for real-time updates, polls `/api/predictionStatus` every 10s.
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
- llm-prediction is fully decoupled from server — it runs as a standalone Flask service and uses observer pattern (dict keyed by observerId) for SSE notifications.
- server auto-reconnects to llm-prediction SSE every 2s on disconnect, using a stable observerId to prevent duplicate observers.
- Model output is a list of per-position logit tensors (not a stacked tensor), because ordinary and special heads have different output dimensions.
- `config.json` `prediction.port` (5006) is used by both llm-prediction (Flask) and server (HTTP/SSE client).