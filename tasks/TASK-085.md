# TASK-085: 强制复盘 Schema 与 ReviewEnforcer

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 8小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

实现节点复盘与视频最终复盘的固定 Schema，并在编排层强制执行。没有通过复盘 Schema 校验的节点，不能进入最终 completed / failed 状态。

## 需求

1. 定义 `node_review.v1` 和 `video_review.v1` JSON Schema。
2. 新增 node_reviews 和 video_reviews 存储。
3. 实现 ReviewEnforcer：节点执行前、成功后、失败后、用户介入后都必须写入结构化复盘。
4. 复盘中记录 user_constraints，包含 source、scope、applies_to、created_in_node_id。
5. 复盘中记录 knowledge_candidates，但不直接写入跨视频知识库。

## 验收标准

- [ ] 节点复盘 Schema 文件存在并通过校验器测试
- [ ] 视频最终复盘能引用所有节点复盘
- [ ] 缺少复盘时节点不能最终完成
- [ ] 用户介入时必须记录限制和批准/拒绝动作
- [ ] 复盘可按 video_id / workflow_id 查询

## 相关文件

- `backend/services/agent/review.py`（建议新增）
- `backend/core/models.py`
- `backend/core/repositories.py`
- `docs/17-功能-视频级Agent工作流设计.md`

## 依赖任务

- TASK-084

