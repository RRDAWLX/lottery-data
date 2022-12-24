<template>
  <number-bar-chart title="普通号码" :x-labels="xLabels1" :data="chartData1" />
  <number-bar-chart title="特别号码" :x-labels="xLabels2" :data="chartData2" />
  
  <el-table :data="list" v-loading="loading">
    <el-table-column prop="date" label="日期" />
    <el-table-column prop="issue" label="期号" sortable />
    <el-table-column label="号码" v-slot="{ row: { numbers } }">
      {{ numbers.slice(0, 6).map(num => num.toString().padStart(2, '0')).join(' ') }}
      |
      {{ numbers[6].toString().padStart(2, '0') }}
    </el-table-column>
  </el-table>

  <update-button @click="updateData" />
</template>

<script setup>
import { shallowRef, ref, computed } from '@vue/reactivity'
import { ElMessage } from 'element-plus'
import NumberBarChart from '../components/number-bar-chart.vue'
import UpdateButton from '../components/update-button.vue'

let list = shallowRef([])
let loading = ref(false)

let fetchData = async () => {
  try {
    list.value = await fetch('/api/getLotteryData/unionLotto')
      .then(res => res.json())
      .then(json => {
        if (json.code === 0) {
          return json.data
        }

        throw new Error('请求彩票数据出错')
      })
  } catch (e) {
    ElMessage({
      message: e.message,
      type: 'error',
    })
    throw e
  }
}

fetchData()

let updateData = async () => {
  loading.value = true
  
  try {
    await fetch('/api/crawlLotteryData', { method: 'POST' })
      .then(res => res.json())
      .then(json => {
        if (json.code !== 0) {
          throw new Error('抓取数据出错')
        }
      })

    await fetchData()
    ElMessage({
      message: '更新数据成功',
      type: 'success',
    })
  } catch (e) {
    ElMessage({
      message: e.message,
      type: 'error',
    })
    throw e
  } finally {
    loading.value = false
  }
}

let xLabels1 = new Array(33).fill(0).map((_v, i) => (i + 1).toString().padStart(2, '0'))
let chartData1 = computed(() => {
  let numberStatistics = new Array(33).fill(0)

  list.value.forEach(({ numbers }) => {
    for (let i = 0; i < 6; i++) {
      numberStatistics[numbers[i] - 1]++
    }
  })

  return numberStatistics
})

let xLabels2 = new Array(16).fill(0).map((_v, i) => (i + 1).toString().padStart(2, '0'))
let chartData2 = computed(() => {
  let numberStatistics = new Array(16).fill(0)
  list.value.forEach(({ numbers }) => numberStatistics[numbers[6] - 1]++)
  return numberStatistics
})
</script>