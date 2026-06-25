# 视觉传达设计岗位切换 Spec

## Why
当前 `boss_auto_apply.py` 脚本是为计算机科学与技术专业求职者（龚曦）配置的，投递 Java/Python/前端等技术岗位。需要将其切换为视觉传达设计专业求职者（王文静）使用，投递 UI/UX、品牌设计、信息可视化、电商设计、综合平面设计等设计类岗位，并清空历史投递日志，从零开始新一轮投递。

## What Changes
- **更换候选人基础事实**：将 `RESUME_BASE_FACTS` 从计算机专业龚曦改为视觉传达设计专业王文静（武汉生物工程学院 2026 届）。
- **更换搜索关键词**：`CONFIG.keywords` 从 `java/python/后端开发/前端开发/全栈开发/软件开发/Android/小程序开发` 改为设计类岗位搜索词。
- **调整过滤规则**：`skip_keywords` 移除硬件/机械/电气等不相关跳过词，改为销售/运营/客服/财务等设计岗不投方向；`max_salary_k` 按设计岗市场行情调整。
- **重写简历画像**：删除 `RESUME_PROFILES` 中所有计算机画像（android/java_backend/python_ai_app/python_automation/fullstack/frontend/miniapp_uniapp/default），替换为 5 个设计画像：
  1. `ui_ux`：UI/UX 设计师，侧重「余光」APP 毕设项目
  2. `brand_visual`：品牌设计/视觉设计，侧重「甜序」VIS 项目
  3. `info_visualization`：信息可视化/数据设计，侧重三张信息图
  4. `ecommerce_design`：电商/运营设计，侧重详情页和产品摄影
  5. `general_visual`：综合视觉/平面设计，全能型打底版
- **调整画像优先级**：`PROFILE_PRIORITY` 按设计岗位优先级重新排序。
- **更新岗位需求规则**：`_JD_REQUIREMENT_RULES` 从技术栈规则改为设计能力规则（UI/UX、品牌VI、信息可视化、电商详情页、摄影、平面设计等）。
- **更新风险表述清单**：`_RISKY_AI_CLAIMS` 移除技术类风险词（JVM/Nginx/微服务等），新增设计类风险词（资深设计总监/千万级用户/已上架商业App等）。
- **更新 AI 身份描述**：`call_mimo_api()` 中校招/社招身份描述从"Java 实习和完整项目交付"改为"视觉传达设计专业应届生及完整作品集"。
- **更新博客链接**：`AI_CONFIG.blog_url` 暂时保留原值（待用户确认是否替换为作品集链接）。
- **清空历史日志**：
  - `boss_apply_log.csv`：清空所有投递记录，仅保留表头
  - `boss_auto_apply.log`：清空运行日志
  - `chat_error_screenshot.png`：保留（运行时自动覆盖）
- **更新脚本信息图谱**：`SCRIPT_INFO_GRAPH.md` 中"如何更换使用对象"章节的设计类示例更新为当前实际配置。
- **更新脚本版本号**：从 v21 升级为 v22，更新顶部注释说明本次切换内容。

## Impact
- Affected specs: 无（项目无既有 spec）
- Affected code:
  - `boss_auto_apply.py`：CONFIG、RESUME_BASE_FACTS、RESUME_PROFILES、PROFILE_PRIORITY、_JD_REQUIREMENT_RULES、_RISKY_AI_CLAIMS、call_mimo_api() 身份描述、_build_local_fallback_greeting() 兜底文案、入口打印信息
  - `boss_apply_log.csv`：清空数据，保留表头
  - `boss_auto_apply.log`：清空内容
  - `SCRIPT_INFO_GRAPH.md`：更新设计类示例
- 不受影响：浏览器启动、登录、卡片抓取、聊天页发送、公司/HR 校验等通用逻辑保持不变。

## ADDED Requirements

### Requirement: 视觉传达设计候选人画像
系统 SHALL 提供 5 个针对视觉传达设计专业的简历画像，分别对应 UI/UX、品牌视觉、信息可视化、电商设计、综合平面设计 5 个岗位方向，每个画像包含 match_keywords/specific_keywords/preferred_keywords/negative_keywords/target_job/skills/campus_pitch/experienced_pitch/proof_points/avoid_claims 字段。

#### Scenario: UI/UX 岗位匹配
- **WHEN** 搜索词或职位名包含 "UI"、"UX"、"交互设计"、"用户体验" 等关键词
- **THEN** 系统选择 `ui_ux` 画像，AI 生成消息时引用「余光」APP 毕设项目（情绪日记、冥想呼吸、匿名漂流瓶、共鸣社区、IP 形象「甜脆」）

