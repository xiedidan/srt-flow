<script setup>
/**
 * Settings view - Configuration management
 * Section is determined by route param, navigation is in sidebar
 */
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useConfigStore } from '@/stores/config'
import ConfigForm from '@/components/settings/ConfigForm.vue'
import AIProviderManager from '@/components/settings/AIProviderManager.vue'
import ReferenceAudioManager from '@/components/settings/ReferenceAudioManager.vue'

const route = useRoute()
const configStore = useConfigStore()

// Section definitions with schema
const sections = {
  global: { 
    label: '通用设置', 
    icon: '⚙️',
    schema: {
      default_source_language: { label: '默认源语言', options: [
        { value: 'en', label: '英语' },
        { value: 'zh', label: '中文' },
        { value: 'ja', label: '日语' },
        { value: 'ko', label: '韩语' }
      ]},
      default_target_language: { label: '默认目标语言', options: [
        { value: 'zh-CN', label: '简体中文' },
        { value: 'en', label: '英语' },
        { value: 'ja', label: '日语' }
      ]},
      log_level: { label: '日志级别', options: [
        { value: 'DEBUG', label: 'DEBUG' },
        { value: 'INFO', label: 'INFO' },
        { value: 'WARNING', label: 'WARNING' },
        { value: 'ERROR', label: 'ERROR' }
      ]},
      max_concurrent_tasks: { label: '最大并发任务数', min: 1, max: 10 },
      proxy_url: { label: '代理地址', hint: '全局代理，用于视频下载、模型下载、API 调用等，留空则不使用代理' }
    }
  },
  'ai-providers': {
    label: 'AI 服务商',
    icon: '🤖',
    isCustom: true  // Custom component, not ConfigForm
  },
  'reference-audio': {
    label: '参考音频',
    icon: '🎵',
    isCustom: true  // Custom component for reference audio management
  },
  download: { 
    label: '下载服务', 
    icon: '📥',
    schema: {
      preferred_quality: { label: '首选画质', options: [
        { value: 'best', label: '最佳' },
        { value: '1080p', label: '1080p' },
        { value: '720p', label: '720p' },
        { value: '480p', label: '480p' }
      ]},
      download_subtitles: { label: '下载字幕' },
      cookies_browser: { label: 'Cookies 来源浏览器', hint: 'YouTube 下载需要登录验证时，从指定浏览器读取 cookies', options: [
        { value: 'none', label: '不使用' },
        { value: 'chrome', label: 'Chrome' },
        { value: 'firefox', label: 'Firefox' },
        { value: 'edge', label: 'Edge' },
        { value: 'safari', label: 'Safari' },
        { value: 'opera', label: 'Opera' },
        { value: 'brave', label: 'Brave' }
      ]},
      nodejs_path: { label: 'Node.js 路径', hint: 'Node.js 可执行文件的完整路径，用于解决 YouTube n-parameter 挑战（例如: C:\\Program Files\\nodejs\\node.exe）' },
      allowed_time_start: { label: '允许下载开始时间', hint: '格式: HH:MM，留空不限制' },
      allowed_time_end: { label: '允许下载结束时间', hint: '格式: HH:MM，留空不限制' }
    }
  },
  asr: { 
    label: '语音识别', 
    icon: '🎤',
    schema: {
      engine: { label: '识别引擎', options: [
        { value: 'faster_whisper_xxl', label: 'Faster Whisper XXL 本地' }
      ]},
      whisper_model_size: { 
        label: 'Whisper 模型', 
        showWhen: { engine: ['faster_whisper_xxl'] }, 
        component: 'whisper-model',
        options: [
          { value: 'tiny', label: 'Tiny' },
          { value: 'base', label: 'Base' },
          { value: 'small', label: 'Small' },
          { value: 'medium', label: 'Medium' },
          { value: 'large', label: 'Large' },
          { value: 'large-v2', label: 'Large V2' },
          { value: 'large-v3', label: 'Large V3' }
        ]
      },
      whisper_extra_args: { label: 'Whisper 额外参数', showWhen: { engine: ['faster_whisper_xxl'] }, hint: '命令行额外参数，如 --language zh --initial_prompt "简体中文"' },
      device: { label: '计算设备', showWhen: { engine: ['faster_whisper_xxl'] }, options: [
        { value: 'auto', label: '自动' },
        { value: 'cpu', label: 'CPU' },
        { value: 'cuda', label: 'CUDA (GPU)' }
      ]}
    }
  },
  translate: { 
    label: '翻译服务', 
    icon: '🌐',
    schema: {
      ai_provider_id: { 
        label: 'AI 服务商', 
        component: 'ai-provider-select',
        hint: '选择已配置的 AI 服务商'
      },
      model_name: { label: '模型名称', hint: '如 deepseek-chat, gpt-4o' },
      batch_size: { label: '批次大小', min: 1, max: 100, hint: '每批翻译的字幕条数' },
      context_overlap_lines: { label: '批次上下文行数', min: 0, max: 10, hint: '每批次前后包含的上下文行数，用于提高翻译连贯性' },
      empty_line_threshold: { label: '空行阈值', min: 0, max: 1, step: 0.1, hint: '批次中空行比例超过此阈值时自动重试，0 表示禁用检测' },
      temperature: { label: '温度', min: 0, max: 2, step: 0.1 },
      max_retries: { label: '最大重试次数', min: 1, max: 10 },
      system_prompt: { 
        label: '系统提示词', 
        component: 'textarea',
        placeholder: 'You are a professional subtitle translator...',
        hint: '留空使用默认。可用变量: {source_lang}, {target_lang}'
      },
      user_prompt_template: { 
        label: '用户提示词模板', 
        component: 'textarea',
        placeholder: '{task_context}\n{context_before}\n{subtitles}\n{context_after}',
        hint: '留空使用默认。可用变量: {source_lang}, {target_lang}, {task_context}, {video_title}, {author}, {description}, {context_before}, {context_after}, {subtitles}'
      }
    }
  },
  tts: { 
    label: '语音合成', 
    icon: '🔊',
    schema: {
      // Common settings
      engine: { label: 'TTS 引擎', group: '通用设置', options: [
        { value: 'chattts', label: 'ChatTTS' },
        { value: 'indextts', label: 'IndexTTS' },
        { value: 'sparktts', label: 'SparkTTS' },
        { value: 'cozyvoice', label: 'CozyVoice' },
        { value: 'coqui', label: 'Coqui TTS' },
        { value: 'vits', label: 'VITS' },
        { value: 'azure_tts', label: 'Azure TTS (在线)' },
        { value: 'edge_tts', label: 'Edge TTS (在线)' },
        { value: 'volc_tts', label: '火山 TTS (在线)' }
      ]},
      output_format: { label: '输出格式', group: '通用设置', options: [
        { value: 'wav', label: 'WAV' },
        { value: 'm4a', label: 'M4A' },
        { value: 'mp3', label: 'MP3' }
      ]},
      speed_factor: { label: '语速倍率', group: '通用设置', min: 0.5, max: 2, step: 0.1 },
      use_gpu: { label: '使用 GPU 加速', group: '通用设置' },
      reference_audio: { label: '参考音频路径', group: '通用设置', hint: '用于语音克隆的参考音频文件路径' },
      
      // ChatTTS settings
      chattts_temperature: { 
        label: '温度', 
        group: 'ChatTTS 设置', 
        showWhen: { engine: ['chattts'] },
        min: 0, max: 1, step: 0.1,
        hint: '控制生成的随机性，越低越稳定'
      },
      chattts_top_p: { 
        label: 'Top P', 
        group: 'ChatTTS 设置', 
        showWhen: { engine: ['chattts'] },
        min: 0, max: 1, step: 0.1 
      },
      chattts_top_k: { 
        label: 'Top K', 
        group: 'ChatTTS 设置', 
        showWhen: { engine: ['chattts'] },
        min: 1, max: 100 
      },
      
      // IndexTTS settings
      indextts_mode: { 
        label: '运行模式', 
        group: 'IndexTTS 设置', 
        showWhen: { engine: ['indextts'] },
        options: [
          { value: 'local', label: '本地部署' },
          { value: 'api', label: 'API 调用' }
        ]
      },
      indextts_api_url: { 
        label: 'API 地址', 
        group: 'IndexTTS 设置', 
        showWhen: { engine: ['indextts'] },
        hint: 'API 模式下的服务地址，如 http://localhost:8080'
      },
      
      // SparkTTS settings
      sparktts_mode: { 
        label: '运行模式', 
        group: 'SparkTTS 设置', 
        showWhen: { engine: ['sparktts'] },
        options: [
          { value: 'local', label: '本地部署' },
          { value: 'api', label: 'API 调用' }
        ]
      },
      sparktts_api_url: { 
        label: 'API 地址', 
        group: 'SparkTTS 设置', 
        showWhen: { engine: ['sparktts'] },
        hint: 'API 模式下的服务地址'
      },
      
      // CozyVoice settings
      cozyvoice_mode: { 
        label: '运行模式', 
        group: 'CozyVoice 设置', 
        showWhen: { engine: ['cozyvoice'] },
        options: [
          { value: 'local', label: '本地部署' },
          { value: 'api', label: 'API 调用' }
        ]
      },
      cozyvoice_api_url: { 
        label: 'API 地址', 
        group: 'CozyVoice 设置', 
        showWhen: { engine: ['cozyvoice'] },
        hint: 'API 模式下的服务地址'
      },
      cozyvoice_speaker: { 
        label: '默认说话人', 
        group: 'CozyVoice 设置', 
        showWhen: { engine: ['cozyvoice'] },
        hint: '如：中文女、中文男、英文女、英文男'
      },
      
      // Coqui TTS settings
      coqui_model_name: { 
        label: '模型名称', 
        group: 'Coqui TTS 设置', 
        showWhen: { engine: ['coqui'] },
        hint: '如 tts_models/multilingual/multi-dataset/xtts_v2'
      },
      
      // VITS settings
      vits_model_path: { 
        label: '模型路径', 
        group: 'VITS 设置', 
        showWhen: { engine: ['vits'] },
        hint: 'VITS 模型文件路径'
      },
      
      // Azure TTS settings (online service)
      azure_tts_voice: { 
        label: '语音角色', 
        group: 'Azure TTS 设置', 
        showWhen: { engine: ['azure_tts'] },
        component: 'tts-voice-select',
        hint: '选择 Azure TTS 语音角色'
      },
      azure_tts_style: { 
        label: '语音风格', 
        group: 'Azure TTS 设置', 
        showWhen: { engine: ['azure_tts'] },
        options: [
          { value: 'general', label: '通用' },
          { value: 'assistant', label: '助理' },
          { value: 'chat', label: '聊天' },
          { value: 'customerservice', label: '客服' },
          { value: 'newscast', label: '新闻播报' },
          { value: 'affectionate', label: '深情' },
          { value: 'angry', label: '愤怒' },
          { value: 'calm', label: '平静' },
          { value: 'cheerful', label: '愉快' },
          { value: 'sad', label: '悲伤' },
          { value: 'serious', label: '严肃' },
          { value: 'friendly', label: '友好' },
          { value: 'gentle', label: '温柔' }
        ],
        hint: '部分角色支持情感风格'
      },
      azure_tts_rate: { 
        label: '语速调整', 
        group: 'Azure TTS 设置', 
        showWhen: { engine: ['azure_tts'] },
        hint: '百分比调整，如 0、+10、-10'
      },
      azure_tts_pitch: { 
        label: '音调调整', 
        group: 'Azure TTS 设置', 
        showWhen: { engine: ['azure_tts'] },
        hint: '百分比调整，如 0、+10、-10'
      },
      
      // Edge TTS settings (online service)
      edge_tts_voice: { 
        label: '语音角色', 
        group: 'Edge TTS 设置', 
        showWhen: { engine: ['edge_tts'] },
        component: 'tts-voice-select',
        hint: '选择 Edge TTS 语音角色'
      },
      edge_tts_rate: { 
        label: '语速调整', 
        group: 'Edge TTS 设置', 
        showWhen: { engine: ['edge_tts'] },
        hint: '如 +0%、+10%、-10%'
      },
      edge_tts_pitch: { 
        label: '音调调整', 
        group: 'Edge TTS 设置', 
        showWhen: { engine: ['edge_tts'] },
        hint: '如 +0Hz、+10Hz、-10Hz'
      },
      
      // Volc TTS settings (online service)
      volc_tts_voice: { 
        label: '语音角色', 
        group: '火山 TTS 设置', 
        showWhen: { engine: ['volc_tts'] },
        component: 'tts-voice-select',
        hint: '选择火山 TTS 语音角色'
      },
      
      // Sentence merge settings
      enable_sentence_merge: { 
        label: '启用句子合并', 
        group: '句子合并',
        hint: '使用 AI 将分散的字幕片段合并成完整句子，使语音更连贯'
      },
      sentence_merge_provider_id: { 
        label: 'AI 服务商', 
        group: '句子合并',
        component: 'ai-provider-select',
        showWhen: { enable_sentence_merge: [true] },
        hint: '用于句子合并的 AI 服务商'
      },
      sentence_merge_model: { 
        label: '模型名称', 
        group: '句子合并',
        showWhen: { enable_sentence_merge: [true] },
        hint: '如 deepseek-chat, gpt-4o'
      },
      sentence_merge_temperature: { 
        label: '温度', 
        group: '句子合并',
        showWhen: { enable_sentence_merge: [true] },
        min: 0, max: 1, step: 0.1,
        hint: '较低温度产生更稳定的合并结果'
      },
      sentence_merge_system_prompt: { 
        label: '系统提示词', 
        group: '句子合并',
        component: 'textarea',
        showWhen: { enable_sentence_merge: [true] },
        placeholder: '你是一个字幕句子合并助手...',
        hint: '留空使用默认'
      },
      sentence_merge_user_prompt: { 
        label: '用户提示词', 
        group: '句子合并',
        component: 'textarea',
        showWhen: { enable_sentence_merge: [true] },
        placeholder: '请合并以下字幕片段...',
        hint: '留空使用默认。可用变量: {subtitles}'
      }
    }
  },
  synthesis: { 
    label: '视频合成', 
    icon: '🎬',
    schema: {
      // Encoding settings group
      video_encoder: { 
        label: '视频编码器', 
        group: '编码设置',
        component: 'encoder-select',
        hint: 'NVENC 需要 NVIDIA 显卡支持'
      },
      video_crf: { 
        label: '视频质量 (CRF)', 
        group: '编码设置',
        min: 0, max: 51,
        hint: '值越小质量越高，文件越大。推荐 18-28'
      },
      video_preset: { 
        label: '编码预设', 
        group: '编码设置',
        options: [
          { value: 'ultrafast', label: '极快 (质量较低)' },
          { value: 'superfast', label: '超快' },
          { value: 'veryfast', label: '很快' },
          { value: 'faster', label: '较快' },
          { value: 'fast', label: '快' },
          { value: 'medium', label: '中等 (推荐)' },
          { value: 'slow', label: '慢' },
          { value: 'slower', label: '较慢' },
          { value: 'veryslow', label: '极慢 (质量最高)' }
        ],
        hint: '仅对 CPU 编码有效，GPU 编码忽略此设置'
      },
      
      // Audio settings group
      mute_original: { label: '静音原视频', group: '音频设置' },
      original_volume: { label: '原音量', group: '音频设置', min: 0, max: 1, step: 0.1 },
      tts_volume: { label: 'TTS 音量', group: '音频设置', min: 0, max: 2, step: 0.1 },
      
      // Original subtitle style group (bottom, smaller, white)
      original_subtitle_font: { label: '字体', group: '原始字幕样式', component: 'font-select', hint: '点击选择系统字体' },
      original_subtitle_font_size: { label: '字号', group: '原始字幕样式', min: 12, max: 200 },
      original_subtitle_bold: { label: '粗体', group: '原始字幕样式' },
      original_subtitle_color: { label: '颜色', group: '原始字幕样式' },
      original_subtitle_alpha: { label: '透明度', group: '原始字幕样式', min: 0, max: 1, step: 0.05, hint: '0 完全透明，1 完全不透明' },
      original_subtitle_outline_color: { label: '描边颜色', group: '原始字幕样式' },
      original_subtitle_outline_width: { label: '描边宽度', group: '原始字幕样式', min: 0, max: 10 },
      original_subtitle_shadow_enabled: { label: '启用阴影', group: '原始字幕样式', hint: '为字幕添加投影效果' },
      original_subtitle_shadow_offset: { label: '阴影偏移', group: '原始字幕样式', min: 0, max: 10, hint: '阴影距离文字的像素数', showWhen: { original_subtitle_shadow_enabled: [true] } },
      original_subtitle_position: { label: '位置', group: '原始字幕样式', options: [
        { value: 'top', label: '顶部' },
        { value: 'center', label: '居中' },
        { value: 'bottom', label: '底部' }
      ]},
      original_subtitle_margin_v: { label: '垂直边距', group: '原始字幕样式', min: 0, max: 500, hint: '距离屏幕边缘的像素数' },
      original_subtitle_background_enabled: { label: '启用背景', group: '原始字幕样式', hint: '为字幕添加半透明背景条' },
      original_subtitle_background_color: { label: '背景颜色', group: '原始字幕样式', showWhen: { original_subtitle_background_enabled: [true] } },
      original_subtitle_background_alpha: { label: '背景透明度', group: '原始字幕样式', min: 0, max: 1, step: 0.05, hint: '0 完全透明，1 完全不透明', showWhen: { original_subtitle_background_enabled: [true] } },
      original_subtitle_background_padding_h: { label: '背景水平边距', group: '原始字幕样式', min: 0, max: 100, hint: '背景框左右内边距', showWhen: { original_subtitle_background_enabled: [true] } },
      original_subtitle_background_padding_v: { label: '背景垂直边距', group: '原始字幕样式', min: 0, max: 100, hint: '背景框上下内边距', showWhen: { original_subtitle_background_enabled: [true] } },
      
      // Translated subtitle style group (above original, larger, yellow)
      translated_subtitle_font: { label: '字体', group: '翻译字幕样式', component: 'font-select', hint: '点击选择系统字体' },
      translated_subtitle_font_size: { label: '字号', group: '翻译字幕样式', min: 12, max: 200 },
      translated_subtitle_bold: { label: '粗体', group: '翻译字幕样式' },
      translated_subtitle_color: { label: '颜色', group: '翻译字幕样式' },
      translated_subtitle_alpha: { label: '透明度', group: '翻译字幕样式', min: 0, max: 1, step: 0.05, hint: '0 完全透明，1 完全不透明' },
      translated_subtitle_outline_color: { label: '描边颜色', group: '翻译字幕样式' },
      translated_subtitle_outline_width: { label: '描边宽度', group: '翻译字幕样式', min: 0, max: 10 },
      translated_subtitle_shadow_enabled: { label: '启用阴影', group: '翻译字幕样式', hint: '为字幕添加投影效果' },
      translated_subtitle_shadow_offset: { label: '阴影偏移', group: '翻译字幕样式', min: 0, max: 10, hint: '阴影距离文字的像素数', showWhen: { translated_subtitle_shadow_enabled: [true] } },
      translated_subtitle_position: { label: '位置', group: '翻译字幕样式', options: [
        { value: 'top', label: '顶部' },
        { value: 'center', label: '居中' },
        { value: 'bottom', label: '底部' }
      ]},
      translated_subtitle_margin_v: { label: '垂直边距', group: '翻译字幕样式', min: 0, max: 500, hint: '距离屏幕边缘的像素数' },
      translated_subtitle_background_enabled: { label: '启用背景', group: '翻译字幕样式', hint: '为字幕添加半透明背景条' },
      translated_subtitle_background_color: { label: '背景颜色', group: '翻译字幕样式', showWhen: { translated_subtitle_background_enabled: [true] } },
      translated_subtitle_background_alpha: { label: '背景透明度', group: '翻译字幕样式', min: 0, max: 1, step: 0.05, hint: '0 完全透明，1 完全不透明', showWhen: { translated_subtitle_background_enabled: [true] } },
      translated_subtitle_background_padding_h: { label: '背景水平边距', group: '翻译字幕样式', min: 0, max: 100, hint: '背景框左右内边距', showWhen: { translated_subtitle_background_enabled: [true] } },
      translated_subtitle_background_padding_v: { label: '背景垂直边距', group: '翻译字幕样式', min: 0, max: 100, hint: '背景框上下内边距', showWhen: { translated_subtitle_background_enabled: [true] } }
    }
  },
  asset: { 
    label: '素材生成', 
    icon: '🖼️',
    schema: {
      // Summary AI settings group
      summary_ai_provider_id: { 
        label: 'AI 服务商', 
        group: '摘要生成',
        component: 'ai-provider-select',
        hint: '用于生成摘要的 AI 服务商'
      },
      summary_model_name: { 
        label: '模型名称', 
        group: '摘要生成',
        hint: '如 deepseek-chat, gpt-4o'
      },
      summary_temperature: { 
        label: '温度', 
        group: '摘要生成',
        min: 0, max: 2, step: 0.1,
        hint: '较低温度产生更准确的摘要'
      },
      summary_system_prompt: { 
        label: '系统提示词', 
        group: '摘要生成',
        component: 'textarea',
        placeholder: 'You are a professional content summarizer...',
        hint: '留空使用默认'
      },
      summary_user_prompt_template: { 
        label: '用户提示词', 
        group: '摘要生成',
        component: 'textarea',
        placeholder: '请根据以下字幕内容生成摘要...',
        hint: '留空使用默认。可用变量: {video_title}, {subtitles}'
      },
      
      // Title AI settings group
      title_count: { 
        label: '候选数量', 
        group: '标题生成',
        min: 1, max: 10 
      },
      title_ai_provider_id: { 
        label: 'AI 服务商', 
        group: '标题生成',
        component: 'ai-provider-select',
        hint: '用于生成标题的 AI 服务商'
      },
      title_model_name: { 
        label: '模型名称', 
        group: '标题生成',
        hint: '如 deepseek-chat, gpt-4o'
      },
      title_temperature: { 
        label: '温度', 
        group: '标题生成',
        min: 0, max: 2, step: 0.1,
        hint: '较高温度产生更有创意的标题'
      },
      title_system_prompt: { 
        label: '系统提示词', 
        group: '标题生成',
        component: 'textarea',
        placeholder: 'You are a professional video title writer...',
        hint: '留空使用默认。可用变量: {title_count}'
      },
      title_user_prompt_template: { 
        label: '用户提示词', 
        group: '标题生成',
        component: 'textarea',
        placeholder: '请根据以下字幕内容生成{title_count}个标题...',
        hint: '留空使用默认。可用变量: {title_count}, {video_title}, {subtitles}'
      },
      
      // Thumbnail AI settings group - Text model for generating image prompts
      thumbnail_ai_provider_id: { 
        label: 'AI 服务商', 
        group: '缩略图生成（提示词）',
        component: 'ai-provider-select',
        hint: '用于生成文生图提示词的 AI 服务商'
      },
      thumbnail_model_name: { 
        label: '模型名称', 
        group: '缩略图生成（提示词）',
        hint: '如 deepseek-chat, gpt-4o'
      },
      thumbnail_temperature: { 
        label: '温度', 
        group: '缩略图生成（提示词）',
        min: 0, max: 2, step: 0.1 
      },
      thumbnail_system_prompt: { 
        label: '系统提示词', 
        group: '缩略图生成（提示词）',
        component: 'textarea',
        placeholder: 'You are a professional thumbnail designer...',
        hint: '留空使用默认'
      },
      thumbnail_user_prompt_template: { 
        label: '用户提示词', 
        group: '缩略图生成（提示词）',
        component: 'textarea',
        placeholder: '请根据以下内容生成缩略图描述...',
        hint: '留空使用默认。可用变量: {video_title}, {summary}'
      },
      
      // Image generation API config
      thumbnail_image_provider: {
        label: '图像生成服务',
        group: '缩略图生成（图像 API）',
        component: 'select',
        options: [
          { value: 'midjourney', label: 'Midjourney' },
          { value: 'stable-diffusion', label: 'Stable Diffusion' }
        ],
        hint: '文生图服务提供商'
      },
      thumbnail_image_api_key: {
        label: 'API Key',
        group: '缩略图生成（图像 API）',
        component: 'secret',
        hint: '图像生成服务的 API Key'
      },
      thumbnail_image_model: {
        label: '图像模型',
        group: '缩略图生成（图像 API）',
        component: 'select',
        options: [
          { value: 'z-image-pro', label: 'Z-Image Pro' }
        ],
        hint: '选择图像生成模型'
      },
      thumbnail_image_base_url: {
        label: 'API 地址',
        group: '缩略图生成（图像 API）',
        hint: '留空使用默认地址'
      }
    }
  }
}

