# Tasks

## 阶段一：清空历史日志

- [ ] Task 1: 清空投递记录 CSV 并保留表头
  - 清空 `boss_apply_log.csv` 文件内容，仅保留第一行表头 `time,company,position,salary,city,hr_name,hr_active,status,reason,url,ai_greeting,resume_type`
  - 验证：文件大小应小于 200 字节，仅含表头一行

- [ ] Task 2: 清空运行日志文件
  - 清空 `boss_auto_apply.log` 文件内容（设为空文件）
  - 验证：文件大小为 0 字节

## 阶段二：重写候选人基础事实

- [ ] Task 3: 更新 RESUME_BASE_FACTS 为王文静的视觉传达设计背景
  - 修改 `boss_auto_apply.py` 中 `RESUME_BASE_FACTS`（约第 180-184 行）
  - summary：改为"2026届武汉生物工程学院视觉传达设计专业本科，目标深圳设计类岗位；作品集涵盖 UI/UX（余光APP毕设）、品牌VI（甜序奶茶）、信息可视化、电商详情页、书籍装帧、CD封面、产品摄影等方向。"
  - core_stack：改为"Photoshop、Illustrator、Adobe XD、After Effects、Premiere、Figma、Sketch、CorelDRAW、Indesign。"
  - communication_rules：改为"只使用作品集中存在的项目事实；不主动暴露手机号、邮箱、期望薪资；社招岗位不主动强调在校/应届，但不要编造正式多年工作经历或知名品牌合作经历。"
  - 验证：三个字段内容正确反映视觉传达设计专业背景

## 阶段三：重写 CONFIG 搜索与过滤

- [ ] Task 4: 更新 CONFIG.keywords 为设计类搜索词
  - 修改 `boss_auto_apply.py` 中 `CONFIG["keywords"]`（约第 86-95 行）
  - 改为：`["UI设计", "UX设计", "交互设计", "视觉设计", "品牌设计", "平面设计", "信息可视化", "电商设计", "美工", "平面设计师"]`
  - 验证：关键词列表全部为设计类岗位搜索词

- [ ] Task 5: 更新 CONFIG.skip_keywords 为设计岗不投方向
  - 修改 `boss_auto_apply.py` 中 `CONFIG["skip_keywords"]`（约第 117-134 行）
  - 移除：硬件/电气/芯片、机械/结构、无人机硬件、制造/装配、外包/驻场 等技术岗跳过词
  - 新增：销售、运营、客服、行政、财务、会计、人事、HR、程序员、开发工程师、算法工程师、测试工程师、运维工程师、后端、前端、Java、Python、Android、iOS、嵌入式、硬件、电气、机械、结构工程师 等非设计岗跳过词
  - 保留：外包、驻场、外派
  - 验证：跳过词列表覆盖所有非设计类岗位

- [ ] Task 6: 调整 CONFIG.max_salary_k 为设计岗市场行情
  - 修改 `boss_auto_apply.py` 中 `CONFIG["max_salary_k"]`（约第 137 行）
  - 从 `15` 改为 `12`（设计应届生薪资上限相对较低）
  - 验证：薪资上限值合理

## 阶段四：重写简历画像

