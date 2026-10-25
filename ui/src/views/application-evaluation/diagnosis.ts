// Evidence-based attribution shared by offline evaluation results and online samples.
// Each finding names the area to fix (tool / model / retrieval / prompt), the node it came
// from and the raw evidence, so the user knows exactly where to go.
export type DiagnosisArea = 'tool' | 'model' | 'retrieval' | 'prompt' | 'unknown'

export interface DiagnosisFinding {
  area: DiagnosisArea
  key: string
  params: Record<string, string | number>
  nodeId?: string
  nodeName?: string
  nodeType?: string
  evidence?: string
}

export interface DiagnosisInput {
  nodes?: Record<string, any>
  contexts?: any[]
  scores?: Record<string, any>
  error?: string
  feedbackVote?: string
  lowScore?: boolean
  trace?: any
  expectedTools?: string[]
  expectedBranch?: string
  labelIds?: string[]
  labelDocs?: any[]
}

export const AREA_TAG: Record<string, 'danger' | 'warning' | 'primary' | 'info'> = { tool: 'danger', retrieval: 'warning', prompt: 'primary', model: 'info', unknown: 'info' }
export const DIAGNOSIS_AREAS: DiagnosisArea[] = ['tool', 'retrieval', 'prompt', 'model', 'unknown']
const TOOL_TYPES = ['tool-lib-node', 'tool-node', 'tool-workflow-lib-node', 'mcp-node', 'application-node']
const RETRIEVAL_TYPES = ['search-knowledge-node', 'search-document-node', 'reranker-node', 'search_step']
const AI_TYPES = ['ai-chat-node', 'chat_step']
const SLOW_SECONDS = 10
const LOW = 0.6

const areaOfType = (type: string): DiagnosisArea => TOOL_TYPES.includes(type) ? 'tool' : RETRIEVAL_TYPES.includes(type) ? 'retrieval' : 'model'
const percent = (value: number) => `${(value * 100).toFixed(0)}%`
const clip = (value: any, size = 600) => {
  const text = typeof value === 'string' ? value : value == null ? '' : JSON.stringify(value)
  return text.length > size ? `${text.slice(0, size)}…` : text
}
const num = (value: any) => value == null || !Number.isFinite(Number(value)) ? null : Number(value)

