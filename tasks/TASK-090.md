# TASK-090: Agent 知识库 Schema、候选提升与版本管理

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 10小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

为每类任务 Agent 建立独立知识库，包含成功经验、失败教训、允许行为、限制条件、工具状态，并用 JSON Schema 约束。支持用户查看、编辑、禁用、回滚和候选提升。

## 需求

1. 定义 Agent 知识目录结构。
2. 为 FfmpegAgent、DownloadAgent、TtsAgent 建立首批 Schema。
3. 实现 AgentKnowledgeStore。
4. 从 node_review.knowledge_candidates 创建 candidate。
5. 用户批准后写入对应 Agent 的 current/*.json。
6. 每次修改创建 versions/<timestamp>/ 快照和 changelog。

## 验收标准

- [ ] 每类 Agent 有独立知识目录
- [ ] 成功经验、失败教训、允许行为、限制条件、工具状态有 Schema
- [ ] candidate 不会自动变成 active
- [ ] 用户可以批准/编辑/禁用候选
- [ ] 支持版本快照和回滚
- [ ] 运行中的视频 Workflow 使用启动时知识快照

## 相关文件

- `backend/services/agent/knowledge.py`（建议新增）
- `data/agent_knowledge/`（运行时目录）
- `frontend/src/components/agent/KnowledgeEditor.vue`（建议新增）

## 依赖任务

- TASK-085

