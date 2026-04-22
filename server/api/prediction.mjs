/**
 * 与 llm-prediction 服务交互的模块。
 *
 * 职责:
 *   1. 通过 SSE 监听 llm-prediction 的训练状态变更
 *   2. 通过 HTTP 调用 llm-prediction 的预测/训练接口
 *   3. 将状态变更通过 EventEmitter 广播给前端 SSE 客户端
 *
 * 生成唯一的 OBSERVER_ID 用于 SSE 去重:
 *   llm-prediction 端通过 observerId 替换旧观察者队列，防止重复监听。
 *   server 重连时使用同一 observerId，保证始终只有一个监听者。
 */

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { EventEmitter } from 'events';
import { randomUUID } from 'crypto';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const config = JSON.parse(readFileSync(join(__dirname, '..', '..', 'config.json'), 'utf-8'));
const PREDICTION_URL = `http://localhost:${config.prediction.port}`;

// server 实例的唯一标识，用于 llm-prediction 的观察者去重
const OBSERVER_ID = randomUUID();

const trainingStatus = {
  unionLotto: 'offline',
  superLotto: 'offline',
};
const predictionResults = {
  unionLotto: null,
  superLotto: null,
};
const emitter = new EventEmitter();

/** 向 llm-prediction 发送 HTTP 请求，失败返回 null。 */
async function fetchFromPrediction(path, options = {}) {
  try {
    const res = await fetch(`${PREDICTION_URL}${path}`, {
      signal: AbortSignal.timeout(5000),
      ...options,
    });
    return await res.json();
  } catch {
    return null;
  }
}

/** 获取预测结果，处理 offline/training/ready/error 等状态。 */
async function getPrediction(lotteryType) {
  const res = await fetchFromPrediction(`/api/predict/${lotteryType}`);
  if (!res) {
    return { status: 'offline', prediction: null };
  }
  if (res.code === 2) {
    return { status: 'training', prediction: null };
  }
  if (res.code === 0 && res.data) {
    trainingStatus[lotteryType] = res.data.status;
    predictionResults[lotteryType] = res.data.prediction;
    return res.data;
  }
  return { status: res.data?.status || 'error', prediction: res.data?.prediction || null };
}

/** 触发 llm-prediction 开始训练。 */
async function triggerTraining(lotteryType, forceFull = false) {
  const url = `/api/train/${lotteryType}${forceFull ? '?forceFull=true' : ''}`;
  const res = await fetchFromPrediction(url, { method: 'POST' });
  if (!res) {
    return { ok: false, msg: 'prediction service offline' };
  }
  if (res.code === 0) {
    trainingStatus[lotteryType] = 'training';
    predictionResults[lotteryType] = null;
    emitter.emit('status', lotteryType, 'training');
  }
  return res;
}

/** 收到 llm-prediction 的 SSE 事件后，更新本地状态并广播给前端。 */
function handlePredictionEvent(lotteryType, status, prediction = null) {
  trainingStatus[lotteryType] = status;
  predictionResults[lotteryType] = prediction;
  emitter.emit('status', lotteryType, status, prediction);
}

/**
 * 连接 llm-prediction 的 SSE 事件流。
 * 使用 OBSERVER_ID 参数确保同一个 server 实例只有一个观察者。
 * 断线后 2s 自动重连。
 */
function connectSSE() {
  fetch(`${PREDICTION_URL}/api/events?observerId=${OBSERVER_ID}`, {
    headers: { 'Accept': 'text/event-stream' },
  }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    console.log('[prediction] SSE connected to llm-prediction');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.lotteryType && data.status) {
              handlePredictionEvent(data.lotteryType, data.status, data.prediction || null);
            }
          } catch {}
        }
      }
    }
  }).catch(() => {}).finally(() => {
    console.log('[prediction] SSE disconnected from llm-prediction, reconnecting in 2s...');
    setTimeout(connectSSE, 2000);
  });
}

export {
  trainingStatus,
  predictionResults,
  emitter,
  getPrediction,
  triggerTraining,
  connectSSE,
};