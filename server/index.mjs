/**
 * Koa 服务入口。
 *
 * 启动流程:
 *   1. 读取 config.json
 *   2. 挂载 bodyParser、错误处理、API 路由
 *   3. 启动 HTTP 服务
 *   4. 连接 llm-prediction 的 SSE 事件流（断线自动重连）
 */

import Koa from 'koa';
import bodyParser from 'koa-bodyparser';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import apiRouter from './api/index.mjs';
import predictionRouter from './api/prediction-routes.mjs';
import { connectSSE } from './api/prediction.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const config = JSON.parse(readFileSync(join(__dirname, '..', 'config.json'), 'utf-8'));

const app = new Koa();

app.use(bodyParser());

app.use(async (ctx, next) => {
  try {
    await next();
  } catch (err) {
    ctx.status = err.status || 500;
    ctx.body = { code: 1, msg: err.message };
  }
});

app.use(apiRouter.routes())
  .use(apiRouter.allowedMethods());
app.use(predictionRouter.routes())
  .use(predictionRouter.allowedMethods());

const port = config.server.port;
app.listen(port, () => {
  console.log(`server started, listening at port ${port}`);
  // 连接 llm-prediction 的 SSE 事件流，断线会自动 2s 重连
  connectSSE();
});