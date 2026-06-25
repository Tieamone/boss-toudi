# Tasks

## 阶段一：校正 RESUME_BASE_FACTS

- [x] Task 1: 校正 RESUME_BASE_FACTS 为简历真实信息
  - 修改 `boss_auto_apply.py` 中 `RESUME_BASE_FACTS`（第 182-186 行）
  - summary 改为："2026届武汉生物工程学院视觉传达设计本科，作品风格偏向简洁、柔和、低饱和和情绪化表达；作品集涵盖 UI 界面设计（余光APP）、品牌视觉识别（甜序低糖甜品）、信息可视化（全球文化迁徙史）等方向。"
  - core_stack 改为："Photoshop、Illustrator、After Effects、Adobe XD、剪映，以及 GPT-image2、Nano Banana、即梦、豆包、lovart 等 AI 设计工具。"
  - communication_rules 追加："JD中未掌握的能力以愿意学习方向表达，不硬说自己做过。"
  - 验证：三个字段严格反映简历真实信息

## 阶段二：校正 RESUME_PROFILES 各画像

- [x] Task 2: 校正 ui_ux 画像
  - 修改 `boss_auto_apply.py` 中 `RESUME_PROFILES["ui_ux"]`（第 189-204 行）
  - skills 改为："Photoshop、Illustrator、After Effects、Adobe XD、剪映、用户调研、信息架构、低保真/高保真原型、IP形象设计。"
  - proof_points 改为：
    1. "「余光」APP：心理健康疗愈类应用，完成用户调研、竞品分析、视觉风格设定、界面设计、IP形象设计及文创延展。"
    2. "功能模块：情绪记录、即时干预、匿名社交、IP陪伴，通过低饱和色彩、水彩插画、圆角界面降低用户心理压力。"
    3. "设计产出：主界面、启动页、引导页、底部导航、低保真/高保真原型、IP三视图、IP表情包、钥匙扣、帆布袋、明信片、抱枕、贴纸。"
  - campus_pitch 改为："应届口径：做过一款心理健康疗愈类APP「余光」，从用户调研、竞品分析到视觉风格设定、界面设计、IP形象设计完整走了一遍流程，通过低饱和色彩和水彩插画降低用户心理压力。"
  - experienced_pitch 改为："项目经历口径：突出「余光」APP完整设计流程、用户调研到高保真原型交付、IP形象设计能力，不主动强调学生身份。"
  - 验证：余光 APP 功能模块、产出、IP 形象均与简历一致

- [x] Task 3: 校正 brand_visual 画像
  - 修改 `boss_auto_apply.py` 中 `RESUME_PROFILES["brand_visual"]`（第 205-220 行）
  - skills 改为："Photoshop、Illustrator、品牌命名定位、Logo设计、色彩字体规范、VI应用系统设计、品牌延伸展示。"
  - proof_points 改为：
    1. "「甜序」低糖甜品品牌VIS：完成品牌命名、品牌理念、标志设计、标准色规范、辅助图形、字体规范及品牌应用延展。"
    2. "应用系统：包装、菜单、物料、标志规范、标准色规范、标志黑白稿、标志安全空间、最小使用规范。"
    3. "品牌亮点：低饱和绿色与柔和粉色建立清新自然甜美印象，结合甜品、果实、叶片元素形成亲和力品牌识别。"
  - campus_pitch 改为："应届口径：做过一套完整的低糖甜品品牌视觉识别系统「甜序」，从品牌命名、理念、Logo设计到标准色规范、辅助图形、应用延展完整落地。"
  - experienced_pitch 改为："项目经历口径：突出「甜序」品牌VIS全流程落地、从命名到应用系统完整交付、品牌延伸和物料适配能力。"
  - 验证：甜序是"低糖甜品"非"奶茶"，产出与简历一致

- [x] Task 4: 校正 info_visualization 画像
  - 修改 `boss_auto_apply.py` 中 `RESUME_PROFILES["info_visualization"]`（第 221-236 行）
  - skills 改为："Photoshop、Illustrator、信息层级梳理、图表样式设计、版面排版、视觉统一。"
  - proof_points 改为：
    1. "「全球文化迁徙史」信息可视化：通过时间轴、地图、矩阵图、雷达图等可视化方式，将复杂历史信息进行视觉整合与清晰表达。"
    2. "设计亮点：蓝色系视觉语言和多类型图表组合，增强复杂历史信息的阅读效率与视觉秩序感。"
    3. "项目能力：信息层级梳理、图表样式设计、版面排版和整体视觉统一。"
  - campus_pitch 改为："应届口径：做过一个全球文化迁徙史的信息可视化项目，通过时间轴、地图、矩阵图、雷达图等多种图表方式整合复杂历史信息。"
  - experienced_pitch 改为："项目经历口径：突出信息可视化多类型图表组合、信息层级梳理、视觉秩序感能力。"
  - 验证：移除虚构的 IKEA 拆解图、海洋的泪，校正为简历真实信息

