# TASK-055: 语音识别预览叠加字幕

## 任务信息
- 优先级: 高
- 状态: Review
- 来源: 问题日记
- 相关功能: 系统配置-语音识别-字幕预览

## 问题描述

语音识别完成后的预览功能，视频播放时没有叠加显示字幕。

## 修复要求

预览视频时，需要将识别出的字幕叠加显示在视频上，方便用户检查识别结果。

## 技术要点

- 前端 VideoPlayer 组件需要支持字幕叠加显示
- 使用 HTML5 video 的 track 元素或 CSS 叠加方式
- 字幕需要与视频时间轴同步

## 修复内容

修改 `frontend/src/components/asr/SubtitleEditorModal.vue`：

1. 为 VideoPlayer 组件添加 `subtitles` 和 `subtitle-mode` 属性
2. 添加 `playerSubtitles` 计算属性，将字幕数据格式化为 VideoPlayer 需要的格式
3. 添加 `subtitleMode` 响应式变量，控制字幕显示/隐藏
4. 添加字幕显示切换按钮，用户可以选择显示或隐藏字幕

## 验收标准

- [x] 语音识别预览时字幕正确叠加在视频上
- [x] 字幕与视频时间轴同步
- [x] 字幕样式清晰可读
- [x] 用户可以切换字幕显示/隐藏
