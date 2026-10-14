# 智能体评测数据模型与日志方案

## 现有数据复用

- `ChatRecord`：问题、答案、会话和详情。
- `ChatRecord.details`：检索节点和段落信息。
- 投票数据：点赞、点踩及原因。
- 应用版本和知识库配置：用于配置快照。
- `apps/evaluation`：保留历史 Dataset/Run，后续扩展为统一评测运行记录。

## 评测事件

新增统一评测事件（可先落地为 JSONField，稳定后拆表）：

```text
event_id
workspace_id
application_id
chat_id
chat_record_id
question
answer
retrieval_candidates[]
final_contexts[]
citation_ids[]
application_version
knowledge_versions[]
model_snapshot{}
prompt_snapshot{}
retrieval_snapshot{}
latency_ms
token_usage{}
estimated_cost
feedback{}
human_handoff
created_at
```

`retrieval_candidates` 是检索阶段候选结果；`final_contexts` 是最终传给生成模型的内容，二者必须区分。

## 真实日志样本

样本状态：

```text
sampled -> pending_review -> reviewed -> evaluated -> archived
```

样本至少包含：

```text
sample_id
source_event_id
question
answer
contexts
feedback
sampling_reason
review_status
```

采样原因包括：高频、点踩、追问、无命中、转人工、超时、高成本、随机抽样。

## 人工标注

```text
answer_correct: yes/no/unknown
answer_score: 0..1
citation_relevant: yes/no/unknown
should_answer: yes/no/unknown
no_answer_handling: correct/incorrect/not_applicable
faithful: yes/no/unknown
needs_handoff: yes/no/unknown
badcase_category: data/retrieval/generation/prompt/model/permission/user/other
gold_answer
gold_context_ids[]
reviewer_id
review_note
reviewed_at
```

## 版本快照

每次离线或灰度运行必须保存：

- 应用发布版本；
- LLM、Embedding、Reranker 模型及版本；
- 系统提示词和节点提示词哈希；
- 分段策略和知识库版本；
- Top K、相似度阈值、检索模式；
- Judge 模型和评估器版本。

## 数据保留和隐私

- 评测数据引用原始记录 ID，避免重复保存不必要的会话数据。
- 导出时脱敏用户标识和密钥。
- 删除或匿名化原始聊天记录时，评测样本按策略同步处理。
