<template>
  <el-card v-loading="loading" shadow="never">
    <template #header><div class="settings-toolbar"><strong>{{ tr('evaluationSettings') }}</strong><el-button :loading="loading" @click="load">{{ tr('refresh') }}</el-button></div></template>
    <h3>{{ tr('judgeDefaults') }}</h3>
    <p>{{ tr('judgeDefaultsHelp') }}</p>
    <el-form label-position="top"><JudgeSettings v-model="judge" /></el-form>
    <el-button type="primary" :loading="saving" :disabled="!loaded" class="mt-16" @click="save">{{ tr('save') }}</el-button>
    <el-divider />
    <div class="settings-toolbar"><h3>{{ tr('retrievalSettings') }}</h3><el-button type="primary" plain @click="openConfig">{{ tr('editRetrievalFallback') }}</el-button></div>
    <el-alert :title="tr('retrievalSettingsHelp')" type="info" :closable="false" />
    <el-empty v-if="!retrieval.version_id" :description="tr('published')" />
    <template v-else>
      <p>{{ tr('publishedVersion') }}: {{ retrieval.version_id }}</p>
      <template v-if="retrieval.type === 'SIMPLE'">
        <p>{{ tr('boundKnowledge') }}: {{ retrieval.knowledge_ids?.join(', ') || '—' }}</p>
        <pre>{{ JSON.stringify(retrieval.settings, null, 2) }}</pre>
        <strong>{{ tr('fallbackSettings') }}</strong><pre>{{ JSON.stringify(retrieval.no_references, null, 2) }}</pre>
      </template>
      <template v-else>
        <el-table :data="retrieval.nodes || []">
          <el-table-column type="expand"><template #default="{ row }"><pre v-if="row.branches?.length">{{ JSON.stringify(row.branches, null, 2) }}</pre><pre v-if="row.reply">{{ typeof row.reply === 'string' ? row.reply : JSON.stringify(row.reply, null, 2) }}</pre><span v-if="!row.branches?.length && !row.reply">—</span></template></el-table-column>
          <el-table-column prop="name" :label="tr('diagNode')" min-width="160" />
          <el-table-column prop="type" :label="tr('nodeType')" min-width="180" />
          <el-table-column :label="tr('retrievalParameters')" min-width="260"><template #default="{ row }"><pre v-if="Object.keys(row.settings || {}).length">{{ JSON.stringify(row.settings, null, 2) }}</pre><span v-else>—</span><div v-if="row.knowledge_ids?.length">{{ tr('boundKnowledge') }}: {{ row.knowledge_ids.join(', ') }}</div></template></el-table-column>
          <el-table-column :label="tr('nextNodes')" min-width="180"><template #default="{ row }">{{ nextNodes(row.id) }}</template></el-table-column>
        </el-table>
        <p>{{ tr('fallbackHelp') }}</p>
      </template>
      <el-button @click="openKnowledge">{{ tr('goKnowledge') }}</el-button>
    </template>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getEvaluationSettings, saveEvaluationSettings } from '@/api/application/evaluation'
import { isWorkFlow } from '@/utils/application'
import JudgeSettings, { type JudgeOptions } from './JudgeSettings.vue'
const props = defineProps<{ applicationId: string }>()
const { t } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const loaded = ref(false)
const judge = ref<JudgeOptions>({ max_tokens: 4096, temperature: 0, thinking: 'auto', json_mode: false })
const retrieval = ref<any>({})
const load = async () => {
  loading.value = true
  loaded.value = false
  try {
    const result = await getEvaluationSettings(props.applicationId)
    judge.value = result.data.judge
    retrieval.value = result.data.retrieval
    loaded.value = true
  } finally { loading.value = false }
}
const save = async () => {
  saving.value = true
  try { judge.value = (await saveEvaluationSettings(props.applicationId, judge.value)).data.judge; ElMessage.success(tr('savedSettings')) }
  finally { saving.value = false }
}
const nextNodes = (id: string) => (retrieval.value.edges || []).filter((e: any) => e.source === id).map((e: any) => retrieval.value.nodes.find((n: any) => n.id === e.target)?.name || e.target).join(' / ') || '—'
const openConfig = () => {
  const { from, id, type } = route.params
  window.open(router.resolve(isWorkFlow(String(type)) ? `/application/${from}/${id}/workflow` : `/application/${from}/${id}/${type}/setting`).href, '_blank')
}
const openKnowledge = () => window.open(router.resolve('/knowledge').href, '_blank')
onMounted(load)
</script>
<style scoped>
.settings-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
p { color: var(--el-text-color-regular); line-height: 1.7; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; }
</style>
