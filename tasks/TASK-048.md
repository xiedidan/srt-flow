---
id: TASK-048
title: 修复翻译字幕空行过多问题
status: Review
assignee: Kiro 
priority: High
source: 问题日记
---

# 任务描述
翻译后的字幕存在较多的空行。如果一个批次中空行太多，应该重试翻译该批次。需要在字幕翻译配置中增加一个翻译空行阈值配置项。

# 验收标准 (Acceptance Criteria)
- [x] 在字幕翻译配置中增加"翻译空行阈值"配置项
- [x] 翻译服务检测批次中的空行数量
- [x] 当空行数量超过阈值时，自动重试该批次翻译
- [x] 前端配置界面支持设置空行阈值

# 上下文 (Context)
- 相关功能：字幕翻译
- 参考 `docs/10-服务-翻译服务设计.md`
- 参考 `backend/services/translator.py`
