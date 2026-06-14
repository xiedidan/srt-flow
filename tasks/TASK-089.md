# TASK-089: 限制条件输入、预设 Chips 与复盘继承

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 8小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

实现用户限制条件的自由表达、预设框架和复盘继承展示。用户可以随意说限制，也可以点击常用 chips；系统应展示当前视频已生效和从复盘继承的限制，避免用户反复说明。

## 需求

1. 前端支持自由文本限制输入。
2. 前端提供常用限制 chips：不升级、不覆盖、不使用付费 API、优先稳定、最多重试 N 次等。
3. 后端保存限制作用域：当前动作、当前节点、当前视频、Agent 默认限制候选。
4. 从节点复盘中读取 review_inherited 限制，并在后续节点展示。
5. Agent 回复中必须回显已解析限制，供用户确认。

## 验收标准

- [ ] 用户自然语言限制可保存并展示为结构化 chips
- [ ] 预设 chips 可一键添加/移除
- [ ] 已生效限制显示在 Evidence Panel
- [ ] 从复盘继承的限制显示来源节点
- [ ] 限制写入 node_review.user_constraints

## 相关文件

- `frontend/src/components/agent/AgentChat.vue`
- `frontend/src/components/agent/EvidencePanel.vue`
- `backend/app/routers/agent_sessions.py`
- `backend/services/agent/review.py`

## 依赖任务

- TASK-085
- TASK-087

