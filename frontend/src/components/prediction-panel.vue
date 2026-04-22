<!--
  预测面板组件。

  根据 status 显示不同内容:
    offline  → "预测服务未启动"
    training → "模型更新中..."（带旋转图标）
    ready    → 显示预测号码（普通号蓝球、特别号橙球）
    error    → "模型训练失败，请稍后重试"
    idle     → "加载中..."

  数据获取方式:
    1. SSE (/api/predictionSSE): 实时监听训练状态变更
    2. 轮询 (/api/predictionStatus/:lotteryType): 每 10s 轮询，兜底保证状态同步
-->

<template>
  <div class="prediction-panel">
    <div v-if="status === 'offline'" class="prediction-status offline">
      <el-icon><WarningFilled /></el-icon>
      <span>预测服务未启动</span>
    </div>
    <div v-else-if="status === 'training'" class="prediction-status">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>模型更新中...</span>
    </div>
    <div v-else-if="status === 'ready' && prediction" class="prediction-result">
      <div class="prediction-label">AI预测号码</div>
      <div class="prediction-numbers">
        <span
          v-for="(num, idx) in prediction"
          :key="idx"
          :class="['prediction-number', idx < ordinaryCount ? 'ordinary' : 'special']"
        >
          {{ num.toString().padStart(2, '0') }}
        </span>
      </div>
    </div>
    <div v-else-if="status === 'error'" class="prediction-status error">
      <el-icon><WarningFilled /></el-icon>
      <span>模型训练失败，请稍后重试</span>
    </div>
    <div v-else class="prediction-status">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Loading, WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  lotteryType: {
    type: String,
    required: true,
  },
  ordinaryCount: {
    type: Number,
    required: true,
  },
})

const status = ref('idle')
const prediction = ref(null)
let eventSource = null
let pollTimer = null

/** 主动拉取当前预测状态（兜底机制）。 */
const fetchData = async () => {
  try {
    const res = await fetch(`/api/predictionStatus/${props.lotteryType}`)
    const json = await res.json()
    if (json.code === 0 && json.data) {
      status.value = json.data.status
      prediction.value = json.data.prediction
    } else {
      status.value = 'offline'
    }
  } catch {
    status.value = 'offline'
  }
}

/** 建立前端 → server 的 SSE 连接，实时接收状态变更。 */
const connectSSE = () => {
  eventSource = new EventSource('/api/predictionSSE')
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.lotteryType === props.lotteryType) {
      status.value = data.status
      prediction.value = data.prediction
    }
  }
  eventSource.onerror = () => {
    eventSource.close()
    eventSource = null
    setTimeout(connectSSE, 5000)
  }
}

/** 定时轮询，防止 SSE 偶尔丢失事件。 */
const startPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(fetchData, 10000)
}

onMounted(() => {
  fetchData()
  connectSSE()
  startPolling()
})

onUnmounted(() => {
  if (eventSource) {
    eventSource.close()
  }
  if (pollTimer) {
    clearInterval(pollTimer)
  }
})

watch(() => props.lotteryType, () => {
  fetchData()
})
</script>

<style scoped>
.prediction-panel {
  margin: 16px 0;
  padding: 16px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.prediction-status {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.prediction-status.offline {
  color: var(--el-color-info);
}

.prediction-status.error {
  color: var(--el-color-danger);
}

.prediction-result {
  text-align: center;
}

.prediction-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.prediction-numbers {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}

.prediction-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 14px;
  font-weight: bold;
  color: #fff;
}

.prediction-number.ordinary {
  background: #409eff;
}

.prediction-number.special {
  background: #e6a23c;
}
</style>