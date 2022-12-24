<template>
  <v-chart class="chart" :option="option" autoresize />
</template>

<script setup>
import { computed } from '@vue/reactivity'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  BarChart,
  GridComponent,
  TitleComponent,
  TooltipComponent,
])

let props = defineProps({
  title: {
    type: String,
    default: '',
  },
  xLabels: {
    type: Array,
    default: () => [],
  },
  data: {
    type: Array,
    default: () => [],
  },
})

let option = computed(() => ({
  title: {
    text: props.title,
    bottom: 20,
    left: 'center',
  },
  tooltip: {
    trigger: 'item',
    formatter: '{c}',
  },
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
      data: props.data,
      type: 'bar',
      showBackground: true,
      backgroundStyle: {
        color: 'rgba(180, 180, 180, 0.2)'
      }
    }
  ]
}))
</script>

<style scoped>
.chart {
  height: 300px;
}
</style>