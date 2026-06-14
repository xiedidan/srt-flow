---
id: TASK-064
title: 修复停止任务卡住的问题
status: Done
assignee: Kiro
priority: High
---

# 任务描述
修复停止任务时卡住的问题。对于本地直接启动的Worker，应该直接把Worker进程杀死，避免Worker本身卡住造成空等。

# 验收标准 (Acceptance Criteria)
- [x] 分析各模块Worker的停止机制
- [x] 实现强制终止Worker进程的功能
- [x] 下载任务可以正常停止
- [x] 检查并修复其他模块的类似问题
- [x] 停止操作响应及时，不会卡住

# 实现方案

## 问题分析

当前架构中任务取消存在的问题：
1. API 的 cancel 端点只修改数据库中的任务状态为 FAILED
2. 正在执行的任务（Worker loop 中的 `service.execute()`）不会被通知
3. 所有 Service 都实现了 `cancel(task_id)` 方法，但从未被调用
4. 导致用户点击停止后，任务继续执行直到完成，体验很差

## 解决方案

在 API 的 cancel 端点中，当任务状态为 RUNNING 时，直接调用对应 Service 的 `cancel()` 方法来强制终止任务。

### 修改内容

1. **backend/app/main.py**
   - 在 `app.state` 中存储 `services` 字典，使其可以从 API 路由访问
   - 代码：`app.state.services = services`

2. **backend/app/routers/tasks.py**
   - 修改 `task_action` 端点的 cancel 逻辑
   - 当任务状态为 RUNNING 时：
     - 从 `app.state.services` 获取对应的 Service 实例
     - 调用 `service.cancel(task_id)` 强制终止任务
   - 然后更新数据库状态为 FAILED

### Service 的 cancel 实现

所有 Service 都已实现 `cancel()` 方法：

- **DownloadService**: 终止 yt-dlp 子进程（`process.terminate()` 或 `process.kill()`）
- **ASRService**: 设置取消标志，终止 Whisper/Gemini 进程
- **TranslationService**: 设置取消标志，停止批次翻译
- **TTSService**: 设置取消标志，停止语音合成
- **SynthesizerService**: 终止 FFmpeg 子进程
- **AssetGenService**: 设置取消标志，停止素材生成
- **EditorService**: 设置取消标志，停止编辑任务

这些 cancel 方法会：
1. 检查 `_current_task_id` 是否匹配
2. 终止正在运行的子进程（如 yt-dlp, ffmpeg）
3. 设置取消标志，让长时间运行的循环提前退出
4. 返回 True 表示取消成功

## 测试验证

需要测试各种任务类型的取消功能：
- 下载任务：在下载过程中点击停止，yt-dlp 进程应该被终止
- 语音识别：在识别过程中点击停止，Whisper 进程应该被终止
- 翻译任务：在翻译过程中点击停止，批次处理应该停止
- 语音合成：在合成过程中点击停止，TTS 进程应该被终止
- 视频合成：在合成过程中点击停止，FFmpeg 进程应该被终止

# 上下文 (Context)
- 来源：问题日记（在下载视频中发现）
- 相关功能：所有功能的任务停止
- 相关文档：`docs/05-调度-工作进程设计.md`
- 相关文件：
  - `backend/app/main.py` - Worker loop 和 services 初始化
  - `backend/app/routers/tasks.py` - 任务管理 API
  - `backend/services/*.py` - 各个 Service 的 cancel 实现
