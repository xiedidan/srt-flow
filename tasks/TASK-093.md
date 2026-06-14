# TASK-093: FfmpegAgent 与 DownloadAgent MVP

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 12小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

实现第一批任务 Agent：FfmpegAgent 和 DownloadAgent。目标不是完全自动修复所有问题，而是能解释错误、提出方案、接收限制、在沙箱中执行低风险修复。

## 需求

### FfmpegAgent

1. 解析 ffmpeg stderr。
2. 识别常见错误：路径转义、字体缺失、编码器不支持、音视频流映射错误。
3. 提出保守修复方案。
4. 支持 10 秒片段沙箱试跑。
5. 通过 ffprobe 校验输出。

### DownloadAgent

1. 解析 yt-dlp / BiliDown 错误。
2. 检查工具版本、代理、cookie、格式参数。
3. 提出更新工具、切换代理、降级格式、重试下载等方案。
4. 高风险动作进入用户确认。

## 验收标准

- [ ] FFMPEG 路径转义错误能生成可读解释和修复方案
- [ ] FFMPEG 修复方案可进入沙箱试跑
- [ ] Download 失败能展示工具版本、代理/cookie 诊断
- [ ] 高风险方案进入 waiting_user
- [ ] 修复尝试写入 agent_interventions 和 node_review

## 相关文件

- `backend/services/agent/ffmpeg_agent.py`（建议新增）
- `backend/services/agent/download_agent.py`（建议新增）
- `backend/services/synthesizer.py`
- `backend/services/download.py`

## 依赖任务

- TASK-090
- TASK-091
- TASK-092

