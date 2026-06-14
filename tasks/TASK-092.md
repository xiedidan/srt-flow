# TASK-092: TaskAgentMiddleware 接入任务执行生命周期

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 10小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

在现有任务执行生命周期中接入 TaskAgentMiddleware。每个任务节点执行前后都经过任务 Agent：before_execute、after_execute、on_error。

## 需求

1. 定义 TaskAgentMiddleware 接口。
2. 支持按 TaskType 选择对应任务 Agent。
3. before_execute：检查参数、工具健康、限制条件、沙箱准备。
4. after_execute：校验产物、写复盘材料、提交沙箱产物。
5. on_error：分类错误、生成修复方案、判断是否需要用户确认。
6. 不破坏独立任务执行。

## 验收标准

- [ ] 可对指定 TaskType 启用/禁用 AgentMiddleware
- [ ] 未启用 Agent 的任务保持原逻辑
- [ ] 失败任务可进入 waiting_user / repair_suggested
- [ ] 节点执行后强制写入复盘
- [ ] WebSocket 推送 Agent 状态

## 相关文件

- `backend/workers/worker.py`
- `backend/app/main.py`
- `backend/services/agent/middleware.py`（建议新增）
- `backend/services/agent/base.py`（建议新增）

## 依赖任务

- TASK-085
- TASK-086
- TASK-091

