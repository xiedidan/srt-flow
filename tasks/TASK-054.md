# TASK-054: 实现语音合成参考音频管理

## 任务信息
- 优先级: 高
- 状态: Review
- 来源: 需求日记

## 需求描述

将现有的参考音频路径配置，改为独立的参考音频管理功能。

## 功能要求

1. **参考音频管理页面**
   - 用户可以上传参考音频文件
   - 用户可以试听已上传的音频
   - 用户可以删除音频
   - 用户可以编辑音频描述

2. **页面展示**
   - 显示文件名
   - 显示描述
   - 操作按钮：试听、编辑、删除

3. **独立于模型**
   - 参考音频管理独立于所有 TTS 模型
   - 各 TTS 模型可以选择使用已管理的参考音频

## 技术要点

- 后端：新增参考音频管理 API（上传、列表、删除、更新描述）
- 前端：新增参考音频管理组件
- 数据库：新增参考音频表存储元数据
- 文件存储：统一存储参考音频文件

## 实现内容

### 后端
- `backend/core/models.py`: 新增 `ReferenceAudio` 数据库模型
- `backend/app/routers/reference_audio.py`: 新增参考音频 API 路由
- `backend/app/routers/__init__.py`: 注册路由

### 前端
- `frontend/src/api/referenceAudio.js`: 新增 API 模块
- `frontend/src/components/settings/ReferenceAudioManager.vue`: 新增管理组件
- `frontend/src/views/SettingsView.vue`: 添加参考音频配置入口
- `frontend/src/components/AppSidebar.vue`: 添加侧边栏导航

### 文档
- `API文档.md`: 新增参考音频管理 API 文档

## 验收标准

- [x] 可以上传参考音频文件
- [x] 可以试听已上传的音频
- [x] 可以编辑音频描述
- [x] 可以删除音频
- [ ] TTS 配置可以选择已管理的参考音频（待后续任务实现）
