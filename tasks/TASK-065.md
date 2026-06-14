---
id: TASK-065
title: 修复标签编辑功能不起作用的问题
status: Done
assignee: Kiro
priority: High
---

# 任务描述
修复视频管理中标签编辑功能不起作用的问题，包括删除和新增标签点击后没有反应。

# 验收标准 (Acceptance Criteria)
- [x] 标签新增功能正常工作
- [x] 标签删除功能正常工作
- [x] 标签编辑后正确保存到数据库
- [x] UI正确反馈操作结果

# 上下文 (Context)
- 来源：问题日记
- 相关功能：视频管理
- 相关文件：前端视频管理页面组件

# 解决方案

## 问题根因
`VideoRepository` 继承自 `BaseRepository`，但 `BaseRepository.update` 方法只接受实体对象参数，而路由中调用 `repo.update(video_id, updates)` 传入的是 video_id 和更新字典。此外，tags 是多对多关系，需要特殊处理。

## 修复内容

### 1. 在 VideoRepository 中添加专门的 update 方法 (backend/core/repositories.py)
- 新增 `update(video_id, updates)` 方法，接受 video_id 和更新字典
- 特殊处理 tags 字段：通过 TagRepository.get_or_create 获取或创建标签，然后替换 video.tags 关系
- 更新其他普通字段

### 2. 修复路由返回值 (backend/app/routers/videos.py)
- 修复 `update_video` 端点，使用 `repo.update()` 返回的更新后的 video 对象
- 将 `video.tags`（Tag 对象列表）正确转换为字符串列表 `[t.name for t in video.tags]`
