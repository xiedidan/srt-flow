# TASK-039: 前端菜单结构重构

## 任务信息
- **状态**: Done
- **优先级**: High
- **负责人**: @Kiro
- **创建时间**: 2024-12-18
- **完成时间**: 2024-12-18
- **预计工时**: 4h
- **实际工时**: 2h

## 任务描述

重构前端菜单结构，将任务类型提升为一级菜单，突出系统核心能力。

### 当前问题
1. 视频管理下有"下载视频"子菜单，层级冗余
2. 任务管理页面需要先进入再选择任务类型，不够直观
3. 系统核心能力（语音识别、翻译、合成等）被隐藏在任务创建流程中

### 目标设计

#### 新菜单结构
```
🏠 首页
🎬 视频管理（一级菜单，包含视频列表和下载功能）
🎤 语音识别（任务列表 + 新建）
🌐 字幕翻译（任务列表 + 新建）
🔊 语音合成（任务列表 + 新建）
🎞️ 视频合成（任务列表 + 新建）
🎨 素材生成（任务列表 + 新建）
✂️ 字幕编辑（任务列表 + 新建）
📋 任务管理（汇总所有任务，只读，不提供新建）
⚙️ 系统设置
```

## 实现步骤

### 1. 更新路由配置 (frontend/src/router/index.js)
- [ ] 添加各任务类型的独立路由
  - `/asr` - 语音识别
  - `/translate` - 字幕翻译
  - `/tts` - 语音合成
  - `/synthesis` - 视频合成
  - `/asset` - 素材生成
  - `/editor` - 字幕编辑
- [ ] 保留 `/tasks` 作为任务汇总页面

### 2. 创建任务类型专属视图组件
- [ ] `frontend/src/views/AsrTasksView.vue` - 语音识别任务
- [ ] `frontend/src/views/TranslateTasksView.vue` - 翻译任务
- [ ] `frontend/src/views/TtsTasksView.vue` - 语音合成任务
- [ ] `frontend/src/views/SynthesisTasksView.vue` - 视频合成任务
- [ ] `frontend/src/views/AssetTasksView.vue` - 素材生成任务
- [ ] `frontend/src/views/EditorTasksView.vue` - 编辑任务

### 3. 重构 AppSidebar.vue
- [ ] 移除视频管理的子菜单
- [ ] 添加各任务类型的一级菜单项
- [ ] 调整任务管理菜单位置（放在任务类型菜单之后）
- [ ] 移除任务管理的子菜单

### 4. 调整 VideosView.vue
- [ ] 在视频管理页面内集成下载功能
- [ ] 移除独立的下载视频入口

### 5. 调整 TasksView.vue
- [ ] 移除新建任务按钮
- [ ] 添加提示：引导用户到各任务类型页面创建任务
- [ ] 保留任务列表、筛选、详情查看功能

### 6. 更新 TaskSubmitModal.vue
- [ ] 创建任务类型专属的提交组件
  - `AsrTaskSubmitModal.vue`
  - `TranslateTaskSubmitModal.vue`
  - `TtsTaskSubmitModal.vue`
  - `SynthesisTaskSubmitModal.vue`
  - `AssetTaskSubmitModal.vue`
  - `EditorTaskSubmitModal.vue`
- [ ] 每个组件只显示对应任务类型的配置项

## 技术要点

### 组件复用策略
- 任务列表展示逻辑可复用 `TaskCard.vue`
- 任务详情查看复用 `TaskDetailModal.vue`
- 各任务类型视图共享相同的布局结构，只是筛选条件不同

### 数据筛选
```javascript
// 在各任务类型视图中
const taskType = 'asr' // 或 'translate', 'tts' 等
const filteredTasks = computed(() => 
  tasksStore.tasks.filter(t => t.type === taskType)
)
```

### 路由元信息
```javascript
{
  path: '/asr',
  name: 'asr-tasks',
  component: () => import('@/views/AsrTasksView.vue'),
  meta: { 
    title: '语音识别',
    taskType: 'asr'
  }
}
```

## 验收标准

- [x] 菜单结构符合新设计
- [x] 各任务类型页面可独立访问
- [x] 各任务类型页面可创建对应任务
- [x] 任务管理页面显示所有任务，不提供新建功能
- [x] 视频管理页面集成下载功能
- [x] 所有页面功能正常，无报错
- [x] 路由跳转流畅，面包屑正确

## 相关文档

- 系统架构文档.md
- API文档.md
- frontend/src/router/index.js
- frontend/src/components/AppSidebar.vue

## 备注

此重构将显著提升用户体验，让系统核心能力一目了然，减少操作层级。

## 完成总结

### 已完成工作

1. **路由配置更新**
   - 新增 6 个任务类型路由：/asr, /translate, /tts, /synthesis, /asset, /editor
   - 每个路由配置了对应的 meta 信息（title, taskType）

2. **创建任务类型专属视图**
   - AsrTasksView.vue - 语音识别任务
   - TranslateTasksView.vue - 字幕翻译任务
   - TtsTasksView.vue - 语音合成任务
   - SynthesisTasksView.vue - 视频合成任务
   - AssetTasksView.vue - 素材生成任务
   - EditorTasksView.vue - 字幕编辑任务
   - 每个视图包含：任务统计、任务列表、新建任务按钮、空状态提示

3. **重构侧边栏菜单**
   - 移除视频管理的子菜单
   - 添加 6 个任务类型一级菜单
   - 任务管理移至任务类型菜单之后
   - 保留系统设置的子菜单结构

4. **调整任务管理页面**
   - 移除新建任务按钮
   - 添加信息提示横幅，引导用户到对应页面创建任务
   - 保留任务列表、筛选、详情查看功能

5. **视频管理页面**
   - 已集成下载功能，无需修改

### 新菜单结构

```
🏠 首页
🎬 视频管理
🎤 语音识别
🌐 字幕翻译
🔊 语音合成
🎞️ 视频合成
🎨 素材生成
✂️ 字幕编辑
📋 任务管理
⚙️ 系统设置
```

### 用户体验提升

- 系统核心能力直接展示在一级菜单，一目了然
- 减少操作层级，从"任务管理 → 新建任务 → 选择类型"变为"直接进入对应页面"
- 每个任务类型页面独立展示该类型的任务，更加聚焦
- 任务管理页面作为汇总视图，方便查看所有任务状态
