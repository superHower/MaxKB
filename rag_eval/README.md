# MaxKB 自动化 RAG 评测

独立 CLI，不依赖 Django 启动，结果写入 SQLite；可由 CI、cron、Windows 任务计划程序触发。
使用 Python 3.11。默认数据库和报告目录在已忽略的 data/ 下。

## 安装与运行

    uv venv --python 3.11 .venv-rag-eval
    uv pip install --python .venv-rag-eval/Scripts/python.exe -r rag_eval/requirements.txt
    python -m rag_eval import regression rag_eval/examples/qa.json
    python -m rag_eval run regression --config rag_eval/examples/config.json --fail-on-regression

上面的 python 应替换为评测虚拟环境解释器；Linux 为 .venv-rag-eval/bin/python。
配置 MAXKB_API_KEY、JUDGE_API_KEY、EMBEDDING_API_KEY 环境变量。只使用应用 API 密钥，
base_url 为实际聊天 API 前缀（默认 http://127.0.0.1:8080/chat/api）。
OpenAI、DeepSeek、Qwen 使用其 OpenAI 兼容 base_url 和模型名称。
DeepSeek 没有 Embedding API，Answer Relevancy 的 Embedding 可独立配置为 Qwen/OpenAI。
评分依赖单独安装，不修改 MaxKB 运行时依赖。

请修改示例配置的 snapshot，与实际发布的 MaxKB 工作流保持一致。
快照来源标记为 operator_supplied，工具不声称已从线上自动验证参数。
记录 Embedding、LLM、Top-K、阈值、Rerank、知识库/模型/RAG 配置版本，以及评分依赖版本。
不要把密钥放进配置、请求 body 或快照；凭据只能通过 api_key_env 指定环境变量。
正式上线前请在目标服务验证业务评分模型支持的 JSON 输出和 RAGAS 提示词。

## 启动项目
在项目根目录 `D:\MyWork\project-agent\MaxKB` 下启动：

```
# 后端 Web 服务
python main.py dev
```

另开两个终端分别启动：

```
# Celery 异步任务
python main.py dev celery
```

```
# 本地 embedding 模型服务
python main.py dev local_model
```

前端再开一个终端：

```
cd ui
npm run dev
```

访问：

- 管理后台：http://localhost:8080/admin
- 前端开发页通常由 Vite 输出地址，一般是：http://localhost:5173

首次运行数据库可先执行：

```
python main.py upgrade_db
```

## 测试集

JSON 顶层为数组；必需 question、ground_truth，可选 id、relevant_doc_ids、
category、knowledge_ids、document_tags。CSV 数组字段使用 JSON 数组字符串。
默认 case ID 是问题的 SHA256 截断；重复问题必须明确提供不同 ID。
导入完整内容生成 SHA256 版本，重复导入幂等，不覆盖历史版本。

    python -m rag_eval --db data/rag_eval.sqlite3 import regression dataset.csv
    python -m rag_eval run regression --version <SHA256> --config config.json

category 可用 frequent、boundary、multi_hop、negative、terminology。
示例包含全部五类，但只是格式和分类示范；应替换为业务真实问题、标准答案和文档 ID。
缺失或空 relevant_doc_ids 表示未标注，检索指标输出 null。
显式空检索结果加非空相关标注表示零命中，与缺少检索日志区分。

## 检索上下文：方案 a，工作流日志

在工作流最终 Rerank/筛选/截断之后、生成节点之前加入日志工具节点，
调用 rag_eval.workflow_logger.log_final_context(db_path, chat_id, chat_record_id, paragraphs)。
Python 路径需包含仓库根目录，工具需有访问评测 SQLite 文件的权限。
可在获得完整日志后通过 CLI 导入：

    python -m rag_eval --db data/rag_eval.sqlite3 log-context final_context.json

日志对象：

    {
      "chat_id": "<当前会话ID>",
      "chat_record_id": "<当前回答记录ID>",
      "contexts": [
        {
          "paragraph_id": "<分段ID>",
          "document_id": "<文档ID>",
          "knowledge_id": "<知识库ID>",
          "content": "<实际传入生成模型的文本>",
          "score": 0.85,
          "document_tags": ["产品手册"]
        }
      ]
    }

contexts 必须按实际进入生成提示词的顺序记录；空列表也必须记录。
从 MaxKB 工作流参数取当前 chat_id/chat_record_id，不能按 question 关联并发请求。
日志节点必须在最终 SSE 帧之前完成，异步写入默认等待 5 秒可配置。
容器部署时将评测数据库挂载到日志工具可访问的本地卷；SQLite WAL 不适合网络文件系统。
工具沙箱权限需按现有部署方式配置。此模块提供日志适配器，未自动修改用户工作流。
若日志在另一主机，应由受控日志服务写入本地 SQLite；不要直接共享 WAL 文件。
可由受控服务接收日志后调用 Store.log_context；本项目不新增公开日志 API。

