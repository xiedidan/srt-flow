# TASK-087: 前端 VideoAgentDrawer 视频级对话框

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 10小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

在不大改原有界面的前提下，为每个视频增加 Agent 对话抽屉。抽屉采用三栏布局：Workflow Timeline、Chat、Evidence & Params。

## 需求

1. 新增 `VideoAgentDrawer.vue`。
2. 左侧显示当前视频 Workflow Timeline。
3. 中间显示 Agent 对话、用户消息、修复方案、批准动作。
4. 右侧显示参数摘要、已生效限制、复盘继承限制、日志/Evidence。
5. 支持从视频列表卡片、视频详情、任务详情打开。
6. 保持现有视频管理和任务页面交互不被破坏。

## 验收标准

- [ ] 视频卡片或详情页可打开 Agent Drawer
- [ ] Drawer 按 video_id 加载正确 Session
- [ ] Timeline、Chat、Evidence 三栏可正常展示
- [ ] 支持发送用户消息
- [ ] 支持批准/拒绝 pending action
- [ ] 移动端或窄屏下布局不重叠

## 相关文件

- `frontend/src/components/agent/VideoAgentDrawer.vue`
- `frontend/src/components/agent/WorkflowTimeline.vue`
- `frontend/src/components/agent/AgentChat.vue`
- `frontend/src/components/agent/EvidencePanel.vue`
- `frontend/src/api/agentSessions.js`
- `frontend/src/stores/agentSessions.js`

## 依赖任务

- TASK-086