// Get current section from route param
const activeSection = computed(() => route.params.section || 'global')

const currentSection = computed(() => sections[activeSection.value])

const currentConfig = computed(() => configStore.getConfig(activeSection.value))

// Load config when section changes (skip for custom components like ai-providers)
watch(activeSection, async (newSection) => {
  // Skip fetching for custom sections that have their own data management
  if (sections[newSection]?.isCustom) {
    return
  }
  if (!configStore.configs[newSection]) {
    await configStore.fetchConfig(newSection)
  }
}, { immediate: true })

async function handleSave(updates) {
  try {
    await configStore.updateConfig(activeSection.value, updates)
  } catch (e) {
    console.error('Save failed:', e)
  }
}

async function handleReset() {
  try {
    await configStore.resetConfig(activeSection.value)
  } catch (e) {
    console.error('Reset failed:', e)
  }
}

async function handleSetSecret(keyName, value) {
  try {
    await configStore.setSecret(activeSection.value, keyName, value)
  } catch (e) {
    console.error('Set secret failed:', e)
  }
}

onMounted(() => {
  configStore.fetchCategories()
})
</script>

<template>
  <div class="settings-view">
    <div class="page-header">
      <h2 class="page-title">
        <span class="section-icon">{{ currentSection?.icon }}</span>
        {{ currentSection?.label || '系统设置' }}
      </h2>
    </div>
    
    <div class="settings-panel">
      <!-- AI Provider Manager (custom component) -->
      <AIProviderManager v-if="activeSection === 'ai-providers'" />
      
      <!-- Reference Audio Manager (custom component) -->
      <ReferenceAudioManager v-else-if="activeSection === 'reference-audio'" />
      
      <!-- Standard ConfigForm for other sections -->
      <ConfigForm
        v-else
        :config="currentConfig"
        :schema="currentSection?.schema"
        :saving="configStore.saving"
        :category="activeSection"
        @save="handleSave"
        @reset="handleReset"
        @set-secret="handleSetSecret"
      />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.settings-view {
  max-width: 800px;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  
  .section-icon {
    font-size: 28px;
  }
}

.settings-panel {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 24px;
}
</style>
