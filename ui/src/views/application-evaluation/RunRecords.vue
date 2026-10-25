<template>
  <el-card class="records-card" shadow="never">
    <template #header>
      <div class="records-heading"><strong>{{ tr('executionsTab') }} <EvaluationHelp :text="tr('executionsHelp')" /></strong><el-button :icon="Refresh" :loading="loading" @click="$emit('refresh')">{{ tr('refresh') }}</el-button></div>
    </template>
    <div class="records-toolbar">
      <el-input v-model="search" clearable :prefix-icon="Search" :placeholder="tr('searchTask')" :aria-label="tr('searchTask')" />
      <el-select v-model="statusFilter" :aria-label="tr('status')"><el-option :label="tr('all')" value="all" /><el-option v-for="state in states" :key="state" :label="tr(state)" :value="state" /></el-select>
    </div>
    <el-table v-loading="loading" :data="filteredRuns" row-key="id">
      <el-table-column :label="tr('taskName')" min-width="220"><template #default="{ row }"><strong>{{ row.dataset_name }}</strong><div class="record-meta">{{ row.dataset_version?.slice(0, 8) || '—' }} · {{ date(row.created_at) }}</div></template></el-table-column>
      <el-table-column :label="tr('status')" width="120"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ tr(row.status) }}</el-tag></template></el-table-column>
      <el-table-column :label="tr('progress')" min-width="160"><template #default="{ row }"><el-progress :percentage="row.total ? Math.min(100, Math.round(row.completed / row.total * 100)) : 0" :stroke-width="6" /><span class="record-meta">{{ row.completed }} / {{ row.total }} {{ tr('questions') }}</span></template></el-table-column>
      <el-table-column :label="tr('error')" min-width="180" show-overflow-tooltip><template #default="{ row }"><span :class="{ 'record-error': row.error }">{{ row.error || '—' }}</span></template></el-table-column>
      <el-table-column :label="tr('actions')" width="260" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="$emit('view', row)">{{ tr('viewRunDetail') }}</el-button><el-button v-if="['completed', 'partial'].includes(row.status)" link @click="$emit('report', row)">{{ tr('viewReport') }}</el-button><el-tooltip :content="tr(row.can_replay ? 'replayHint' : 'replayUnavailable')"><span><el-button link :disabled="replayBusy || !row.can_replay" @click="$emit('replay', row)">{{ tr('replay') }}</el-button></span></el-tooltip></template></el-table-column>
      <template #empty><el-empty :description="tr('noRuns')" :image-size="64" /></template>
    </el-table>
  </el-card>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh, Search } from '@element-plus/icons-vue'
import EvaluationHelp from './EvaluationHelp.vue'
const props = defineProps<{ runs: any[]; loading: boolean; replayBusy: boolean }>()
defineEmits<{ refresh: []; view: [row: any]; report: [row: any]; replay: [row: any] }>()
const { t } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const search = ref('')
const statusFilter = ref('all')
const states = ['queued', 'running', 'completed', 'partial', 'failed']
const filteredRuns = computed(() => props.runs.filter(row =>
  (statusFilter.value === 'all' || row.status === statusFilter.value) &&
  `${row.dataset_name} ${row.dataset_version}`.toLowerCase().includes(search.value.toLowerCase()),
))
const date = (value: string) => value ? new Date(value).toLocaleString() : '—'
const statusType = (state: string) => state === 'completed' ? 'success' : state === 'failed' ? 'danger' : state === 'partial' ? 'warning' : 'info'
</script>
<style scoped>
.records-card { border-radius: 10px; border-color: var(--el-border-color-lighter); }
.records-card :deep(.el-card__body) { padding: 0; }
.records-heading, .records-toolbar { display: flex; align-items: center; gap: 12px; }
.records-heading { justify-content: space-between; }
.records-toolbar { flex-wrap: wrap; padding: 16px 20px; }
.records-toolbar > .el-input { width: 280px; }
.records-toolbar > .el-select { width: 150px; }
.record-meta { color: var(--el-text-color-secondary); font-size: 12px; margin-top: 6px; }
.record-error { color: var(--el-color-danger); }
.records-card :deep(th.el-table__cell) { background: var(--el-fill-color-lighter); }
.records-card :deep(td.el-table__cell) { padding: 16px 0; }
</style>
