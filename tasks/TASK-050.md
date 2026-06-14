---
id: TASK-050
title: 实现视频合成双字幕样式配置
status: Review
assignee: Kiro
priority: High
source: 问题日记
---

# 任务描述
系统配置-视频合成界面，需要支持原始字幕样式配置、翻译字幕样式配置。

默认样式：
- 原始字幕：屏幕下方，白色半透明，字号较小
- 翻译字幕：原始字幕上方，黄色半透明，字号较大

# 验收标准 (Acceptance Criteria)
- [x] 后端支持原始字幕样式配置（位置、颜色、透明度、字号）
- [x] 后端支持翻译字幕样式配置（位置、颜色、透明度、字号）
- [x] 前端配置界面支持分别设置两种字幕样式
- [x] 视频合成服务正确应用双字幕样式
- [x] 默认样式符合需求描述

# 上下文 (Context)
- 相关功能：系统配置-视频合成
- 参考 `docs/12-服务-视频合成服务设计.md`
- 参考 `backend/services/synthesizer.py`

# 实现方案

## 后端修改
1. `backend/core/config.py` - 扩展 `SynthesisConfig` 模型：
   - 新增原始字幕样式配置（original_subtitle_*）
   - 新增翻译字幕样式配置（translated_subtitle_*）
   - 保留旧字段用于向后兼容

2. `backend/app/main.py` - 合成任务预处理：
   - 从数据库配置读取双字幕样式
   - 构建 primary_subtitle_style（翻译字幕）
   - 构建 secondary_subtitle_style（原始字幕）

## 前端修改
1. `frontend/src/views/SettingsView.vue` - 更新 synthesis schema：
   - 音频设置分组
   - 原始字幕样式分组
   - 翻译字幕样式分组

## 文档更新
1. `docs/01-核心-配置管理器设计.md` - 更新视频合成配置清单
