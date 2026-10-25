<template>
  <div class="sample-evidence">
        <dl class="eval-meta eval-section">
          <div><dt>{{ tr('traceId') }}</dt><dd class="eval-id">{{ sample.event.chat_record_id }}</dd></div>
          <div><dt>{{ tr('applicationVersion') }}</dt><dd class="eval-tags">
            <span class="eval-id">{{ sample.event.application_version || '—' }}</span>
            <el-tag v-if="sample.event.application_version" size="small" :type="sample.event.version_inferred ? 'warning' : 'info'">
              {{ tr(sample.event.version_inferred ? 'versionInferred' : 'versionExact') }}
            </el-tag>
          </dd></div>
        </dl>
        <section class="eval-section">
        <el-tabs v-model="activeEvidence" class="eval-tabs">
          <el-tab-pane :label="tr('retrievedEvidence')" name="retrieval">
            <el-empty v-if="!sample.event.retrieval_candidates?.length" :description="tr('noEvidence')" />
            <div v-for="(context, index) in sample.event.retrieval_candidates || []" :key="context.id || index" class="context-evidence">
              <div class="eval-section-title"><span class="evidence-index">{{ index + 1 }}</span><span>{{ context.document_name || context.document_id || context.id || '—' }}</span></div>
              <p class="eval-copy">{{ context.content || '—' }}</p>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="tr('citationEvidence')" name="citations">
            <el-text v-if="!sample.event.citation_ids_available" type="info">{{ tr('citationUnavailable') }}</el-text>
            <p v-else class="eval-copy eval-id">{{ sample.event.citation_ids?.join(', ') || '—' }}</p>
          </el-tab-pane>
          <el-tab-pane :label="tr('nodeEvidence')" name="nodes">
            <el-alert v-if="sample.event.node_evidence_source === 'chat_record'" :title="tr('historicalNodeEvidence')" type="info" :closable="false" />
            <pre v-if="Object.keys(sample.event.node_details || {}).length" class="eval-code">{{ JSON.stringify(sample.event.node_details, null, 2) }}</pre>
            <el-empty v-else :description="tr('noEvidence')" />
          </el-tab-pane>
        </el-tabs>
        </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

defineProps<{ sample: any }>()
const { t } = useI18n()
const tr = (key: string) => t(`views.applicationEvaluation.ux.${key}`)
const activeEvidence = ref('retrieval')
</script>

<style scoped>
.context-evidence { padding: 16px; margin-bottom: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.context-evidence:last-child { margin-bottom: 0; }
.context-evidence .eval-section-title { justify-content: flex-start; overflow-wrap: anywhere; }
.evidence-index { display: inline-flex; flex: 0 0 24px; align-items: center; justify-content: center; height: 24px; border-radius: 4px; color: var(--el-color-primary); background: var(--el-color-primary-light-9); font-size: 12px; }
</style>