- [ ] Task 7: 替换 RESUME_PROFILES 为 5 个设计类画像
  - 修改 `boss_auto_apply.py` 中 `RESUME_PROFILES`（约第 186-315 行）
  - 删除所有计算机画像：android、java_backend、python_ai_app、python_automation、fullstack、frontend、miniapp_uniapp、default
  - 新增 5 个设计画像：
    - `ui_ux`：UI/UX 设计师，match_keywords 含 UI/UX/交互/用户体验/app设计，proof_points 引用「余光」APP 毕设项目（情绪日记、冥想呼吸、匿名漂流瓶、共鸣社区、IP 形象「甜脆」），negative_keywords 含 前端开发/后端/Java/Python/Android
    - `brand_visual`：品牌设计/视觉设计，match_keywords 含 品牌/视觉/VI/CIS/logo，proof_points 引用「甜序」奶茶品牌 VIS 项目，negative_keywords 含 UI 开发/前端/后端
    - `info_visualization`：信息可视化/数据设计，match_keywords 含 信息可视化/数据可视化/信息图/数据设计，proof_points 引用三张信息图（全球文化迁徙史桑基图、IKEA 毕利书柜拆解图、海洋的泪环保科普图），negative_keywords 含 纯插画/纯摄影
    - `ecommerce_design`：电商/运营设计，match_keywords 含 电商/详情页/运营设计/美工/产品摄影，proof_points 引用 RNW 护发精油和百雀羚保湿乳详情页及产品摄影，negative_keywords 含 纯文案/纯运营
    - `general_visual`：综合视觉/平面设计（default 兜底），match_keywords 含 平面设计/视觉传达/海报/包装/书装/CD封面，proof_points 综合引用所有作品，negative_keywords 含 销售/运营/客服/开发
  - 每个画像必须包含完整字段：match_keywords、specific_keywords、preferred_keywords、negative_keywords、target_job、skills、campus_pitch、experienced_pitch、proof_points、avoid_claims
  - 验证：5 个画像字段完整，内容反映作品集真实项目

- [ ] Task 8: 更新 PROFILE_PRIORITY 为设计画像优先级
  - 修改 `boss_auto_apply.py` 中 `PROFILE_PRIORITY`（约第 317-325 行）
  - 改为：`["ui_ux", "brand_visual", "info_visualization", "ecommerce_design", "general_visual"]`
  - 验证：优先级列表与 RESUME_PROFILES 键名一致

## 阶段五：更新岗位需求规则与风险表述

- [ ] Task 9: 更新 _JD_REQUIREMENT_RULES 为设计能力规则
  - 修改 `boss_auto_apply.py` 中 `_JD_REQUIREMENT_RULES`（约第 727-740 行）
  - 删除所有技术栈规则（Java后端、接口开发、数据库、权限、WebSocket、Python、AI应用、自动化、Vue前端、小程序、Android、跨端）
  - 新增设计能力规则：
    - ("UI/UX设计", ("ui", "ux", "交互设计", "用户体验", "app设计", "界面设计", "原型"))
    - ("品牌/VI设计", ("品牌", "vi", "cis", "logo", "标识", "视觉识别"))
    - ("信息可视化", ("信息可视化", "数据可视化", "信息图", "数据设计", "图表"))
    - ("电商/详情页设计", ("电商", "详情页", "运营设计", "美工", "商品设计"))
    - ("平面/海报设计", ("平面", "海报", "宣传", "物料", "画册"))
    - ("包装设计", ("包装", "盒型", "结构设计"))
    - ("书籍装帧", ("书装", "书籍装帧", "排版", "版式"))
    - ("产品摄影", ("摄影", "产品摄影", "拍摄", "修图"))
    - ("插画/IP设计", ("插画", "ip形象", "吉祥物", "卡通"))
    - ("视觉传达", ("视觉传达", "视觉设计", "graphic design"))
  - 验证：规则覆盖所有设计岗位方向

- [ ] Task 10: 更新 _RISKY_AI_CLAIMS 为设计类风险词
  - 修改 `boss_auto_apply.py` 中 `_RISKY_AI_CLAIMS`（约第 742-747 行）
  - 移除技术类风险词：精通、资深、专家、架构师、架构负责人、团队管理、带团队、千万级、百万级、高并发、大流量、分布式、微服务、JVM调优、Nginx、线上故障、故障排查、排障、运维、模型训练、训练模型、微调、LangChain、RAG、向量库
  - 新增设计类风险词：资深设计总监、设计负责人、设计主管、团队管理、带团队、千万级用户、百万级用户、已上架商业App、知名品牌合作、4A广告公司、国际大奖、红点奖、iF设计奖、资深设计师、高级设计师、主设计师、设计总监
  - 保留通用风险词：精通、资深、专家、团队管理、带团队、千万级、百万级
  - 验证：风险词列表覆盖设计类夸大表述

## 阶段六：更新 AI 身份描述与兜底文案

