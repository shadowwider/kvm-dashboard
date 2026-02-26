# 经验教训 (Lessons Learned)

## 模式识别 (Pattern Recognition)

- 初始创建项目时，遵循用户定义的任务管理流程。

## pysnmp v6 迁移关键差异 (2026-02-26)

1. **`pysnmp.carrier.asyncore` 已移除** → 用 `pysnmp.carrier.asyncio` 或 socket 替代
2. **`bulkCmd` 不再是 async iterator** → 是单次 `async` 调用，返回 `tuple`，需手动循环实现 WALK
3. **`bulkCmd` 返回结构**: `var_bind_table` 是 `list[list[ObjectType]]`（嵌套一层 list）
4. **`ObjectType[0]` 是 `ObjectIdentity`**，`str()` 返回 MIB 名称（如 `SNMPv2-SMI::enterprises.32828...`），**不是数字 OID**。用 `ObjectIdentity.getOid()` 获取 `ObjectName`，再 `tuple()` 转数字元组
5. **`endOfMibView` → `EndOfMibView`**, **`noSuchObject` → `NoSuchObject`** (大写)
6. **这些是类而不是实例**，需要 `EndOfMibView()` 和 `NoSuchObject()` 加括号实例化
7. **`passlib` + `bcrypt>=5.0` 不兼容**，需要 pin `bcrypt==4.0.1`

## SQLite 兼容性注意事项

- PostgreSQL 的 `JSONB` → 通用 `JSON`
- 复合主键在 SQLite 中不支持 nullable → 改用自增 `id`
- TimescaleDB hypertable 必须条件跳过
