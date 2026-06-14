# TASK-072: 显示句子合并的默认提示词

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-01-27
- **预计工时**: 2小时

## 任务描述

句子合并的提示词现在显示"留空则使用默认提示词"，但是默认提示词到底是什么？需要展示出来，让用户了解默认行为。

## 需求

在语音合成配置界面中：
1. 显示句子合并的默认提示词内容
2. 用户可以查看默认提示词
3. 用户可以基于默认提示词进行修改

## 实现方案

### 前端修改

1. **配置界面优化**
   - 在提示词输入框下方显示"默认提示词"折叠面板
   - 点击可展开查看完整的默认提示词
   - 提供"使用默认提示词"按钮快速填充

2. **UI 设计**
   ```vue
   <el-form-item label="句子合并提示词">
     <el-input 
       type="textarea" 
       placeholder="留空则使用默认提示词"
       v-model="config.merge_prompt"
     />
     <el-collapse>
       <el-collapse-item title="查看默认提示词">
         <pre>{{ defaultMergePrompt }}</pre>
         <el-button size="small" @click="useDefaultPrompt">
           使用默认提示词
         </el-button>
       </el-collapse-item>
     </el-collapse>
   </el-form-item>
   ```

### 后端修改

1. **API 返回默认值**
   - 在配置 API 中返回默认提示词
   - 添加 `default_merge_prompt` 字段

2. **配置结构**
   ```python
   {
     "merge_prompt": "",  # 用户自定义
     "default_merge_prompt": "..."  # 系统默认
   }
   ```

## 验收标准

- [ ] 配置界面显示"查看默认提示词"选项
- [ ] 点击可展开查看完整默认提示词
- [ ] 提供"使用默认提示词"按钮
- [ ] 点击按钮后，输入框填充默认内容
- [ ] 用户可以基于默认内容进行修改
- [ ] 清空输入框后仍使用默认提示词

## 相关文件

- `frontend/src/views/SettingsView.vue` - 配置页面
- `backend/app/routers/system.py` - 配置 API
- `backend/services/tts.py` - TTS 服务（包含默认提示词）

## 依赖任务

- TASK-071 (调查并修复语音合成句子合并功能) - 相关

## 备注

这是一个用户体验优化，帮助用户理解系统的默认行为，便于用户进行自定义调整。