- [ ] Task 11: 更新 call_mimo_api() 中校招/社招身份描述
  - 修改 `boss_auto_apply.py` 中 `call_mimo_api()` 函数（约第 855-872 行）
  - 校招身份：从"你是一名正在求职的应届生"改为"你是一名视觉传达设计专业应届生，需要在Boss直聘上向HR发送第一条打招呼消息。"
  - 社招身份：从"你是一名有Java实习和多个完整项目交付经历的求职者"改为"你是一名有完整作品集的视觉传达设计求职者，需要在Boss直聘上向HR发送第一条打招呼消息。"
  - 校招 extra_hint：保持"可以自然提到应届、实习、可到岗，但不要显得低姿态"，将"重点写项目事实和能上手的技术点"改为"重点写作品集事实和能上手的设计能力点"
  - 社招 extra_hint：保持"不要提及任何学校、在校、应届、实习等字眼"，将"可以说项目经历、开发经历、交付经历"改为"可以说设计项目经历、作品交付经历"，将"不要虚构正式工作年限、公司规模、团队管理、用户量"改为"不要虚构正式工作年限、公司规模、团队管理、知名品牌合作、国际大奖"
  - 验证：身份描述符合视觉传达设计专业背景

- [ ] Task 12: 更新 _build_local_fallback_greeting() 兜底文案
  - 修改 `boss_auto_apply.py` 中 `_build_local_fallback_greeting()` 函数（约第 831-846 行）
  - 将"软件开发"等默认值改为"设计岗位"
  - 将"开发要求"改为"设计要求"
  - 验证：兜底文案符合设计类岗位语境

## 阶段七：更新脚本版本号与入口信息

- [ ] Task 13: 更新脚本顶部注释和版本号
  - 修改 `boss_auto_apply.py` 第 1-11 行
  - 版本号从 v21 改为 v22
  - 更新注释说明本次切换内容：候选人从计算机专业切换为视觉传达设计专业王文静，画像重写为 5 个设计方向，清空历史日志
  - 验证：版本号和注释反映本次变更

- [ ] Task 14: 更新入口打印信息
  - 修改 `boss_auto_apply.py` 中 `if __name__ == "__main__":` 块（约第 2942-2953 行）
  - 将"Boss直聘 自动投递 v21 (智能校招/社招双模式)"改为"Boss直聘 自动投递 v22 (视觉传达设计-王文静)"
  - 验证：入口打印信息正确

## 阶段八：更新文档

- [ ] Task 15: 更新 SCRIPT_INFO_GRAPH.md 设计类示例
  - 修改 `SCRIPT_INFO_GRAPH.md` 中"如何更换使用对象"章节（约第 94-131 行）
  - 将设计类示例从泛指改为当前实际配置：keywords 改为 `["UI设计", "视觉设计", "品牌设计", "平面设计", "信息可视化", "电商设计"]`
  - 更新画像示例为当前 5 个设计画像
  - 验证：文档示例与代码实际配置一致

## 阶段九：验证

- [x] Task 16: 语法检查与运行验证
  - 运行 `python -c "import ast; ast.parse(open('boss_auto_apply.py', encoding='utf-8').read())"` 验证语法正确
  - 运行 `python -c "from boss_auto_apply import CONFIG, RESUME_PROFILES, PROFILE_PRIORITY; print(CONFIG['keywords']); print(list(RESUME_PROFILES.keys())); print(PROFILE_PRIORITY)"` 验证配置加载正确
  - 验证：无语法错误，配置加载输出符合预期

# Task Dependencies
- Task 1, Task 2 可并行执行
- Task 3, Task 4, Task 5, Task 6 可并行执行（均为 CONFIG 或 RESUME_BASE_FACTS 修改）
- Task 7, Task 8 必须顺序执行（Task 8 依赖 Task 7 的画像键名）
- Task 9, Task 10 可并行执行
- Task 11, Task 12 可并行执行
- Task 13, Task 14 可并行执行
- Task 15 依赖 Task 7（需要引用最终画像配置）
- Task 16 依赖所有前置任务完成
