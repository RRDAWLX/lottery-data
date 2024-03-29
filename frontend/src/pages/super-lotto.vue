<template>
  <div>最大可能组合：{{ probability.max.join(' ') }}</div>
  <div>最小可能组合：{{ probability.min.join(' ') }}</div>

  <number-bar-chart title="普通号码" :x-labels="xLabels1" :data="chartData1" />
  <number-bar-chart title="特别号码" :x-labels="xLabels2" :data="chartData2" />
  
  <el-table :data="list" v-loading="loading">
    <el-table-column prop="date" label="日期" align="center" />
    <el-table-column prop="issue" label="期号" align="center" sortable :sort-orders="['descending', 'ascending']" />
    <el-table-column label="号码" align="center" v-slot="{ row: { numbers } }">
      {{ numbers.slice(0, 5).map(num => num.toString().padStart(2, '0')).join(' ') }}
      |
      {{ numbers.slice(5).map(num => num.toString().padStart(2, '0')).join(' ') }}
    </el-table-column>
  </el-table>

  <update-button @click="updateData" />
</template>

<script setup>
import { shallowRef, ref, computed } from '@vue/reactivity'
import { ElMessage } from 'element-plus'
import NumberBarChart from '@/components/number-bar-chart.vue'
import UpdateButton from '@/components/update-button.vue'

let list = shallowRef([])
let loading = ref(false)

let fetchData = async () => {
  try {
    list.value = await fetch('/api/getLotteryData/superLotto')
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

let xLabels1 = new Array(35).fill(0).map((_v, i) => (i + 1).toString().padStart(2, '0'))
let chartData1 = computed(() => {
  let numberStatistics = new Array(35).fill(0)
  
  list.value.forEach(({ numbers }) => {
    for (let i = 0; i < 5; i++) {
      numberStatistics[numbers[i] - 1]++
    }
  })

  return numberStatistics
})

let xLabels2 = new Array(12).fill(0).map((_v, i) => (i + 1).toString().padStart(2, '0'))
let chartData2 = computed(() => {
  let numberStatistics = new Array(12).fill(0)

  list.value.forEach(({ numbers }) => {
    for (let i = 5; i < 7; i++) {
      numberStatistics[numbers[i] - 1]++
    }
  })

  return numberStatistics
})

let probability = computed(() => {
  let numbers1 = chartData1.value.map((count, idx) => ({ number: idx + 1, count }))
  numbers1.sort((a, b) => a.count - b.count)
  let numbers2 = chartData2.value.map((count, idx) => ({ number: idx + 1, count }))
  numbers2.sort((a, b) => a.count - b.count)

  let minPart1 = numbers1.slice(0, 5).map(({ number }) => number.toString().padStart(2, '0'))
  minPart1.sort()
  let minPart2 = numbers2.slice(0, 2).map(({ number }) => number.toString().padStart(2, '0'))
  minPart2.sort()

  let maxPart1 = numbers1.slice(-5).map(({ number }) => number.toString().padStart(2, '0'))
  maxPart1.sort()
  let maxPart2 = numbers2.slice(-2).map(({ number }) => number.toString().padStart(2, '0'))
  minPart2.sort()
  
  return {
    min: [...minPart1, ...minPart2],
    max: [...maxPart1, ...maxPart2],
  }
})
</script>