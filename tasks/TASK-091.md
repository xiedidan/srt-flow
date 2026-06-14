# TASK-091: SandboxRunner 与 ToolRegistry 基础设施

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 10小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

实现沙箱执行和工具注册基础设施，用于下载、FFMPEG、自部署 TTS 等脆弱工具的隔离试跑、证据收集、产物校验和原子提交。

## 需求

1. 新增 SandboxRunner：创建沙箱目录、装配输入、执行命令、收集日志和产物。
2. 新增 ToolRegistry：登记 ffmpeg、ffprobe、yt-dlp、BiliDown、自部署 TTS 服务等。
3. 支持命令白名单、超时、资源限制和脱敏日志。
4. 支持沙箱产物校验和原子提交。
5. 支持 sandbox_runs 记录。

## 验收标准

- [ ] 可为 task_id 创建独立沙箱目录
- [ ] 可运行白名单命令并收集 stdout/stderr
- [ ] 可记录工具版本和健康检查结果
- [ ] 可校验并提交产物
- [ ] 失败时证据可被 Agent Session 读取

## 相关文件

- `backend/services/agent/sandbox.py`（建议新增）
- `backend/services/agent/tools.py`（建议新增）
- `backend/core/models.py`
- `backend/core/repositories.py`

## 依赖任务

- TASK-084
- TASK-085

