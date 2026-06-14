# TASK-074: 实现翻译空行合并功能

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-01-27
- **预计工时**: 3小时

## 任务描述

如果翻译 API 返回了空行，就把空行与前面一行合并起来（注意合并时间戳）。废弃原有的空行阈值配置，因为添加了空行合并，空行阈值不再有用了。

## 需求

1. 检测翻译结果中的空行
2. 将空行与前一行合并
3. 正确处理时间戳合并
4. 移除空行阈值配置

## 实现方案

### 后端修改

1. **翻译服务修改** (`backend/services/translator.py`)
   ```python
   def merge_empty_lines(subtitles: List[Subtitle]) -> List[Subtitle]:
       """Merge empty translation lines with previous line"""
       merged = []
       for i, sub in enumerate(subtitles):
           if not sub.translated_text.strip() and merged:
               # Merge with previous subtitle
               prev = merged[-1]
               prev.end_time = sub.end_time
               # Keep original text
               prev.original_text += " " + sub.original_text
           else:
               merged.append(sub)
       return merged
   ```

2. **在翻译后调用合并**
   ```python
   # After translation
   translated_subtitles = await translate_batch(batch)
   translated_subtitles = merge_empty_lines(translated_subtitles)
   ```

3. **移除空行阈值配置**
   - 从 `backend/core/config.py` 中移除相关字段
   - 从前端配置界面移除相关输入
   - 更新数据库迁移（如果需要）

### 前端修改

1. **移除配置项**
   - 从 `frontend/src/views/SettingsView.vue` 移除空行阈值配置
   - 更新配置 schema

### 数据库修改

1. **配置表更新**
   - 移除 `empty_line_threshold` 字段（如果存在）

## 验收标准

- [ ] 翻译结果中的空行被正确合并到前一行
- [ ] 合并后的时间戳正确（使用后一行的结束时间）
- [ ] 原始文本也被合并
- [ ] 空行阈值配置已从前后端移除
- [ ] 通过测试验证合并逻辑正确
- [ ] 更新相关文档

## 测试用例

```python
# 输入
[
  Subtitle(start=0, end=2, original="Hello", translated="你好"),
  Subtitle(start=2, end=4, original="world", translated=""),
  Subtitle(start=4, end=6, original="!", translated="!")
]

# 输出
[
  Subtitle(start=0, end=2, original="Hello", translated="你好"),
  Subtitle(start=2, end=6, original="world !", translated="!"),
]
```

## 相关文件

- `backend/services/translator.py` - 翻译服务
- `backend/core/config.py` - 配置模型
- `frontend/src/views/SettingsView.vue` - 配置页面
- `backend/app/main.py` - 配置预处理
- `docs/10-服务-翻译服务设计.md` - 设计文档

## 依赖任务

- TASK-048 (修复翻译字幕空行过多问题) - 相关，可能需要协调

## 备注

这个方案比空行阈值更直接有效，直接在源头解决空行问题。注意要正确处理边界情况（如第一行就是空行）。
