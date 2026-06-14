# TASK-057: 语音合成前字幕句子合并

## 任务信息
- 优先级: 高
- 状态: Review
- 来源: 问题日记
- 相关功能: 系统配置-语音合成

## 问题描述

由于字幕有长度限制，很多句子是从中间分开的，语音合成的时候会不连贯。

## 修复要求

1. **句子合并**
   - 在语音合成之前，使用 AI 将分开的句子合并起来
   - 合并后的整句语音更加连贯

2. **语音组装调整**
   - 合成完毕的语音在组装时需要对应调整
   - 确保合并后的语音与原始时间轴正确对应

3. **配置项**
   - 在语音合成配置中增加语句合并 AI 的相关配置
   - 包括：AI 服务商选择、模型选择、提示词等

## 技术要点

- 后端：新增句子合并服务，调用 AI 进行智能合并
- 配置：新增语句合并相关配置项
- 时间轴：合并后需要重新计算时间轴映射

## 实现内容

### 后端修改

1. `backend/core/config.py` - TTSConfig 新增字段：
   - `enable_sentence_merge`: 是否启用句子合并
   - `sentence_merge_provider_id`: AI 服务商 ID
   - `sentence_merge_model`: 模型名称
   - `sentence_merge_temperature`: 温度参数
   - `sentence_merge_system_prompt`: 自定义系统提示词
   - `sentence_merge_user_prompt`: 自定义用户提示词

2. `backend/services/tts.py` - 新增类和修改：
   - `MergedSubtitleEntry`: 合并后的字幕条目数据类
   - `SentenceMergeError`: 句子合并错误异常
   - `SentenceMerger`: AI 句子合并器类
     - 调用 LLM API 进行智能句子合并
     - 解析 AI 返回的合并结果
     - 处理时间轴映射
   - `TTSService.execute()`: 集成句子合并流程
     - 在 TTS 合成前执行句子合并
     - 使用合并后的条目进行语音合成
     - 保持与原始时间轴的对应关系

3. `backend/app/main.py` - TTS 任务预处理：
   - 加载句子合并配置
   - 解密 AI 服务商 API Key
   - 注入到任务 payload 中

### 前端修改

1. `frontend/src/views/SettingsView.vue` - TTS 配置 schema：
   - 新增"句子合并"配置组
   - 支持启用/禁用句子合并
   - AI 服务商选择（复用 AIProviderSelect 组件）
   - 模型名称、温度等参数配置
   - 自定义提示词配置

## 验收标准

- [x] 语音合成前自动进行句子合并（可配置开关）
- [x] 合并后的语音连贯自然
- [x] 合成语音与视频时间轴正确对应
- [x] 可配置语句合并 AI 参数（服务商、模型、提示词等）
