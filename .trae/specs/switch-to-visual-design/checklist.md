# 视觉传达设计岗位切换 Checklist

## 历史日志清理
- [x] boss_apply_log.csv 已清空数据，仅保留表头一行
- [x] boss_auto_apply.log 已清空为空文件

## 候选人基础事实
- [x] RESUME_BASE_FACTS.summary 反映王文静视觉传达设计专业背景（武汉生物工程学院 2026 届）
- [x] RESUME_BASE_FACTS.core_stack 列出设计软件（PS/AI/XD/AE/PR/Figma 等）
- [x] RESUME_BASE_FACTS.communication_rules 符合设计求职者沟通边界

## CONFIG 搜索与过滤
- [x] CONFIG.keywords 全部为设计类搜索词（UI设计/UX设计/交互设计/视觉设计/品牌设计/平面设计/信息可视化/电商设计/美工/平面设计师）
- [x] CONFIG.skip_keywords 覆盖非设计类岗位（销售/运营/客服/开发/硬件/机械等）
- [x] CONFIG.max_salary_k 调整为设计岗市场行情（12K）

## 简历画像
- [x] RESUME_PROFILES 包含 5 个设计画像：ui_ux、brand_visual、info_visualization、ecommerce_design、general_visual
- [x] ui_ux 画像 proof_points 引用「余光」APP 毕设项目（情绪日记/冥想呼吸/匿名漂流瓶/共鸣社区/IP 形象「甜脆」）
- [x] brand_visual 画像 proof_points 引用「甜序」奶茶品牌 VIS 项目（命名/定位/logo/色彩字体/菜单包装/手提袋/饮品杯/门头/海报）
- [x] info_visualization 画像 proof_points 引用三张信息图（全球文化迁徙史桑基图/IKEA 毕利书柜拆解图/海洋的泪环保科普图）
- [x] ecommerce_design 画像 proof_points 引用 RNW 护发精油和百雀羚保湿乳详情页及产品摄影
- [x] general_visual 画像 proof_points 综合引用所有作品（APP/VI/信息图/详情页/书装/CD 封面/摄影）
- [x] 每个画像包含完整字段（match_keywords/specific_keywords/preferred_keywords/negative_keywords/target_job/skills/campus_pitch/experienced_pitch/proof_points/avoid_claims）
- [x] PROFILE_PRIORITY 顺序为 ["ui_ux", "brand_visual", "info_visualization", "ecommerce_design", "general_visual"]

## 岗位需求规则与风险表述
- [x] _JD_REQUIREMENT_RULES 覆盖设计能力（UI/UX/品牌VI/信息可视化/电商详情页/平面海报/包装/书装/摄影/插画IP/视觉传达）
- [x] _RISKY_AI_CLAIMS 移除技术类风险词，新增设计类风险词（资深设计总监/设计负责人/已上架商业App/知名品牌合作/4A广告公司/红点奖/iF设计奖等）

## AI 身份描述与兜底文案
- [x] call_mimo_api() 校招身份描述符合视觉传达设计专业应届生
- [x] call_mimo_api() 社招身份描述符合视觉传达设计求职者
- [x] call_mimo_api() extra_hint 提及"作品集事实"和"设计能力点"而非"技术点"
- [x] _build_local_fallback_greeting() 兜底文案使用"设计岗位"而非"软件开发"

## 脚本版本与入口
- [x] 脚本顶部版本号更新为 v22
- [x] 脚本顶部注释说明本次切换内容
- [x] 入口打印信息更新为"Boss直聘 自动投递 v22 (视觉传达设计-王文静)"

## 文档更新
- [x] SCRIPT_INFO_GRAPH.md 设计类示例更新为当前实际配置

## 语法与运行验证
- [x] python ast.parse 语法检查通过
- [x] 配置加载验证通过（keywords/profiles/priority 输出正确）