export function diagnose(input: DiagnosisInput): DiagnosisFinding[] {
  const nodes = Object.entries(input.nodes && typeof input.nodes === 'object' ? input.nodes : {}).map(([key, detail]: [string, any]) => ({
    id: String(detail?.node_id ?? key), name: String(detail?.name || detail?.step_type || key), type: String(detail?.type || detail?.step_type || ''), detail: detail || {},
  }))
  const scores = input.scores || {}
  const contexts = input.contexts || []
  const findings: DiagnosisFinding[] = []
  const node = (item: typeof nodes[number]) => ({ nodeId: item.id, nodeName: item.name, nodeType: item.type })
  const steps: any[] = Array.isArray(input.trace?.steps) ? input.trace.steps : []
  // Retrieval parameters come from the executed version's node config recorded in the trace.
  const retrievalParams = (nodeId?: string) => {
    const r = steps.find(step => step.node_id === nodeId && step.retrieval)?.retrieval
    return r ? clip({ knowledge_ids: r.knowledge_ids, top_n: r.top_n, similarity: r.similarity, search_mode: r.search_mode, hit_count: r.hit_count, question: r.question }) : undefined
  }

  const failed = nodes.filter(item => item.detail.err_message || (item.detail.status != null && Number(item.detail.status) !== 200))
  for (const item of failed) {
    findings.push({ area: areaOfType(item.type), key: 'diagNodeFailed', params: { node: item.name }, ...node(item), evidence: clip(item.detail.err_message || `status ${item.detail.status}`) })
  }
  if (input.error && !failed.length) findings.push({ area: 'unknown', key: 'diagRunError', params: {}, evidence: clip(input.error) })

  const toolAccuracy = num(scores.tool_call_accuracy)
  const calls: any[] = input.trace?.tool_calls || []
  const callNames = calls.map(call => call.name || call.id)
  if ((toolAccuracy != null && toolAccuracy < LOW) || scores.task_success === 0) {
    const tool = nodes.find(item => TOOL_TYPES.includes(item.type))
    const expected = input.expectedTools ? { expected: input.expectedTools, actual: callNames } : {}
    findings.push({ area: 'tool', key: 'diagToolInaccurate', params: { value: toolAccuracy == null ? '—' : percent(toolAccuracy) }, ...(tool ? node(tool) : {}), evidence: clip({ ...expected, ...(tool ? { params: tool.detail.params ?? tool.detail.tool_params, result: tool.detail.result } : {}) }) })
  } else if (scores.tool_order_correct === 0) {
    const tool = nodes.find(item => TOOL_TYPES.includes(item.type))
    findings.push({ area: 'tool', key: 'diagToolOrder', params: {}, ...(tool ? node(tool) : {}), evidence: clip({ expected: input.expectedTools, actual: callNames }) })
  }

  const wrongBranch = scores.branch_correct === 0
  if (wrongBranch) {
    const branch = steps.find(step => step.branch) || {}
    const taken = (input.trace?.branches || []).map((row: any) => `${row.node_name || row.node_id}: ${row.name ?? row.category ?? row.id ?? '—'}`)
    findings.push({ area: 'prompt', key: 'diagWrongBranch', params: { node: branch.name || '—', expected: input.expectedBranch || '—' }, nodeId: branch.node_id, nodeName: branch.name, nodeType: branch.type, evidence: clip({ expected: input.expectedBranch, actual: taken }) })
  }

  const search = nodes.find(item => RETRIEVAL_TYPES.includes(item.type) && !failed.includes(item))
  const hit = num(scores.hit_rate ?? scores.retrieval_hit)
  const recall = num(scores.context_recall)
  const retrievalStart = findings.length
  const staleLabels = (input.labelDocs || []).filter(doc => doc?.status && doc.status !== 'ok')
  const hitDocs = [...new Map(contexts.map(row => [String(row.document_id), row.document_name || row.title || row.document_id])).entries()]
  if (staleLabels.length && hit === 0) {
    findings.push({ area: 'retrieval', key: 'diagStaleLabel', params: { count: staleLabels.length }, evidence: clip(staleLabels.map(doc => `${doc.id} · ${doc.status === 'missing' ? 'missing' : `outside ${doc.name}`}`).join('\n')) })
  } else if (search && !contexts.length) {
    findings.push({ area: 'retrieval', key: 'diagNoContext', params: { node: search.name }, ...node(search), evidence: retrievalParams(search.id) || clip(search.detail.question) })
  } else if (!wrongBranch && !search && !contexts.length && nodes.some(item => item.type === 'intent-node')) {
    const intent = nodes.find(item => item.type === 'intent-node')!
    findings.push({ area: 'retrieval', key: 'diagSearchSkipped', params: { node: intent.name }, ...node(intent), evidence: clip({ category: intent.detail.category, branch: intent.detail.branch_id }) })
  } else if (hit === 0) {
    const labeled = input.labelDocs?.length ? input.labelDocs.map(doc => `${doc.name || ''} ${doc.id}`.trim()) : input.labelIds || []
    findings.push({ area: 'retrieval', key: 'diagMissedDocs', params: { count: contexts.length }, ...(search ? node(search) : {}), evidence: [clip({ labeled, retrieved: hitDocs.slice(0, 5).map(([id, name]) => `${name} ${id}`) }), retrievalParams(search?.id)].filter(Boolean).join('\n') })
  } else if (recall != null && recall < 0.5) {
    findings.push({ area: 'retrieval', key: 'diagLowRecall', params: { value: percent(recall) }, ...(search ? node(search) : {}), evidence: retrievalParams(search?.id) })
  }
  const retrievalOk = findings.length === retrievalStart && !wrongBranch

  const ai = nodes.find(item => AI_TYPES.includes(item.type))
  const prompt = ai ? { ...node(ai), evidence: clip(ai.detail.system || ai.detail.question) } : {}
  const faithfulness = num(scores.faithfulness ?? scores.faithfulness_signal)
  const correctness = num(scores.answer_correctness)
  if (retrievalOk && !failed.length && faithfulness != null && faithfulness < LOW) {
    findings.push({ area: 'prompt', key: 'diagUnfaithful', params: { value: percent(faithfulness) }, ...prompt })
  } else if (retrievalOk && !failed.length && correctness != null && correctness < LOW) {
    findings.push({ area: 'prompt', key: 'diagWrongAnswer', params: { value: percent(correctness) }, ...prompt })
  }

  for (const item of nodes.filter(row => AI_TYPES.includes(row.type) && !failed.includes(row))) {
    const seconds = num(item.detail.run_time)
    if (seconds != null && seconds > SLOW_SECONDS) findings.push({ area: 'model', key: 'diagSlow', params: { node: item.name, seconds: seconds.toFixed(1) }, ...node(item) })
  }

  if (!findings.length && (input.feedbackVote === '1' || input.lowScore)) findings.push({ area: 'unknown', key: 'diagNoEvidence', params: {} })
  return findings
}

export const diagnoseResult = (row: any) => diagnose({
  nodes: row.node_details, contexts: row.contexts, scores: { ...(row.scores || {}) }, error: row.error,
  lowScore: row.total_score != null && Number(row.total_score) < LOW,
  trace: row.trace, expectedTools: row.expected_tools, expectedBranch: row.expected_branch,
  labelIds: row.relevant_doc_ids, labelDocs: row.label_docs,
})

export type RetrievalZeroCause = 'stale' | 'skipped' | 'empty' | 'mismatch'
// Why a labeled case scored 0 on retrieval; each cause has a different fix.
export const retrievalZeroCause = (row: any): RetrievalZeroCause | null => {
  if (!row?.relevant_doc_ids?.length || num(row.scores?.hit_rate) !== 0) return null
  if ((row.label_docs || []).some((doc: any) => doc?.status && doc.status !== 'ok')) return 'stale'
  if (row.contexts?.length) return 'mismatch'
  const ran = Object.values(row.node_details || {}).some((detail: any) => RETRIEVAL_TYPES.includes(String(detail?.type || detail?.step_type || '')))
  return ran ? 'empty' : 'skipped'
}

export const diagnoseSample = (sample: any) => diagnose({
  nodes: sample.event?.node_details,
  contexts: sample.event?.final_contexts?.length ? sample.event.final_contexts : sample.event?.retrieval_candidates,
  scores: { ...(sample.result?.scores || {}), tool_call_accuracy: sample.event?.tool_call_accuracy ?? sample.result?.scores?.tool_call_accuracy, task_success: sample.event?.task_success ?? sample.result?.scores?.task_success },
  error: sample.event?.execution_error,
  feedbackVote: sample.event?.feedback?.vote,
  trace: sample.event?.trace,
  lowScore: sample.annotation?.answer_score != null && Number(sample.annotation.answer_score) < LOW,
})
