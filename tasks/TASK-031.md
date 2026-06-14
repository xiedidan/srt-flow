---
id: TASK-031
title: 实现后端 API 接口层
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现后端 RESTful API 接口，包括任务管理、视频管理、配置管理、WebSocket 状态推送。

# 验收标准 (Acceptance Criteria)
- [x] 任务 API（提交/查询/操作）- tasks.py: POST/GET/action endpoints
- [x] 视频 API（列表/详情/更新/文件内容）- videos.py: CRUD + file content
- [x] 配置 API（获取/更新）- config.py: 已实现（TASK-018）
- [x] WebSocket 状态推送 /ws/status - websocket.py: ConnectionManager + broadcast
- [x] API 文档自动生成（Swagger）- FastAPI 自动生成 /docs

# 上下文 (Context)
- 参考 `API文档.md`
- 目录：`backend/app/routers/`
