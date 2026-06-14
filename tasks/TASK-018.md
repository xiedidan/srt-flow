---
id: TASK-018
title: 实现配置管理器模块
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现配置管理器模块，支持 .env 系统配置和 SQLite 用户配置的统一管理，包含敏感信息加密存储。

# 验收标准 (Acceptance Criteria)
- [x] .env 文件加载与解析
- [x] SQLite 配置表设计与 CRUD (接口已实现，待数据库模块集成)
- [x] AES-256-GCM 加密/解密实现
- [x] 配置分层管理（系统级/全局/功能级）
- [x] 前端脱敏显示支持
- [x] 配置缓存机制

# 上下文 (Context)
- 参考 `docs/01-核心-配置管理器设计.md`
- 目录：`backend/core/config.py`
