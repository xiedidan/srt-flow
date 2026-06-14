---
id: TASK-067
title: 视频管理中直接新建视频合成任务
status: Review
assignee: Kiro
priority: High
---

# 任务描述
在视频管理界面的快速建立栏中，添加视频合成任务的快捷按钮，并修复三个点点击没有反应的问题。

# 验收标准 (Acceptance Criteria)
- [x] 修复快速建立栏三个点点击无反应的问题
- [x] 添加视频合成任务的快捷按钮
- [x] 点击快捷按钮可以直接新建视频合成任务
- [x] 新建任务时自动关联当前视频

# 实现说明
1. 将 VideoCard 中的"更多"按钮（⋯）替换为"视频合成"按钮（🎬）
2. 创建 SynthesisTaskModal 组件，支持：
   - 显示视频信息
   - 检测可用字幕（原始/翻译）
   - 选择字幕模式（双字幕/仅翻译/仅原始）
   - 无字幕时显示错误提示
3. 在 VideosView 中集成 SynthesisTaskModal

# 上下文 (Context)
- 来源：需求日记
- 相关功能：视频管理
- 相关文件：前端视频管理页面组件
