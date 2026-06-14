# TASK-073: 调查并修复视频合成 FFMPEG 报错

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-01-27
- **预计工时**: 3小时

## 任务描述

视频合成虽然可以正确完成，但 FFMPEG 一直报错：
```
[h264 @ 0000019bad890dc0] Late SEI is not implemented. Update your FFmpeg version to the newest one from Git. If the problem still occurs, it means that your file has a feature which has not been implemented.
```

## 问题分析

可能的原因：
1. FFMPEG 版本过旧
2. 输入视频包含特殊的 H.264 SEI (Supplemental Enhancement Information) 数据
3. FFMPEG 参数配置不当
4. 编码器选择问题

## 需求

1. 调查报错的根本原因
2. 确认是否影响输出视频质量
3. 如果不影响质量，考虑抑制该警告
4. 如果影响质量，修复问题

## 实现方案

### 调查步骤

1. **检查 FFMPEG 版本**
   ```bash
   ffmpeg -version
   ```

2. **分析输入视频**
   ```bash
   ffprobe -v error -show_streams input.mp4
   ```

3. **测试不同参数**
   - 尝试添加 `-ignore_unknown` 参数
   - 尝试使用 `-c:v copy` 避免重新编码
   - 尝试使用不同的编码器

### 可能的解决方案

1. **升级 FFMPEG**
   - 如果版本过旧，升级到最新版本
   - 更新 Docker 镜像中的 FFMPEG

2. **调整 FFMPEG 参数**
   ```python
   # 添加参数抑制警告
   cmd = [
       'ffmpeg',
       '-loglevel', 'error',  # 只显示错误
       '-ignore_unknown',     # 忽略未知数据
       # ... 其他参数
   ]
   ```

3. **重新编码视频**
   - 如果是输入视频的问题，考虑在合成前重新编码
   - 移除特殊的 SEI 数据

## 验收标准

- [ ] 确认报错的根本原因
- [ ] 确认是否影响输出视频质量
- [ ] 如果不影响质量，成功抑制警告
- [ ] 如果影响质量，修复问题并验证输出正常
- [ ] 更新文档说明 FFMPEG 版本要求
- [ ] 在多个测试视频上验证修复效果

## 相关文件

- `backend/services/synthesizer.py` - 视频合成服务
- `deploy/Dockerfile` - Docker 镜像配置
- `docs/12-服务-视频合成服务设计.md` - 设计文档

## 依赖任务

无

## 备注

这是一个警告信息，虽然不影响功能，但可能影响日志可读性。需要先确认是否影响输出质量，再决定处理方式。
