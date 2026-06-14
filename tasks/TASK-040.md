---
id: TASK-040
title: 翻译提示词定制功能
status: Review
assignee: Kiro
priority: High
---

# 任务描述

实现翻译任务的用户提示词定制功能，允许用户在新建翻译任务时调整提示词，以提供背景信息。

# 需求来源

docs/需求日记.md - 翻译提示词定制

# 功能要点

1. 新建翻译任务时，允许用户输入任务背景/上下文信息
2. 任务背景通过 `{context}` 占位符添加到用户提示词的开始
3. 调整后的用户提示词需要记录在任务详情中以便查阅

# 验收标准 (Acceptance Criteria)

- [x] 翻译任务创建表单增加"任务背景"输入字段
- [x] 后端支持接收并存储任务背景信息
- [x] 翻译服务在构建提示词时，将背景信息通过 `{context}` 占位符注入
- [x] 任务详情页面可以查看完整的用户提示词
- [x] 更新 API 文档

# 上下文 (Context)

- 参考 `docs/10-服务-翻译服务设计.md` 了解翻译服务实现
- 参考 `frontend/src/components/tasks/TranslateTaskModal.vue` 了解翻译任务创建界面
- 参考 `backend/services/translator.py` 了解翻译服务后端实现
