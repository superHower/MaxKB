import { del, get, post, postUpload, put } from '@/request/index'
import type { Ref } from 'vue'
import type { Result } from '@/request/Result'
import useStore from '@/stores'

const prefix = (applicationId: string) => {
  const { user } = useStore()
  return `/workspace/${user.getWorkspaceId()}/application/${applicationId}/evaluation`
}
export const getEvaluationDatasets = (id: string, loading?: Ref<boolean>): Promise<Result<any[]>> =>
  get(`${prefix(id)}/datasets`, {}, loading)
export const getEvaluationDataset = (id: string, datasetId: string, loading?: Ref<boolean>): Promise<Result<any>> =>
  get(`${prefix(id)}/datasets/${datasetId}`, {}, loading)
export const updateEvaluationDataset = (id: string, datasetId: string, name: string, file?: File, loading?: Ref<boolean>): Promise<Result<any>> => {
  const form = new FormData()
  form.append('name', name)
  if (file) form.append('file', file)
  return put(`${prefix(id)}/datasets/${datasetId}`, form, undefined, loading)
}
export const deleteEvaluationDataset = (id: string, datasetId: string, loading?: Ref<boolean>): Promise<Result<any>> =>
  del(`${prefix(id)}/datasets/${datasetId}`, {}, undefined, loading)
export const uploadEvaluationDataset = (
  id: string,
  name: string,
  file: File,
  loading?: Ref<boolean>,
): Promise<Result<any>> => {
  const form = new FormData()
  form.append('name', name)
  form.append('file', file)
  return postUpload(`${prefix(id)}/datasets`, form, undefined, undefined, loading).request
}
export const getEvaluationRuns = (id: string, loading?: Ref<boolean>): Promise<Result<any[]>> =>
  get(`${prefix(id)}/runs`, {}, loading)
export const startEvaluation = (
  id: string,
  data: any,
  loading?: Ref<boolean>,
): Promise<Result<any>> => post(`${prefix(id)}/runs`, data, undefined, loading)
export const getEvaluationRun = (
  id: string,
  runId: string,
  loading?: Ref<boolean>,
): Promise<Result<any>> => get(`${prefix(id)}/runs/${runId}`, {}, loading)
export const getEvaluationJudgePrompt = (id: string): Promise<Result<{ default: string; max_length: number }>> =>
  get(`${prefix(id)}/runs/judge-prompt`)
export const getEvaluationSettings = (id: string): Promise<Result<any>> => get(`${prefix(id)}/settings`)
export const saveEvaluationSettings = (id: string, judge: any): Promise<Result<any>> =>
  put(`${prefix(id)}/settings`, { judge })
export const replayEvaluationRun = (id: string, runId: string, loading?: Ref<boolean>): Promise<Result<any>> =>
  post(`${prefix(id)}/runs/${runId}/replay`, {}, undefined, loading)
export const downloadEvaluationReport = (id: string, runId: string, format: 'json' | 'md') =>
  fetch(`${window.MaxKB?.prefix || '/admin'}/api${prefix(id)}/runs/${runId}?format=${format}`, {
    headers: { Authorization: `Bearer ${useStore().login.getToken()}` },
  })

export const getEvaluationEvents = (id: string, params?: any, loading?: Ref<boolean>) =>
  get(`${prefix(id)}/events`, params, loading)
export const getEvaluationMetrics = (id: string, params?: any, loading?: Ref<boolean>) =>
  get(`${prefix(id)}/metrics`, params, loading)
export const getEvaluationExperiments = (id: string, loading?: Ref<boolean>) =>
  get(`${prefix(id)}/experiments`, {}, loading)
export const createEvaluationExperiment = (id: string, data: any, loading?: Ref<boolean>) =>
  post(`${prefix(id)}/experiments`, data, undefined, loading)
export const actionEvaluationExperiment = (id: string, experimentId: string, action: 'start' | 'stop', loading?: Ref<boolean>) =>
  post(`${prefix(id)}/experiments/${experimentId}/action`, { action }, undefined, loading)
export const getEvaluationAssignment = (id: string, experimentId: string, subjectId: string, loading?: Ref<boolean>) =>
  get(`${prefix(id)}/experiments/${experimentId}/assignment`, { subject_id: subjectId }, loading)
export const getEvaluationSamples = (id: string, params?: any, loading?: Ref<boolean>) =>
  get(`${prefix(id)}/samples`, params, loading)
export const getEvaluationSample = (id: string, sampleId: string, loading?: Ref<boolean>): Promise<Result<any>> =>
  get(`${prefix(id)}/samples/${sampleId}`, {}, loading)
export const sampleEvaluationEvents = (id: string, data: any, loading?: Ref<boolean>) =>
  post(`${prefix(id)}/samples`, data, undefined, loading)
export const annotateEvaluationSample = (id: string, sampleId: string, data: any, loading?: Ref<boolean>) =>
  post(`${prefix(id)}/samples/${sampleId}/annotation`, data, undefined, loading)
export const evaluateEvaluationSample = (id: string, sampleId: string, loading?: Ref<boolean>) =>
  post(`${prefix(id)}/samples/${sampleId}/evaluate`, {}, undefined, loading)
export const getEvaluationBadcases = (id: string, params?: any, loading?: Ref<boolean>) =>
  get(`${prefix(id)}/badcases`, params, loading)
export const generateEvaluationBadcases = (id: string, limit = 100, loading?: Ref<boolean>) =>
  post(`${prefix(id)}/badcases`, { limit }, undefined, loading)
export const updateEvaluationBadcase = (id: string, badcaseId: string, data: any, loading?: Ref<boolean>) =>
  put(`${prefix(id)}/badcases/${badcaseId}`, data, undefined, loading)

export const getImprovementCandidates = (id: string, params?: any) => get(`${prefix(id)}/candidates`, params)
export const getImprovementCandidate = (id: string, candidateId: string) => get(`${prefix(id)}/candidates/${candidateId}`)
export const getCandidateOptions = (id: string) => get(`${prefix(id)}/candidates/options`)
export const saveImprovementCandidate = (id: string, data: any, candidateId?: string) => candidateId
  ? put(`${prefix(id)}/candidates/${candidateId}`, data)
  : post(`${prefix(id)}/candidates`, data)
export const actionImprovementCandidate = (id: string, candidateId: string, data: any) =>
  post(`${prefix(id)}/candidates/${candidateId}/action`, data)

export const getEvaluationReleases = (id: string, loading?: Ref<boolean>) =>
  get(`${prefix(id)}/releases`, {}, loading)
export const actionEvaluationRelease = (id: string, data: any, loading?: Ref<boolean>) =>
  post(`${prefix(id)}/releases`, data, undefined, loading)
