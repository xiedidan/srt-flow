---
id: TASK-019
title: 实现数据库管理器模块
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现数据库管理器模块，包括 SQLite 连接管理、SQLAlchemy ORM 配置、数据模型定义。

# 验收标准 (Acceptance Criteria)
- [x] SQLite 连接池配置 (StaticPool + WAL mode)
- [x] SQLAlchemy 异步引擎配置 (aiosqlite)
- [x] 基础数据模型定义（视频、任务、配置、标签、分组、文件、日志）
- [x] 数据库初始化与迁移脚本 (自动创建表)
- [x] 会话管理与依赖注入 (FastAPI Depends)

# 上下文 (Context)
- 参考 `docs/02-核心-数据库管理器设计.md`
- 目录：`backend/core/database.py`、`backend/core/models.py`
