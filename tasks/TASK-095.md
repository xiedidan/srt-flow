# TASK-095: 视频级 Agent 工作流 MVP 联调与验收

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 8小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

对单视频 Agent 工作流 MVP 进行端到端联调。重点验证：视频级会话、故障对话、限制条件、沙箱修复、强制复盘、知识候选、原步骤页面跳转。

## 验收场景

1. 一个视频创建或读取 Agent Session。
2. Workflow Timeline 显示下载、ASR、翻译、TTS、合成等步骤。
3. 人为触发 FFMPEG 或下载类错误。
4. Agent 解释错误并提出修复方案。
5. 用户通过对话添加限制并批准方案。
6. 系统在沙箱中试跑修复。
7. 成功/失败都写入 node_review。
8. knowledge_candidates 进入候选池。
9. 用户可从 Timeline 跳转到原步骤 UI。

## 验收标准

- [ ] MVP 主流程可跑通
- [ ] 失败场景可进入视频 Agent 对话
- [ ] 用户限制能贯穿修复和复盘
- [ ] 强制复盘不可跳过
- [ ] 前端无明显布局重叠或状态错乱
- [ ] 更新相关文档和使用说明

## 相关文件

- `backend/services/agent/*`
- `frontend/src/components/agent/*`
- `docs/17-功能-视频级Agent工作流设计.md`
- `README.md`

## 依赖任务

- TASK-083
- TASK-084
- TASK-085
- TASK-086
- TASK-087
- TASK-088
- TASK-089
- TASK-090
- TASK-091
- TASK-092
- TASK-093
- TASK-094
