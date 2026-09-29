# Phase 2：多租户身份、登录与权限

## 完成范围

Phase 2 建立租户身份边界，不引入产品、客户、模板或生成任务等后续业务表。

- `tenants` 与 `users` 表、约束和 Alembic 迁移
- Owner、Admin、Member 三种租户内角色
- Argon2id 密码哈希和 JWT Access Token
- 登录、当前会话、用户列表及创建用户 API
- React 登录页、受保护路由、会话恢复和退出登录
- PostgreSQL 强制 RLS 与运行/迁移账号分离

## 数据库安全模型

数据库连接职责严格分离：

- `productflow`：仅用于迁移、租户初始化和测试数据准备的管理角色。
- `productflow_app`：FastAPI 运行角色；不是超级用户，没有 `BYPASSRLS`，不能建库或建角色。

`tenants` 和 `users` 均启用 `ENABLE ROW LEVEL SECURITY` 与 `FORCE ROW LEVEL SECURITY`。每个受保护事务先使用 `set_config(..., true)` 设置事务级 `app.tenant_id` 和 `app.user_id`，RLS 策略随后只允许访问当前租户数据。事务结束后上下文自动失效，不会泄漏到连接池的下一次使用。

登录只需要全局唯一的用户名（或邮箱）和密码。系统通过参数受限的 `SECURITY DEFINER` 函数 `app.lookup_active_login(text)` 在后台定位账号所属 Tenant；应用角色不能直接绕过 RLS 枚举租户。确定租户后，事务立即设置租户上下文，再查询用户和校验密码。

JWT 中包含 `sub`、`tid`、`role`、`jti`、签发/到期时间、Issuer 和 Audience。后端不会单独信任 Token 中的角色：每次受保护请求都会在 RLS 上下文中重新加载用户和租户，并检查二者仍处于启用状态。

## 表与核心约束

### tenants

- 主键：`id UUID`
- 唯一：`slug`
- 状态：`active | suspended | archived`
- 租户代码由系统维护，不参与登录
- 用户名和邮箱在全平台范围内唯一

### users

- 主键：`id UUID`
- 外键：`tenant_id -> tenants.id ON DELETE CASCADE`
- 唯一：`(tenant_id, id)`、`(tenant_id, username)`、`(tenant_id, email)`
- 角色：`owner | admin | member`
- 状态：`active | disabled`
- 用户名和邮箱必须为小写

`(tenant_id, id)` 复合唯一键为后续所有租户业务表采用复合外键预留了一致的引用目标。

## API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 公开 | 以用户名/邮箱和密码登录 |
| `GET` | `/api/v1/auth/me` | 已登录 | 返回当前用户和租户 |
| `GET` | `/api/v1/users` | Owner / Admin | 列出当前租户用户 |
| `POST` | `/api/v1/users` | Owner / Admin | 创建当前租户用户；Admin 只能创建 Member |

错误响应使用统一结构并返回正确的 `401`、`403` 或 `409`，不泄露“租户不存在”与“账号或密码错误”的差异。

## 初始化租户

租户和首位 Owner 必须由管理角色通过命令行创建：

```bash
docker compose run --rm migrate python -m app.cli.create_tenant_owner \
  --tenant-name "Acme Trading" \
  --tenant-slug acme \
  --username owner \
  --email owner@example.com \
  --password "replace-with-a-long-password"
```

命令会拒绝长度少于 12 个字符的密码，并验证当前数据库连接确实为超级用户，避免把高权限初始化能力暴露给 Web 运行进程。

## Phase 2 验收边界

自动化测试覆盖密码哈希、JWT 声明、成功/失败登录、受保护接口、角色限制，以及两个租户之间的数据库级读写隔离。

本阶段不包含 Refresh Token、服务端 Token 撤销列表、忘记密码/修改密码 UI、邀请邮件或 SSO。这些能力不影响当前短时 Access Token 和账号停用校验的安全边界，将在身份生命周期阶段继续扩展。
