---
id: TASK-060
title: 任务管理界面显示视频缩略图和名称
status: Done
assignee: Kiro
priority: High
---

# 任务描述
在任务管理界面中，显示视频的缩略图和名称，提升用户体验和任务识别度。

# 验收标准 (Acceptance Criteria)
- [x] 任务列表中显示关联视频的缩略图
- [x] 任务列表中显示关联视频的名称
- [x] 缩略图加载失败时显示占位图
- [x] 界面布局美观，不影响现有功能

# 实现方案

## 后端支持
后端 API (`/api/v1/tasks`) 已经返回 `video_id` 和 `video_title` 字段，无需修改。

## 前端修改 (`frontend/src/components/tasks/TaskCard.vue`)

1. **添加缩略图显示**
   - 使用 `/api/v1/videos/{video_id}/thumbnail` 获取缩略图
   - 添加 `thumbnailError` ref 跟踪加载失败状态
   - 加载失败时显示 🎬 占位图标

2. **卡片视图 (Card View)**
   - 在任务类型和状态下方添加视频信息区域
   - 左侧显示 80x45 像素的缩略图
   - 右侧显示视频标题和任务 ID
   - 标题过长时显示省略号，hover 显示完整标题

3. **列表视图 (List View)**
   - 在最左侧添加 48x27 像素的小缩略图
   - 添加视频标题列，替换原来的任务 ID 列
   - 标题过长时显示省略号

4. **样式优化**
   - 缩略图使用圆角和渐变背景
   - 占位图使用 emoji 图标
   - 保持与现有设计风格一致

# 上下文 (Context)
- 来源：需求日记
- 相关功能：任务管理
- 视频缩略图存储在 `data/downloads/<UUID>_<SafeTitle>/assets/thumbnail.jpg`
- 相关文件：
  - `frontend/src/components/tasks/TaskCard.vue` - 任务卡片组件
  - `frontend/src/views/TasksView.vue` - 任务管理页面
