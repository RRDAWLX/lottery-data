<template>
  <v-chart class="chart" :option="option" autoresize />
</template>

<script setup>
import { computed } from '@vue/reactivity'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  ToolboxComponent,
  MarkLineComponent,
  MarkPointComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  GridComponent,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  ToolboxComponent,
  MarkLineComponent,
  MarkPointComponent,
])

let props = defineProps({
  title: {
    type: String,
    default: '',
  },
  // ['01', '02', '03']
  xLabels: {
    type: Array,
    default: () => [],
  },
  // [9, 8, 10]
  data: {
    type: Array,
    default: () => [],
  },
})

let option = computed(() => {
  let len = props.xLabels.length
  let mockData = new Array(len).fill(0)
  let sum = props.data.reduce((s, n) => s + n, 0)

  while (sum-- > 0) {
    let idx = Math.floor(Math.random() * len)
    mockData[idx]++
  }

  return {
    title: {
      text: props.title,
      bottom: 20,
      left: 'center',
    },
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: ['真实数据', '随机生成数据']
    },
    toolbox: {
      show: true,
      feature: {
        dataView: { show: true, readOnly: false },
        magicType: { show: true, type: ['line', 'bar'] },
        restore: { show: true },
        saveAsImage: { show: true }
      }
    },
    calculable: true,
    xAxis: {
      type: 'category',
      data: props.xLabels,
      name: '号码',
    },
    yAxis: {
      type: 'value',
      name: '频次'
    },
    series: [
      {
        name: '真实数据',
        data: props.data,
        type: 'bar',
        markPoint: {
          data: [
            { type: 'max', name: 'Max' },
            { type: 'min', name: 'Min' }
          ]
        },
        markLine: {
          data: [{ type: 'average', name: 'Avg' }]
        },
      },
      {
        name: '随机生成数据',
        data: mockData,
        type: 'bar',
        markPoint: {
          data: [
            { type: 'max', name: 'Max' },
            { type: 'min', name: 'Min' }
          ]
        },
      },
    ]
  }
})
</script>

<style scoped>
.chart {
  height: 300px;
}
</style>