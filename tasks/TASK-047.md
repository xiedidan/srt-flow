---
id: TASK-047
title: 修复仪表盘视频总数显示为0的问题
status: Review
assignee: Kiro 
priority: High
source: 问题日记
---

# 任务描述
系统中有已经下载的视频，但仪表盘的视频总数显示为0。需要排查并修复仪表盘统计数据的获取逻辑。

# 验收标准 (Acceptance Criteria)
- [x] 仪表盘能正确显示已下载视频的总数
- [x] 统计数据与实际视频数量一致
- [x] 相关API接口返回正确的统计数据

# 上下文 (Context)
- 相关功能：仪表盘
- 需要检查前端仪表盘组件和后端统计API