- [x] Task 5: 校正 ecommerce_design 画像
  - 修改 `boss_auto_apply.py` 中 `RESUME_PROFILES["ecommerce_design"]`（第 237-252 行）
  - skills 改为："Photoshop、Illustrator、剪映、UI界面设计、品牌视觉识别、版式设计、视觉风格把控。"
  - proof_points 改为：
    1. "可迁移能力：UI界面设计、品牌视觉识别、版式设计能力可迁移到电商详情页和运营视觉设计。"
    2. "设计风格：作品风格偏向简洁、柔和、低饱和和情绪化表达，适合电商视觉及新媒体视觉相关岗位。"
    3. "学习意愿：电商详情页和运营视觉虽无直接项目，但具备快速学习设计工具和持续优化作品的能力。"
  - campus_pitch 改为："应届口径：作品风格偏向简洁柔和，UI界面设计、品牌视觉识别、版式设计能力可以迁移到电商视觉方向，愿意快速学习详情页和运营视觉的专项要求。"
  - experienced_pitch 改为："项目经历口径：突出UI界面设计、品牌视觉识别、版式设计能力的可迁移性，表达愿意学习电商专项要求。"
  - avoid_claims 追加："不要虚构RNW、百雀羚等具体品牌详情页项目经历"
  - 验证：移除虚构的 RNW、百雀羚、产品摄影，改为可迁移能力+学习意愿

- [x] Task 6: 校正 general_visual 画像
  - 修改 `boss_auto_apply.py` 中 `RESUME_PROFILES["general_visual"]`（第 253-270 行）
  - skills 改为："Photoshop、Illustrator、After Effects、Adobe XD、剪映、UI界面设计、品牌视觉识别、版式设计、信息可视化设计、IP形象设计。"
  - proof_points 改为：
    1. "UI界面设计：「余光」心理健康疗愈APP，完成用户调研到高保真原型全流程，含IP形象设计及文创延展。"
    2. "品牌视觉识别：「甜序」低糖甜品品牌VIS，从命名、Logo到标准色规范、应用延展。"
    3. "信息可视化：「全球文化迁徙史」，通过时间轴、地图、矩阵图、雷达图整合复杂历史信息。"
  - campus_pitch 改为："应届口径：作品涵盖UI界面设计、品牌视觉识别、信息可视化等方向，风格偏向简洁柔和低饱和，PS、AI、AE、XD、剪映都比较熟练。"
  - experienced_pitch 改为："项目经历口径：突出多元设计能力、从调研到高保真输出的完整流程把控能力。"
  - 验证：移除虚构的书籍装帧、CD封面、产品摄影，改为简历真实项目

- [x] Task 7: 校正 default 画像
  - 修改 `boss_auto_apply.py` 中 `RESUME_PROFILES["default"]`（第 271-287 行）
  - skills 同 general_visual 校正
  - proof_points 同 general_visual 校正
  - campus_pitch 同 general_visual 校正
  - 验证：default 画像与简历一致

## 阶段三：优化招呼语生成策略

- [x] Task 8: 优化 call_mimo_api() 的 prompt 生成规则
  - 修改 `boss_auto_apply.py` 中 `call_mimo_api()` 的 prompt（第 854-883 行）
  - 调整生成规则结构，从"看到岗位关键要求 → 我做过的相关项目事实 → 能匹配岗位的技术点 → 期待进一步交流"改为：
    "先回应岗位关键要求并匹配我的能力 → 自然引出相关项目证据（不要直接以毕设/在校期间开头）→ 匹配的技术点或愿意学习的方向 → 期待进一步交流"
  - 新增规则："JD中要求但我未掌握的能力，以'愿意学习/可快速上手/之前接触过相关思路'方向表达，不要硬说自己做过"
  - 新增规则："不要直接以'我的毕业设计是...'或'在校期间我做了...'开头，先回应岗位需求再自然引出项目证据"
  - 验证：prompt 规则包含 JD 技术匹配和不直接讲毕设的要求

- [x] Task 9: 优化 _build_local_fallback_greeting() 兜底招呼语
  - 修改 `boss_auto_apply.py` 中 `_build_local_fallback_greeting()`（第 801-816 行）
  - 调整兜底招呼语结构，不再以"我做过{proof}"开头，改为先回应岗位要求再引出证据
  - 改为："看到{target}偏{req_text}，我的{skills}能力可以匹配相关要求，{proof}让我对这类设计有实际理解。期待进一步交流。"
  - 验证：兜底招呼语不直接以毕设开头，先回应岗位要求

## 阶段四：验证

- [x] Task 10: 语法检查与配置加载验证
  - 运行 `python -c "import ast; ast.parse(open('boss_auto_apply.py', encoding='utf-8').read())"` 验证语法正确
  - 运行 `python -c "from boss_auto_apply import RESUME_BASE_FACTS, RESUME_PROFILES; print(RESUME_BASE_FACTS['core_stack']); print(RESUME_PROFILES['ui_ux']['proof_points'])"` 验证配置加载
  - 验证：无语法错误，配置加载输出符合简历真实信息

# Task Dependencies
- Task 1 可独立执行
- Task 2-7 可并行执行（均为 RESUME_PROFILES 各画像修改）
- Task 8, Task 9 可并行执行（均为招呼语策略优化）
- Task 10 依赖所有前置任务完成
