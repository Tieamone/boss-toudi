# 简历信息校正与招呼语策略优化 Spec

## Why
用户提供王文静真实简历后，发现脚本中 `RESUME_BASE_FACTS` 和 `RESUME_PROFILES` 存在多处与简历不符的虚构信息（如 Figma/CorelDRAW/InDesign/Premiere 等简历未提及的软件；甜序被误写为"奶茶"而非"低糖甜品"；余光 APP 功能模块被虚构；IKEA 拆解图/海洋的泪/RNW/百雀羚/书籍装帧/CD 封面/产品摄影等简历均未提及的项目）。同时用户要求优化招呼语生成策略：根据 JD 技术匹配着重介绍、不匹配往学习方向靠，且不要上来直接讲毕设。

## What Changes

### 一、简历信息校正（删除虚构、补全真实）

- **校正 `RESUME_BASE_FACTS.core_stack`**：从"Photoshop、Illustrator、Adobe XD"改为简历真实软件"Photoshop、Illustrator、After Effects、Adobe XD、剪映，以及 GPT-image2、Nano Banana、即梦、豆包、lovart 等 AI 设计工具"
- **校正 `RESUME_BASE_FACTS.summary`**：补充简历自我评价中的风格定位"作品风格偏向简洁、柔和、低饱和和情绪化表达"，并移除虚构项目方向（书籍装帧、CD 封面、产品摄影）
- **校正 `ui_ux` 画像**：
  - skills 移除 Figma（简历未提），改为"Photoshop、Illustrator、After Effects、Adobe XD、剪映"
  - proof_points 校正余光 APP 功能：从"情绪日记、冥想呼吸、匿名漂流瓶、共鸣社区"改为"情绪记录、即时干预、匿名社交、IP 陪伴"
  - proof_points 校正 IP 形象：从"IP 形象「甜脆」"改为"IP 陪伴形象"（简历未提名字）
  - proof_points 补充简历真实产出：主界面、启动页、引导页、底部导航、低保真/高保真原型、IP 三视图、IP 表情包、钥匙扣、帆布袋、明信片、抱枕、贴纸
  - proof_points 补充简历真实亮点：低饱和色彩、水彩插画、圆角界面、匿名社交机制
- **校正 `brand_visual` 画像**：
  - skills 移除 CorelDRAW（简历未提），改为"Photoshop、Illustrator"
  - proof_points 校正甜序项目：从"奶茶品牌"改为"低糖甜品品牌"
  - proof_points 校正产出：移除虚构的"手提袋、饮品杯、门头"，改为简历真实的"包装、菜单、物料、标志规范、标准色规范、标志黑白稿、标志安全空间、最小使用规范"
  - proof_points 补充简历亮点：低饱和绿色与柔和粉色、甜品果实叶片元素
- **校正 `info_visualization` 画像**：
  - proof_points 校正全球文化迁徙史：从"桑基图展示文化扩散路径"改为"时间轴、地图、矩阵图、雷达图等可视化方式"
  - proof_points 移除虚构项目：删除"IKEA 毕利书柜拆解图"、"海洋的泪环保科普图"
  - proof_points 补充简历亮点：蓝色系视觉语言、多类型图表组合、增强复杂历史信息阅读效率与视觉秩序感
- **校正 `ecommerce_design` 画像**：
  - skills 移除 Premiere（简历未提），改为"剪映"
  - proof_points 移除虚构项目：删除"RNW 护发精油详情页"、"百雀羚保湿乳详情页"、"产品摄影"
  - proof_points 改为基于简历可推导的真实能力：UI 界面设计、品牌视觉识别、版式设计能力可迁移到电商视觉
  - target_job 保持"电商/运营设计"，但 proof_points 诚实表达为"可迁移能力+愿意学习"
- **校正 `general_visual` 画像**：
  - skills 移除 InDesign、Premiere、Figma（简历未提），改为"Photoshop、Illustrator、After Effects、Adobe XD、剪映"
  - proof_points 移除虚构项目：删除"书籍装帧、CD 专辑封面设计、产品摄影、RNW、百雀羚详情页"
  - proof_points 改为简历真实项目：余光 APP、甜序品牌 VIS、全球文化迁徙史信息可视化
- **校正 `default` 画像**：
  - skills 同 general_visual 校正
  - proof_points 同 general_visual 校正

### 二、招呼语策略优化

