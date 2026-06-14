---
id: TASK-049
title: 修复语音识别Gemini配置显示问题
status: Review
assignee: Kiro
priority: High
source: 问题日记
---

# 任务描述
系统配置-语音识别界面，即使选中非Gemini的接口，也会显示2个Gemini的配置（并且是英文的）。需要修复配置项的条件显示逻辑。

# 验收标准 (Acceptance Criteria)
- [x] 选择非Gemini引擎时，不显示Gemini相关配置项
- [x] Gemini配置项的标签显示为中文
- [x] 配置项的 showWhen 条件正确生效

# 上下文 (Context)
- 相关功能：系统配置-语音识别
- 参考 `docs/01-核心-配置管理器设计.md` 中的配置项条件显示规则
- 参考 `frontend/src/components/settings/ConfigForm.vue`

# 解决方案
问题原因：后端 `ASRConfig` 模型中定义了 `gemini_base_url` 和 `gemini_api_key` 字段，但前端 schema 中没有定义这些字段。当后端返回这些字段时，由于 schema 中没有对应的定义，`isFieldVisible` 函数找不到 `showWhen` 条件，默认返回 `true`，导致字段被显示。同时由于没有 label 定义，显示为英文字段名。

修复方案：在 `frontend/src/views/SettingsView.vue` 的 ASR schema 中添加缺失的 `gemini_base_url` 和 `gemini_api_key` 字段定义，并设置正确的 `showWhen` 条件和中文标签。
