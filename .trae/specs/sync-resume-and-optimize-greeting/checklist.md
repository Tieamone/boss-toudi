# 简历信息校正与招呼语策略优化 Checklist

## RESUME_BASE_FACTS 校正
- [x] core_stack 反映简历真实软件（PS/AI/AE/XD/剪映 + AI 设计工具）
- [x] summary 包含简历风格定位（简洁、柔和、低饱和、情绪化表达）
- [x] communication_rules 包含 JD 未掌握能力以学习方向表达的规则

## RESUME_PROFILES 校正
- [x] ui_ux 画像 skills 移除 Figma，proof_points 校正余光 APP 功能（情绪记录/即时干预/匿名社交/IP陪伴）
- [x] ui_ux 画像 proof_points 包含简历真实产出（主界面/启动页/引导页/IP三视图/表情包/文创延展）
- [x] brand_visual 画像 skills 移除 CorelDRAW
- [x] brand_visual 画像 proof_points 校正甜序为"低糖甜品"非"奶茶"
- [x] brand_visual 画像 proof_points 包含简历真实产出（包装/菜单/标志规范/标准色/黑白稿/安全空间）
- [x] info_visualization 画像 proof_points 移除虚构的 IKEA 拆解图、海洋的泪
- [x] info_visualization 画像 proof_points 校正为时间轴/地图/矩阵图/雷达图
- [x] ecommerce_design 画像 skills 移除 Premiere，改为剪映
- [x] ecommerce_design 画像 proof_points 移除虚构的 RNW、百雀羚、产品摄影
- [x] ecommerce_design 画像 proof_points 改为可迁移能力+学习意愿
- [x] general_visual 画像 skills 移除 InDesign/Premiere/Figma
- [x] general_visual 画像 proof_points 移除虚构的书籍装帧/CD封面/产品摄影
- [x] default 画像与 general_visual 校正一致

## 招呼语策略优化
- [x] call_mimo_api() prompt 包含 JD 技术匹配规则（匹配着重介绍，不匹配往学习方向靠）
- [x] call_mimo_api() prompt 包含不直接以毕设开头的规则
- [x] call_mimo_api() prompt 结构调整为"先回应岗位要求 → 自然引出证据 → 匹配技术或学习意愿 → 期待交流"
- [x] _build_local_fallback_greeting() 不以毕设开头，先回应岗位要求

## 语法与配置验证
- [x] python ast.parse 语法检查通过
- [x] 配置加载验证通过（core_stack 和 ui_ux proof_points 输出符合简历）