retrieval_source=log 从外部表读；response 读取已有定制响应的 retrieval_context；
none 仅评测生成（Faithfulness 无上下文不可计算）。
本次没有修改 MaxKB API 或重新执行向量检索。
聊天记录展示字段可能受 show_knowledge 控制，且可能包含 Rerank 前候选，
不直接把它当生成上下文。
SQLite 表 retrieval_events 用 (chat_id, chat_record_id) 唯一关联，保留分段 ID、内容、分数、元数据。

## 指标和总分

- Context Precision：按文档 ID 去重（保留首次排名），相关位置的 Precision 求平均；
  分母是已召回相关文档数量。这是排序敏感 AP 风格指标，另输出 precision_at_k。
- Context Recall：召回的唯一相关文档数量 / 标注相关文档数量。
- Hit Rate：是否至少召回一个相关文档；总体取平均。
- MRR：首次相关文档排名倒数，无命中为零。
- Faithfulness：RAGAS Faithfulness；缺少/空生成上下文为 null。
- Answer Relevancy：RAGAS ResponseRelevancy，Judge LLM 与独立 Embedding。
- Completeness：RAGAS AspectCritic，判断是否完整覆盖标准答案关键事实，输出 0/1；
  配置 completeness_strictness 控制多数投票次数（建议正奇数）。
- Keypoint Coverage：LLM rubric 给出标准答案关键点连续覆盖率 [0,1] 和理由。
- 自定义评分：judge.dimensions 为名称到评分标准的映射，返回 [0,1] 和理由。

所有得分范围为 [0,1]。weights 指定总分维度和正权重，必需维度缺失时总分为 null，
不通过删除失败维度抬高总分。报告包含每个指标有效样本数/总样本数。
知识库/文档标签优先采用测试集标注，未标注时从上下文推导；
无召回样本要按目标知识库分组时必须在测试集中标注 knowledge_ids，避免遗漏。
Context Precision/Recall 是基于文档标注的指标，不能代替分段级人工相关性判断。
LLM Judge 有随机误差，建议固定 Judge/Embedding 版本及 rubric，并人工抽查下降样本。

## 回归、报告和历史查询

默认基线为同测试集版本最后一次 completed 运行。
跨知识库、模型或 RAG 配置版本，通过修改 snapshot 并指定 --baseline <run_id> 对比。
报告记录配置差异，只比较相同 case ID、问题、标准答案、相关文档标注的样本；
逐维度仅比较两边都有有效得分的样本，输出匹配数量。
数据集变化时同时列出新增/删除样本。

    python -m rag_eval run regression --config config.json --baseline <run_id> --fail-on-regression
    python -m rag_eval export <run_id> --output data/export

每次输出 <run_id>.md 与 <run_id>.json，逐条结果包括回答、耗时（包含重试等待）、
timestamp、attempts、token_usage（API 返回时）、上下文、逐项分数、总分、Judge 理由和错误。
降分阈值为绝对分差，默认 0.05；所有评分维度下降都会列出问题、前后回答和具体分差。
退出码：0 成功，2 有调用/评分失败或所需总分缺失，3 --fail-on-regression 检测到回归。
数据库保存 datasets、runs、results、retrieval_events，历史运行可重新导出。
趋势查询示例（SQLite JSON 函数）：

    SELECT created_at,
           json_extract(report, '$.summary.total_score.mean') AS score,
           json_extract(config, '$.snapshot.model_version') AS model_version
    FROM runs WHERE status = 'completed' ORDER BY created_at;

## 每周定时触发

Linux cron，周一 09:00（需配置该用户的环境变量/安全凭据来源）：

    0 9 * * 1 cd /opt/MaxKB && .venv-rag-eval/bin/python -m rag_eval run regression --config /opt/MaxKB/eval-config.json --fail-on-regression >> data/rag_eval-weekly.log 2>&1

Windows 任务计划程序：每周一 09:00，程序设为虚拟环境 python.exe，
参数 -m rag_eval run regression --config <配置绝对路径> --fail-on-regression，
起始目录设为仓库路径。用任务运行账户的环境变量提供密钥。
scheduler/CI 应防止同一评测重叠执行，并监控非零退出码。

## 验证

    python -m unittest discover -s rag_eval/tests -v

离线测试覆盖导入、版本、SSE 结束/中断、重试、排名去重、持久化、分组、基线和导出。
在线端到端评测需要实际 MaxKB 应用、日志节点、业务测试集和 Judge/Embedding 凭据。