- **优化 `call_mimo_api()` 的 prompt 生成规则**：
  - 新增"JD 技术匹配"逻辑：从 JD 提取的技术要求与候选人 skills 进行匹配，匹配上的着重介绍，没匹配上的往"愿意学习/可快速上手"方向靠
  - 新增"不要上来直接讲毕设"规则：调整生成规则结构，先回应岗位关键要求 → 再自然引出相关项目证据（而非直接以"我的毕业设计是..."开头）
  - 调整 prompt 中的结构指引：从"看到岗位关键要求 → 我做过的相关项目事实 → 能匹配岗位的技术点 → 期待进一步交流"改为"先回应岗位关键要求并匹配我的能力 → 自然引出相关项目证据（不要直接以毕设开头）→ 匹配的技术点或愿意学习的方向 → 期待进一步交流"
- **优化 `_format_profile_facts()`**：新增"可学习方向"字段，传递给 AI 用于不匹配时的兜底表达
- **优化 `_build_local_fallback_greeting()`**：兜底招呼语也遵循"不直接讲毕设"原则，先回应岗位要求再引出证据

## Impact
- Affected specs: 无
- Affected code:
  - `boss_auto_apply.py` 中 `RESUME_BASE_FACTS`（第 182-186 行）
  - `boss_auto_apply.py` 中 `RESUME_PROFILES` 全部 6 个画像（第 188-288 行）
  - `boss_auto_apply.py` 中 `call_mimo_api()` 的 prompt 生成规则（第 854-883 行）
  - `boss_auto_apply.py` 中 `_format_profile_facts()`（第 682-696 行）
  - `boss_auto_apply.py` 中 `_build_local_fallback_greeting()`（第 801-816 行）

## ADDED Requirements

### Requirement: JD 技术匹配与学习意愿表达
系统 SHALL 在生成招呼语时，将 JD 提取的技术要求与候选人 skills 进行匹配，匹配上的能力着重介绍，没匹配上的能力以"愿意学习/可快速上手"方向表达，不得硬说自己做过。

#### Scenario: JD 技术要求与候选人技能匹配
- **WHEN** JD 要求 UI 设计、品牌 VI、信息可视化等候选人已掌握的能力
- **THEN** AI 着重介绍相关项目证据和技能匹配点

#### Scenario: JD 技术要求与候选人技能不匹配
- **WHEN** JD 要求候选人未掌握的工具或能力（如 C4D、3D 建模、视频后期特效等）
- **THEN** AI 以"愿意学习/可快速上手/之前接触过相关思路"方向表达，不硬说自己精通

### Requirement: 招呼语不得直接以毕设开头
系统 SHALL 在生成招呼语时，先回应岗位关键要求并匹配能力，再自然引出相关项目证据，不得直接以"我的毕业设计是..."或"在校期间我做了..."等学生口吻开头。

#### Scenario: 社招岗位招呼语
- **WHEN** 检测到社招岗位
- **THEN** AI 先回应岗位要求 → 自然引出项目证据（不提"毕设""在校"）→ 匹配技术或学习意愿 → 期待交流

#### Scenario: 校招岗位招呼语
- **WHEN** 检测到校招岗位
- **THEN** AI 先回应岗位要求 → 自然引出项目证据（可以提项目但不直接以"毕设"开头）→ 匹配技术或学习意愿 → 期待交流

## MODIFIED Requirements

### Requirement: 候选人基础事实
RESUME_BASE_FACTS SHALL 严格反映王文静简历真实信息：
- summary：2026 届武汉生物工程学院视觉传达设计本科，作品风格偏向简洁、柔和、低饱和和情绪化表达，作品集涵盖 UI 界面设计（余光 APP）、品牌视觉识别（甜序低糖甜品）、信息可视化（全球文化迁徙史）等方向。
- core_stack：Photoshop、Illustrator、After Effects、Adobe XD、剪映，以及 GPT-image2、Nano Banana、即梦、豆包、lovart 等 AI 设计工具。
- communication_rules：只使用简历中存在的项目事实；不主动暴露手机号、邮箱、期望薪资；社招岗位不主动强调在校/应届，但不要编造正式多年工作经历或知名品牌合作经历；JD 中未掌握的能力以愿意学习方向表达。

### Requirement: 简历画像项目证据
所有 RESUME_PROFILES 画像的 proof_points SHALL 只包含简历中真实存在的项目事实，不得虚构 IKEA 拆解图、海洋的泪、RNW、百雀羚、书籍装帧、CD 封面、产品摄影等简历未提及的项目。

### Requirement: 招呼语生成结构
`call_mimo_api()` 的 prompt 生成规则 SHALL 遵循"先回应岗位要求 → 自然引出项目证据（不直接以毕设开头）→ 匹配技术或学习意愿 → 期待交流"的结构，并在 prompt 中明确传递 JD 技术匹配结果。
