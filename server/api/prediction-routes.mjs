/**
 * 预测相关的 API 路由。
 *
 * 路由:
 *   GET  /api/predictionStatus/:lotteryType — 查询预测状态和结果
 *   POST /api/trainModel/:lotteryType        — 触发训练
 *   GET  /api/predictionSSE                  — SSE 事件流，推送训练状态变更给前端
 */

import Router from '@koa/router';
import { trainingStatus, predictionResults, emitter, getPrediction, triggerTraining } from './prediction.mjs';

const router = new Router({
  prefix: '/api',
});

router.get('/predictionStatus/:lotteryType', async (ctx) => {
  const { lotteryType } = ctx.params;
  const data = await getPrediction(lotteryType);
  ctx.body = {
    code: 0,
    msg: 'success',
    data,
  };
});

router.post('/trainModel/:lotteryType', async (ctx) => {
  const { lotteryType } = ctx.params;
  const forceFull = ctx.query.forceFull === 'true';
  const result = await triggerTraining(lotteryType, forceFull);
  ctx.body = result;
});

router.get('/predictionSSE', async (ctx) => {
  ctx.status = 200;
  ctx.set('Content-Type', 'text/event-stream');
  ctx.set('Cache-Control', 'no-cache');
  ctx.set('Connection', 'keep-alive');
  ctx.respond = false;

  const sendEvent = (lotteryType, status, prediction) => {
    ctx.res.write(`data: ${JSON.stringify({ lotteryType, status, prediction })}\n\n`);
  };
  emitter.on('status', sendEvent);
  ctx.res.write(`data: ${JSON.stringify({ connected: true })}\n\n`);
  ctx.req.on('close', () => {
    emitter.off('status', sendEvent);
  });
});

export default router;