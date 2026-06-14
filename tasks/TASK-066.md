---
id: TASK-066
title: 视频下载时优先加载封面和名称
status: Review
assignee: Kiro
priority: High
---

# 任务描述
在视频下载过程中，优先下载并显示视频的封面和名称，而不是只显示网页链接。

# 验收标准 (Acceptance Criteria)
- [x] 下载开始时优先获取视频元数据（封面、名称）
- [x] 在下载列表中显示视频封面缩略图
- [x] 在下载列表中显示视频名称
- [x] 元数据获取失败时显示占位信息

# 上下文 (Context)
- 来源：问题日记
- 相关功能：视频管理/下载
- 相关文件：`backend/services/download.py`

# 实现方案

## 后端修改

1. **YtDlpDownloader.fetch_metadata()** - 新增方法
   - 使用 `yt-dlp --skip-download` 快速获取视频元数据
   - 返回 title, thumbnail_url, duration, channel_name 等信息
   - 超时设置 60 秒

2. **DownloadService.execute()** - 修改流程
   - 先调用 fetch_metadata() 获取元数据
   - 通过 payload_callback 更新任务 payload
   - 再执行实际下载

3. **QueueManager.update_task_payload()** - 新增方法
   - 支持运行时更新任务 payload

4. **Worker._create_payload_callback()** - 新增方法
   - 创建 payload 更新回调
   - 更新后通过 WebSocket 广播元数据

5. **BaseService.execute()** - 接口扩展
   - 添加可选的 payload_callback 参数
   - 所有服务已更新兼容

6. **videos.py API** - 修改返回数据
   - 下载任务返回 title, thumbnail_url, duration, channel_name

## 前端修改

1. **VideoCard.vue** - 支持远程缩略图
   - 下载中的视频使用 thumbnail_url 显示远程封面

2. **videos.js store** - 新增 updateDownloadMetadata()
   - 处理 WebSocket 元数据更新

3. **VideosView.vue** - 处理 task_metadata 消息
   - 监听 WebSocket 的 task_metadata 事件

## WebSocket 新增消息类型

```json
{
  "type": "task_metadata",
  "data": {
    "task_id": "xxx",
    "metadata": {
      "title": "视频标题",
      "thumbnail_url": "https://...",
      "duration": 360,
      "channel_name": "频道名"
    }
  }
}
```
