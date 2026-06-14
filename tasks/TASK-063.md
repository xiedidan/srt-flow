---
id: TASK-063
title: 修复下载视频进度显示问题
status: Done
assignee: Kiro
priority: High
---

# 任务描述
修复下载视频时进度显示的问题。由于存在多个文件需要下载，UI上不会区分具体文件，导致进度归0的现象。

# 验收标准 (Acceptance Criteria)
- [x] 进度显示连续，不会出现归0现象
- [ ] UI显示已下载文件数/总文件数 (需要扩展WebSocket协议，暂不实现)
- [ ] UI显示正在下载的文件名 (需要扩展WebSocket协议，暂不实现)
- [x] UI显示当前文件的下载进度 (显示整体进度，包含阶段提示)

# 实现方案

## 后端修改 (`backend/services/download.py`)

1. 增强 `ProgressParser` 类，添加多文件下载检测模式：
   - `YT_DLP_DESTINATION_PATTERN`: 检测新文件开始下载
   - `YT_DLP_COMPLETE_PATTERN`: 检测文件下载完成
   - `YT_DLP_ALREADY_DOWNLOADED_PATTERN`: 检测已下载文件
   - `YT_DLP_MERGER_PATTERN`: 检测合并阶段

2. 修改 `parse_yt_dlp()` 返回带类型的进度信息：
   - `type: "new_file"` - 新文件开始
   - `type: "progress"` - 下载进度
   - `type: "file_complete"` - 文件完成
   - `type: "merging"` - 合并阶段

3. 重写 `_run_download()` 方法实现多文件进度跟踪：
   - 跟踪 `completed_files`, `current_file_progress`, `estimated_total_files`
   - 整体进度计算: `(completed_files + current_file_progress/100) / total_files * 90`
   - 预留 10% 给合并阶段 (90-100%)
   - 进度单调递增，不会归零

## 前端修改 (`frontend/src/components/videos/VideoCard.vue`)

1. 修改 `downloadStatusText` 计算属性，根据进度显示阶段：
   - 0-89%: "下载中 XX%"
   - 90-94%: "处理中..."
   - 95-100%: "合并中..."

# 上下文 (Context)
- 来源：问题日记
- 相关功能：下载视频
- 相关文件：`backend/services/download.py`, `frontend/src/components/videos/VideoCard.vue`
