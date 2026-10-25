<template>
  <div ref="chartRef" class="evaluation-chart" :style="{ height }" role="img" :aria-label="label" />
</template>
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const emit = defineEmits<{ select: [index: number] }>()
const props = withDefaults(defineProps<{ option: Record<string, any>; height?: string; label?: string }>(), { height: '260px', label: '' })
const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | undefined
let observer: ResizeObserver | undefined
const render = () => chart?.setOption(props.option, true)
onMounted(() => {
  chart = echarts.init(chartRef.value!)
  render()
  chart.on('click', (params: any) => emit('select', params.dataIndex))
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(chartRef.value!)
})
watch(() => props.option, render, { deep: true })
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>
<style scoped>
.evaluation-chart { width: 100%; }
</style>
