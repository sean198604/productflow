# Phase 5：Excel 导入工作台

## 范围

Phase 5 将 Phase 4 的导入 API 接入 ProductFlow Web 工作台，视觉系统延续 3010 项目的企业 SaaS 风格，但不复制其项目管理业务。

本阶段交付：

- 四步导入向导：上传文件 → 字段映射 → 预览确认 → 导入完成
- XLSX 拖放/选择、上传进度状态及安全提示
- 工作表选择、表头行和数据起始行设置
- 智能字段建议、已有模板复用、管理员保存模板
- `source / target / transform / default_value / required / validation / formatter` 编辑
- 数据预览、错误行与重复 SKU 展示、客户端分页
- 图片缩略图、置信度、匹配来源、SKU、图片类型和主图人工确认
- 覆盖、仅补非空字段、跳过三种显式重复策略
- 导入结果与历史任务恢复
- 桌面侧栏和移动端五项底部导航

## 后端补充

- `GET /api/v1/import-image-candidates/{candidate_id}/content`
  - 通过租户 RLS 校验后返回导入候选图片
  - `Cache-Control: private`
- `PATCH /api/v1/import-image-candidates/{candidate_id}`
  - 支持 `matched_sku`，允许候选图片绑定到本次预览中尚未创建的产品
  - 仅 `preview_ready` 状态可调整匹配
- 图片宽高读取原始位图像素；无法识别的矢量/特殊格式才回退到 OOXML 显示尺寸

## 安全边界

- 上传分析不会直接写入产品表
- 只有用户确认重复策略后才执行导入
- 低于自动匹配阈值的图片始终保持 unmatched
- 候选图片访问和人工匹配均由租户上下文与 RLS 约束
- 客户字段和内部字段在映射目标中显示明确边界

## 真实数据验收

使用 `DEMO/Windchime.xlsx` 在专用 QA 租户完成部署后验收：

- 1 个工作表
- 19 个可预览数据行，其中 18 行有效、1 行有明确验证错误
- 19 张候选图片全部由锚点规则以 0.99 置信度匹配
- 缩略图通过受保护接口正常显示
- 数据预览、图片匹配、重复策略和任务恢复页面正常

验收未执行最后的“确认并写入产品库”，避免把 QA 检查数据误认为用户正式产品数据。