#### Scenario: 品牌设计岗位匹配
- **WHEN** 搜索词或职位名包含 "品牌设计"、"视觉设计"、"VI"、"CIS" 等关键词
- **THEN** 系统选择 `brand_visual` 画像，AI 生成消息时引用「甜序」奶茶品牌 VIS 项目（命名、定位、logo、色彩字体规范、菜单包装、手提袋、饮品杯、门头、宣传海报）

#### Scenario: 信息可视化岗位匹配
- **WHEN** 搜索词或职位名包含 "信息可视化"、"数据可视化"、"信息图"、"数据设计" 等关键词
- **THEN** 系统选择 `info_visualization` 画像，AI 生成消息时引用三张信息图作品（全球文化迁徙史桑基图、IKEA 毕利书柜拆解图、海洋的泪环保科普图）

#### Scenario: 电商设计岗位匹配
- **WHEN** 搜索词或职位名包含 "电商设计"、"详情页"、"运营设计"、"美工" 等关键词
- **THEN** 系统选择 `ecommerce_design` 画像，AI 生成消息时引用 RNW 护发精油和百雀羚保湿乳详情页及产品摄影作品

#### Scenario: 综合平面设计岗位匹配
- **WHEN** 未命中上述 4 个特定画像，但职位属于设计类
- **THEN** 系统选择 `general_visual` 画像，AI 生成消息时综合引用 APP 界面、品牌 VI、信息可视化、电商详情页、书籍装帧、CD 封面、产品摄影等多元作品

### Requirement: 设计类岗位搜索关键词
系统 SHALL 使用以下关键词搜索岗位：UI设计、UX设计、交互设计、视觉设计、品牌设计、平面设计、信息可视化、电商设计、美工、平面设计师。

### Requirement: 设计类岗位过滤规则
系统 SHALL 跳过以下岗位：销售、运营、客服、行政、财务、会计、人事、HR、硬件工程师、电气工程师、机械工程师、程序员、开发工程师、算法工程师、测试工程师、运维工程师、剪辑师（纯剪辑无设计）、3D建模师（除非综合设计岗）。

## MODIFIED Requirements

### Requirement: 候选人基础事实
RESUME_BASE_FACTS SHALL 反映王文静的视觉传达设计专业背景：
- summary：武汉生物工程学院视觉传达设计专业 2026 届应届生，作品涵盖 UI/UX、品牌 VI、信息可视化、电商设计、包装、书装、摄影等方向。
- core_stack：PS、AI、XD、AE、PR 等设计软件。
- communication_rules：只使用作品集中存在的项目事实；不主动暴露手机号、邮箱、期望薪资；社招岗位不主动强调在校/应届，但不要编造正式多年工作经历。

### Requirement: 岗位需求提取规则
_JD_REQUIREMENT_RULES SHALL 从技术栈规则改为设计能力规则，覆盖：UI/UX 设计、品牌/VI 设计、信息可视化、电商/详情页设计、平面/海报设计、包装设计、书籍装帧、产品摄影、插画/IP 设计、视觉传达等。

### Requirement: AI 风险表述校验
_RISKY_AI_CLAIMS SHALL 移除技术类风险词（JVM/Nginx/微服务/分布式/高并发/模型训练/LangChain/RAG 等），新增设计类风险词（资深设计总监/设计负责人/带团队/千万级用户/百万级用户/已上架商业App/知名品牌合作/4A 广告公司/国际大奖等）。

## REMOVED Requirements

### Requirement: 计算机专业画像
**Reason**: 候选人已从计算机专业龚曦更换为视觉传达设计专业王文静，所有计算机画像（android/java_backend/python_ai_app/python_automation/fullstack/frontend/miniapp_uniapp/default）不再适用。
**Migration**: 替换为 5 个设计类画像（ui_ux/brand_visual/info_visualization/ecommerce_design/general_visual）。

### Requirement: 计算机岗位搜索关键词
**Reason**: 不再投递 java/python/后端开发/前端开发/全栈开发/软件开发/Android/小程序开发 等技术岗位。
**Migration**: 替换为设计类搜索关键词。

### Requirement: 历史投递日志
**Reason**: 用户要求"把日志记录删除，从新开始"，历史投递记录为计算机岗位，对新轮投递无参考价值且会误触发"已投递/已跳过"去重逻辑。
**Migration**: 清空 `boss_apply_log.csv` 数据保留表头；清空 `boss_auto_apply.log` 内容。
