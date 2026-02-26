# 任务清单 (Tasks)

- [x] 创建 Python 3.10 虚拟环境 (使用 uv) 
- [x] 重构后端目录结构，引入 FastAPI + SQLAlchemy
- [x] 兼容 SQLite（测试用）和 TimescaleDB（生产用）
- [x] 重写 SNMP 模拟器兼容 pysnmp v6 (剥离 asyncore，改用 pure socket + rfc1905 PDU)
- [x] **查阅官方 MIB / 日志验证 OID 树权威性，修正映射和测试**
- [x] 重构 oid_map 消除 Hardcode，实现 sysObjectID 探测
- [x] 拓展 OID 模型，增加自由存档标志(archive_enabled)
- [x] 新增端点 /api/topology 用于渲染动态拓扑图结构
- [ ] 完善定时轮询任务的健壮度
- [ ] 开发前端管理界面（基础配置、验证）

# 任务回顾 (Review)

- `2026-02-26`:
  - 根据权威的 `GUD-CCDC-MIB`、`GUD-CCDCCPU-MIB` 文件和真机实测 `kvm_snmp_monitor.log`，对 `oid_map.py` 的设备标量、`portTable` (端口状态)、`targetModuleTable` (CPU终端模块状态) 进行了完整、正向推导验证。
  - 测试通过证明当前系统能够一次性精准地获取设备层数据（含稀疏编号的 fan 和 net接口）、提取出所有的终端数量，并正确落库。
  - 核心痛点解决：`pysnmp v6` 的 `bulkCmd` 手动 WALK 逻辑重构完成。
  - 总结了“数据源可信度优先级”教训，不再在有权威 MIB 文档的情况下依赖自研模拟环境盲目修改映射。
