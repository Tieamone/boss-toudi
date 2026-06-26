"""
Boss直聘 自动投递脚本 v22
────────────────────────────────────────────────
v22 更新项：
1. 【切换】候选人从计算机专业龚曦切换为视觉传达设计专业王文静（武汉生物工程学院2026届）
2. 【重写】简历画像重写为 5 个设计方向：UI/UX、品牌视觉、信息可视化、电商设计、综合平面
3. 【更新】搜索关键词、跳过词、岗位需求规则、风险表述清单全部适配设计类岗位
4. 【清理】清空历史投递日志，从零开始新一轮投递
5. 【保留】浏览器启动、登录、卡片抓取、聊天页发送等通用逻辑保持不变
────────────────────────────────────────────────
"""

import time
import random
import re
import csv
import logging
import logging.handlers
import sys
import os
import subprocess
import socket
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from DrissionPage import ChromiumOptions, ChromiumPage
from openai import OpenAI, OpenAIError
import httpx

# ══════════════════════════════════════════════
# 环境变量加载（.env 文件）
# ══════════════════════════════════════════════
def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip().lstrip("\ufeff")
                if key.lower().startswith("export "):
                    key = key[7:].strip()
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                else:
                    value = re.sub(r"\s+#.*$", "", value).strip()
                if key:
                    os.environ[key] = value

_load_env()

def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", "disable", "disabled", "关闭", "禁用"}

_mimo_api_key = os.environ.get("MIMO_API_KEY", "").strip()
_mimo_ai_enabled = _env_bool("MIMO_AI_ENABLED", True)

if not _mimo_api_key:
    print("[INFO] MIMO_API_KEY 未在 .env 中设置，AI 打招呼已关闭")
elif not _mimo_ai_enabled:
    print("[INFO] MIMO_AI_ENABLED=false，AI 打招呼已关闭")

def _normalize_mimo_base_url(raw_url: str) -> str:
    base_url = (raw_url or "https://api.xiaomimimo.com/v1").strip().rstrip("/")
    suffix = "/chat/completions"
    if base_url.endswith(suffix):
        base_url = base_url[: -len(suffix)].rstrip("/")
    return base_url

# ══════════════════════════════════════════════
# 投递配置区
# 换使用对象时优先改这里：
# 1) keywords/city/max_salary_k：目标岗位、城市、薪资上限
# 2) skip_keywords/require_keywords/min_fit_score：过滤边界和精确度
# 3) RESUME_BASE_FACTS/RESUME_PROFILES：候选人事实、画像、证明点和禁用话术
# ══════════════════════════════════════════════
CONFIG = {
    # ── 关键词（短词，覆盖面更广）──────────────────────────────
    "keywords": [
        "电商设计",
        "美工",
        "UI设计",
        "平面设计",
        "信息可视化",
        "视觉设计",
        "剪辑师",
        "产品设计",   
        "ip设计",
        "品牌设计", 
        "文创设计",
        "平面设计师",
    ],

    "city": "深圳",
    "max_apply_per_keyword": 10,
    "max_apply_per_day": 150,

    "apply_interval_min": 2,
    "apply_interval_max": 3,
    "page_turn_interval": (2, 3),

    # ── 校招开关（v20 关闭，不再限制应届）─────────────────────
    "is_campus_recruitment": True,
    "experience_param": "102",         # is_campus_recruitment=True 时才生效

    # ── ★ 最新排序（scene 参数）────────────────────────────────
    # scene=1: 推荐（默认算法排序）
    # scene=3: 最新（按发布时间倒序，手机端「最新」tab对应值）
    # 启动时会自动嗅探验证是否生效，失败则回退 scene=1
    "scene_param": "3",
    "scene_sniff_verify": False,        # True=启动时验证 scene=3 是否真实生效

    # ── 过滤规则──────────────────────────────────────────────
    "skip_keywords": [
        # 非设计类岗位
        "销售", "运营", "客服", "行政", "财务", "会计", "人事", "HR",
        "产品经理", "市场", "采购", "物流", "仓储","游戏ui设计",
        "音效", "音频设计", "声音设计", "游戏音频",
        # 硬件 / 电气 / 机械
        "硬件工程师", "电气工程师", "机械工程师", "结构工程师",
        "电子工程师", "单片机", "PCB", "射频", "芯片",
        "机械", "结构设计",
        # 机械与建筑工程设计
        "机械设计", "结构设计", "模具设计", "暖通设计", "给排水设计", 
        "管道设计", "消防设计", "机电设计", "钢结构设计", "幕墙设计",
        # 软件架构与逻辑
        "架构设计", "数据库设计", "算法设计", "顶层设计", "流程设计",

        # 游戏策划类（游戏行业常把策划称为设计）
        "关卡设计", "数值设计", "系统设计", "战斗设计", "剧情设计",
        # 细分产品设计
        "面料设计", "鞋样设计", "鞋履设计", "箱包设计", "珠宝设计", 
        "首饰设计", "玩具设计", "家具设计", "软装设计", 

        # 容易混淆的边界词
        "包装结构设计", # 注意：区别于你可能要投的"包装视觉设计"或"包装平面设计"    
        # 动画与特效
        "动画设计", "特效设计", "角色设计", "场景设计", "动作设计", "分镜设计",
        "课程设计", "教学设计", "问卷设计", "薪酬设计", "制度设计",
        # 工程/建筑/电路软件
        "CAD", "AutoCAD", "SolidWorks", "ProE", "Creo", "BIM", "Revit", "Altium", "Rhino" ,
        # 电子与半导体设计
        "电路设计", "IC设计", "芯片设计", "PCB设计", "射频设计", "天线设计",    
        # 非视觉设计类（含"设计"但方向不符）
        "工业设计", "服装设计", "男装", "女装", "童装",
        "室内设计", "建筑设计", "环境设计", "园林", "景观",
        "工艺设计", "电气设计", "硬件设计",
        # 机械建模软件
        "ug",
        # 纯剪辑/3D（非综合设计岗）
         "3D建模师",
        # 外包 / 驻场
        "外包", "驻场", "外派",
    ],
    "jd_skip_keywords": [
        # 音频/音效专业软件（出现在JD里说明是音频岗，不是视觉设计）
        "Cubase", "Reaper", "Wwise", "Protools", "Pro Tools", "DAW", "混音", "音效制作", "音频制作",
        # 工程/建筑/电气软件（JD里出现代表岗位需要这类工具）
        "CAD", "AutoCAD", "SolidWorks", "ProE", "Creo", "BIM", "Revit", "Altium", "Rhino",
        # 机械/建筑设计方向词
        "机械设计", "结构设计", "模具设计", "暖通设计", "给排水设计",
        "管道设计", "消防设计", "机电设计", "钢结构设计", "幕墙设计",
        # 非视觉设计方向
        "室内设计", "建筑设计", "环境设计", "园林", "景观",
        "工业设计", "服装设计", "面料设计", "鞋样设计", "鞋履设计",
        "箱包设计", "珠宝设计", "首饰设计", "玩具设计", "家具设计", "软装设计",
        "包装结构设计",
        # 游戏策划类（JD里出现代表是策划岗不是设计岗）
        "关卡设计", "数值设计", "战斗设计", "剧情设计",
        # 电子/半导体
        "电路设计", "IC设计", "芯片设计", "PCB设计", "射频设计", "天线设计",
        "电气设计", "硬件设计",
        # 机械建模软件
        "ug",
        # 外包/驻场
        "外包", "驻场", "外派",
    ],
    "require_keywords": ["设计", "美工", "视觉", "插画"],  # 白名单：职位名必须含其一才投递
    "skip_if_not_active": True,
    "max_salary_k": 15,  # 薪资上限（K），超过此值跳过。设为 0 关闭薪资过滤。
    "min_salary_k": 5,  # 薪资下限（K），低于此值跳过。设为 0 关闭薪资过滤。
    "min_fit_score": 28,  # 岗位适配最低分；越高越精确但会少投，设为 0 关闭适配分过滤。
    "skip_anonymous_headhunter_jobs": True,  # 跳过匿名代招/猎头岗，避免聊天页无法按真实公司校验
    "chat_contact_scan_limit": 8,       # fallback 聊天列表最多检查几项，防止被新消息挤下去后长时间空转
    "allow_company_only_when_hr_unreliable": True,  # 招聘人抓取不可靠时，仅公司校验通过也允许发送
    "anonymous_company_markers": [
        "某大型", "某知名", "某500强", "某上市", "某外企", "某国企",
        "某互联网", "某软件", "某科技", "某集团", "某ICT", "匿名公司",
    ],
    "headhunter_keywords": [
        "猎头", "代招", "人力资源", "人力", "人才", "劳务", "招聘服务",
        "RPO", "科锐", "科锐尔", "科锐国际", "万宝盛华", "外企德科",
        "德科", "中智", "任仕达", "锐仕方达", "伯乐", "前程无忧",
    ],
    "log_file": "boss_apply_log.csv",
    "app_log_file": "boss_auto_apply.log",
    "browser_port": 9222,
    "test_mode": False,
}

# ══════════════════════════════════════════════
# AI 配置区
# ══════════════════════════════════════════════
AI_CONFIG = {
    "api_key": _mimo_api_key,
    "model": os.environ.get("MIMO_MODEL", "mimo-v2.5-pro"),
    "base_url": _normalize_mimo_base_url(
        os.environ.get("MIMO_BASE_URL") or os.environ.get("MIMO_API_URL") or "https://api.xiaomimimo.com/v1"
    ),
    "api_timeout": 120,
    "api_retry": 1,
    "trust_env": _env_bool("MIMO_TRUST_ENV", False),
    "post_send_delay": 2,
    "typing_char_delay": 0.1,
    "blog_url": "http://124.222.207.22/portfolio",
    "enabled": bool(_mimo_api_key) and _mimo_ai_enabled,
    "jd_relevance_filter_enabled": False,
}

# ══════════════════════════════════════════════
# 这些没必要 简历画像配置（依据根目录《龚曦-互联网.pdf》整理）
# 换使用对象时按这个模板改：
# - RESUME_BASE_FACTS：候选人的专业、目标、核心经历、沟通边界
# - 每个 RESUME_PROFILES 条目：岗位方向、匹配词、偏好词、负面词、技能、证据、禁用话术
# - PROFILE_PRIORITY：画像优先级，越靠前越先抢同分岗位
# ══════════════════════════════════════════════
RESUME_BASE_FACTS = {
    "summary": "2026届武汉生物工程学院视觉传达设计本科，作品风格偏向简洁、柔和、低饱和和情绪化表达；作品集涵盖 UI 界面设计（余光APP）、品牌视觉识别（甜序低糖甜品）、信息可视化（全球文化迁徙史）等方向；曾参与亚马逊电商设计实习，了解电商平台视觉规范、产品卖点表达和商业页面设计逻辑；具备基础摄影能力，能辅助完成产品拍摄、素材整理和后期处理。",
    "core_stack": "Photoshop、Illustrator、C4D、After Effects、Adobe XD、剪映，以及 GPT-image2、Nano Banana、Seedream、即梦、豆包、lovart 等 AI 设计工具。",
    "communication_rules": "只使用简历中存在的项目事实；不主动暴露手机号、邮箱、期望薪资；社招岗位不主动强调在校/应届，但不要编造正式多年工作经历或知名品牌合作经历；JD中未掌握的能力以愿意学习方向表达，不硬说自己做过。",
}

RESUME_PROFILES = {
    "ui_ux": {
        "match_keywords": ["ui", "ux", "交互设计", "用户体验", "app设计", "界面设计", "原型设计", "移动端设计"],
        "specific_keywords": ["ui设计", "ux设计", "交互设计", "用户体验", "app设计", "界面设计", "原型", "高保真", "低保真"],
        "preferred_keywords": ["ui", "ux", "交互", "用户体验", "app", "界面", "原型", "xd", "ae", "剪映"],
        "negative_keywords": ["前端开发", "后端", "java", "python", "android", "ios", "嵌入式", "硬件", "算法"],
        "target_job": "UI/UX设计师",
        "skills": "Photoshop、Illustrator、C4D、After Effects、Adobe XD、剪映、用户调研、信息架构、低保真/高保真原型、IP形象设计。",
        "campus_pitch": "应届口径：做过一款心理健康疗愈类APP「余光」，从用户调研、竞品分析到视觉风格设定、界面设计、IP形象设计完整走了一遍流程，通过低饱和色彩和水彩插画降低用户心理压力。",
        "experienced_pitch": "项目经历口径：突出「余光」APP完整设计流程、用户调研到高保真原型交付、IP形象设计能力，不主动强调学生身份。",
        "proof_points": [
            "「余光」APP：心理健康疗愈类应用，完成用户调研、竞品分析、视觉风格设定、界面设计、IP形象设计及文创延展。",
            "功能模块：情绪记录、即时干预、匿名社交、IP陪伴，通过低饱和色彩、水彩插画、圆角界面降低用户心理压力。",
            "设计产出：主界面、启动页、引导页、底部导航、低保真/高保真原型、IP三视图、IP表情包、钥匙扣、帆布袋、明信片、抱枕、贴纸。",
        ],
        "avoid_claims": ["不要声称APP已上架或拥有真实用户量", "不要虚构大型商业项目交付经历", "不要说自己精通前端开发或代码实现"],
    },
    "brand_visual": {
        "match_keywords": ["品牌设计", "视觉设计", "vi", "cis", "logo", "标识", "品牌识别", "品牌视觉"],
        "specific_keywords": ["品牌设计", "视觉设计", "vi设计", "cis", "logo设计", "标识设计", "视觉识别系统", "品牌延伸"],
        "preferred_keywords": ["品牌", "vi", "cis", "logo", "标识", "视觉识别", "品牌延伸", "应用系统", "标准色"],
        "negative_keywords": ["前端开发", "后端", "java", "python", "android", "嵌入式", "硬件", "算法", "纯摄影"],
        "target_job": "品牌设计/视觉设计",
        "skills": "Photoshop、Illustrator、C4D、品牌命名定位、Logo设计、色彩字体规范、VI应用系统设计、品牌延伸展示。",
        "campus_pitch": "应届口径：做过一套完整的低糖甜品品牌视觉识别系统「甜序」，从品牌命名、理念、Logo设计到标准色规范、辅助图形、应用延展完整落地。",
        "experienced_pitch": "项目经历口径：突出「甜序」品牌VIS全流程落地、从命名到应用系统完整交付、品牌延伸和物料适配能力。",
        "proof_points": [
            "「甜序」低糖甜品品牌VIS：完成品牌命名、品牌理念、标志设计、标准色规范、辅助图形、字体规范及品牌应用延展。",
            "应用系统：包装、菜单、物料、标志规范、标准色规范、标志黑白稿、标志安全空间、最小使用规范。",
            "品牌亮点：低饱和绿色与柔和粉色建立清新自然甜美印象，结合甜品、果实、叶片元素形成亲和力品牌识别。",
        ],
        "avoid_claims": ["不要虚构知名品牌合作经历", "不要声称品牌已实际投入商业运营", "不要说自己擅长品牌战略咨询"],
    },
    "info_visualization": {
        "match_keywords": ["信息可视化", "数据可视化", "信息图", "数据设计", "图表设计", "infographic"],
        "specific_keywords": ["信息可视化", "数据可视化", "信息图", "数据设计", "图表", "时间轴", "矩阵图", "雷达图"],
        "preferred_keywords": ["信息可视化", "数据可视化", "信息图", "数据设计", "图表", "时间轴", "矩阵图", "雷达图"],
        "negative_keywords": ["纯插画", "纯摄影", "前端开发", "后端", "java", "python", "数据分析师", "算法"],
        "target_job": "信息可视化/数据设计",
        "skills": "Photoshop、Illustrator、C4D、信息层级梳理、图表样式设计、版面排版、视觉统一。",
        "campus_pitch": "应届口径：做过一个全球文化迁徙史的信息可视化项目，通过时间轴、地图、矩阵图、雷达图等多种图表方式整合复杂历史信息。",
        "experienced_pitch": "项目经历口径：突出信息可视化多类型图表组合、信息层级梳理、视觉秩序感能力。",
        "proof_points": [
            "「全球文化迁徙史」信息可视化：通过时间轴、地图、矩阵图、雷达图等可视化方式，将复杂历史信息进行视觉整合与清晰表达。",
            "设计亮点：蓝色系视觉语言和多类型图表组合，增强复杂历史信息的阅读效率与视觉秩序感。",
            "项目能力：信息层级梳理、图表样式设计、版面排版和整体视觉统一。",
        ],
        "avoid_claims": ["不要虚构大数据可视化平台项目", "不要声称有专业数据分析或统计建模经验", "不要说自己精通D3.js或前端可视化开发"],
    },
    "ecommerce_design": {
        "match_keywords": ["电商设计", "详情页", "运营设计", "美工", "商品设计", "店铺设计"],
        "specific_keywords": ["电商设计", "详情页", "运营设计", "美工", "商品设计", "店铺装修", "卖点提炼"],
        "preferred_keywords": ["电商", "详情页", "运营设计", "美工", "卖点", "版式", "视觉风格"],
        "negative_keywords": ["纯文案", "纯运营", "前端开发", "后端", "java", "python", "算法", "数据分析师"],
        "target_job": "电商/运营设计",
        "skills": "Photoshop、Illustrator、C4D、剪映、UI界面设计、品牌视觉识别、版式设计、视觉风格把控。",
        "campus_pitch": "应届口径：曾参与亚马逊电商设计实习，了解电商平台视觉规范、产品卖点表达和商业页面设计逻辑，具备一定的电商视觉执行能力；UI界面设计、品牌视觉识别、版式设计能力可迁移到电商视觉方向。",
        "experienced_pitch": "项目经历口径：曾参与亚马逊电商设计实习，了解电商平台视觉规范、产品卖点表达和商业页面设计逻辑；UI界面设计、品牌视觉识别、版式设计能力可迁移到电商详情页和运营视觉设计。",
        "proof_points": [
            "亚马逊电商设计实习：了解电商平台视觉规范、产品卖点表达和商业页面设计逻辑，具备一定的电商视觉执行能力。",
            "可迁移能力：UI界面设计、品牌视觉识别、版式设计能力可迁移到电商详情页和运营视觉设计。",
            "设计风格：作品风格偏向简洁、柔和、低饱和和情绪化表达，适合电商视觉及新媒体视觉相关岗位。",
        ],
        "avoid_claims": ["不要虚构千万级GMV或爆款详情页数据", "不要声称有大型电商团队主视觉经验", "不要说自己精通视频剪辑或后期特效", "不要虚构RNW、百雀羚等具体品牌详情页项目经历"],
    },
    "general_visual": {
        "match_keywords": ["平面设计", "视觉传达", "海报", "包装", "画册", "宣传物料"],
        "specific_keywords": ["平面设计", "视觉传达", "海报设计", "包装设计", "画册", "宣传物料", "排版"],
        "preferred_keywords": ["平面", "视觉传达", "海报", "包装", "画册", "物料", "排版", "版式"],
        "negative_keywords": ["销售", "运营", "客服", "行政", "财务", "开发", "硬件", "电气", "机械", "算法"],
        "target_job": "综合视觉/平面设计",
        "skills": "Photoshop、Illustrator、C4D、After Effects、Adobe XD、剪映、UI界面设计、品牌视觉识别、版式设计、信息可视化设计、IP形象设计。",
        "campus_pitch": "应届口径：作品涵盖UI界面设计、品牌视觉识别、信息可视化等方向，风格偏向简洁柔和低饱和，PS、AI、AE、XD、剪映都比较熟练。",
        "experienced_pitch": "项目经历口径：突出多元设计能力、从调研到高保真输出的完整流程把控能力。",
        "proof_points": [
            "UI界面设计：「余光」心理健康疗愈APP，完成用户调研到高保真原型全流程，含IP形象设计及文创延展。",
            "品牌视觉识别：「甜序」低糖甜品品牌VIS，从命名、Logo到标准色规范、应用延展。",
            "信息可视化：「全球文化迁徙史」，通过时间轴、地图、矩阵图、雷达图整合复杂历史信息。",
        ],
        "avoid_claims": ["不要泛泛说学习能力强，必须用作品集事实支撑", "不要虚构大型商业项目或知名品牌合作", "不要声称精通所有设计软件或所有设计领域"],
    },
    "default": {
        "match_keywords": [],
        "specific_keywords": [],
        "preferred_keywords": ["设计", "视觉", "平面", "ui", "品牌", "海报", "包装"],
        "negative_keywords": ["销售", "运营", "客服", "行政", "财务", "硬件", "结构", "电气", "开发", "算法"],
        "target_job": "视觉传达设计",
        "skills": "Photoshop、Illustrator、C4D、After Effects、Adobe XD、剪映、UI界面设计、品牌视觉识别、版式设计、信息可视化设计、IP形象设计。",
        "campus_pitch": "应届口径：作品涵盖UI界面设计、品牌视觉识别、信息可视化等方向，风格偏向简洁柔和低饱和，PS、AI、AE、XD、剪映都比较熟练。",
        "experienced_pitch": "项目经历口径：突出多元设计能力、从调研到高保真输出的完整流程把控能力。",
        "proof_points": [
            "UI界面设计：「余光」心理健康疗愈APP，完成用户调研到高保真原型全流程，含IP形象设计及文创延展。",
            "品牌视觉识别：「甜序」低糖甜品品牌VIS，从命名、Logo到标准色规范、应用延展。",
            "信息可视化：「全球文化迁徙史」，通过时间轴、地图、矩阵图、雷达图整合复杂历史信息。",
        ],
        "avoid_claims": ["不要泛泛说学习能力强，必须用作品集事实支撑"],
    },
}

PROFILE_PRIORITY = [
    "ui_ux",
    "brand_visual",
    "info_visualization",
    "ecommerce_design",
    "general_visual",
]

# ══════════════════════════════════════════════
# 城市代码映射
# ══════════════════════════════════════════════
CITY_CODES = {
    "北京": "101010100", "上海": "101020100", "深圳": "101280600",
    "广州": "101280100", "杭州": "101210100", "成都": "101270100",
    "武汉": "101200100", "南京": "101190100", "西安": "101110100",
    "重庆": "101040100", "天津": "101030100", "苏州": "101190400",
}

# ══════════════════════════════════════════════
# 日志（带轮转）
# ══════════════════════════════════════════════
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

if not log.hasHandlers():
    _stream_handler = logging.StreamHandler()
    _stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    log.addHandler(_stream_handler)

    _file_handler = logging.handlers.RotatingFileHandler(
        CONFIG.get("app_log_file", "boss_auto_apply.log"), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    _file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    log.addHandler(_file_handler)


RUN_PID_FILE = Path(__file__).with_name("boss_auto_apply.pid")

def _read_run_pid() -> int | None:
    try:
        raw = RUN_PID_FILE.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except Exception:
        return None

def _claim_single_instance() -> int:
    current_pid = os.getpid()
    old_pid = _read_run_pid()
    if old_pid and old_pid != current_pid:
        log.warning(f"Found previous boss_auto_apply.py pid={old_pid}; terminating it before start...")
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(old_pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            else:
                os.kill(old_pid, 9)
            time.sleep(1)
        except Exception as e:
            log.warning(f"Failed to terminate previous pid={old_pid}: {e}")
    RUN_PID_FILE.write_text(str(current_pid), encoding="utf-8")
    return current_pid

def _release_single_instance(pid: int):
    if _read_run_pid() != pid:
        return
    try:
        RUN_PID_FILE.unlink()
    except FileNotFoundError:
        pass


class MiMoAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None,
                 error_code: str = "", response_text: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response_text = response_text


@dataclass
class JobRecord:
    time: str = ""
    company: str = ""
    position: str = ""
    salary: str = ""
    city: str = ""
    hr_name: str = ""
    hr_active: str = ""
    status: str = ""
    reason: str = ""
    url: str = ""
    ai_greeting: str = ""
    resume_type: str = ""

# ══════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════
_BOSS_DIGIT_TRANSLATION = str.maketrans({
    chr(0xE031 + i): str(i) for i in range(10)
})

def _decode_boss_obfuscated_digits(text: str) -> str:
    return str(text or "").translate(_BOSS_DIGIT_TRANSLATION)

def detect_browser():
    candidates = []
    if sys.platform == "win32":
        username = os.environ.get("USERNAME", "")
        appdata = os.environ.get("LOCALAPPDATA", f"C:\\Users\\{username}\\AppData\\Local")
        edge_data = os.path.join(appdata, "Microsoft", "Edge", "User Data")
        candidates.extend([
            (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", edge_data),
            (r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", edge_data),
        ])
    for exe, data_dir in candidates:
        if os.path.exists(exe):
            return exe, data_dir
    return None, None

def _get_text(ele) -> str:
    try:
        return _decode_boss_obfuscated_digits(ele.text.strip()) if ele else ""
    except Exception:
        return ""

def _get_full_text(ele) -> str:
    if not ele:
        return ""
    try:
        result = ele.run_js("return this.textContent.trim()")
        text = str(result).strip() if result else ""
        return _decode_boss_obfuscated_digits(text if text else _get_text(ele))
    except Exception:
        return _get_text(ele)

def _parse_salary_upper_bound_k(salary_text: str) -> float | None:
    salary_text = _decode_boss_obfuscated_digits(salary_text)
    if not salary_text:
        return None
    if "面议" in salary_text or "元/天" in salary_text or "未知" in salary_text:
        return None
    if "薪" in salary_text and "K" not in salary_text.upper():
        return None
    numbers = re.findall(r'(\d+(?:\.\d+)?)\s*[Kk]', salary_text)
    if numbers:
        return max(float(n) for n in numbers)
    return None

def _strip_salary_from_position(position: str) -> str:
    """从职位名中剥离薪资相关子串（底薪、K区间、面议、元/天月等）。"""
    text = str(position or "")
    if not text:
        return text
    patterns = [
        r'无责任底薪',
        r'底薪',
        r'\d+(?:\.\d+)?\s*[Kk]?\s*[-–~]\s*\d+(?:\.\d+)?\s*[Kk]',
        r'\d+(?:\.\d+)?\s*[Kk]',
        r'面议',
        r'\d+\s*元/[天月]',
        r'元/[天月]',
        r'薪资\d+',
    ]
    cleaned = text
    for pat in patterns:
        cleaned = re.sub(pat, '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else text

def select_resume_profile(position: str, company: str, job_desc: str,
                           search_keyword: str = "") -> tuple:
    """
    选择最匹配的简历画像。
    搜索词用于定大方向，职位名和JD里的具体技术词用于细分画像。
    """
    sk = search_keyword.lower().strip()
    pos_lower = position.lower()
    combined = (company + " " + job_desc[:300]).lower()

    best_key = "default"
    best_score = 0
    best_reason = ""
    for profile_key in PROFILE_PRIORITY:
        profile = RESUME_PROFILES[profile_key]
        score = 0
        reasons = []

        for kw in profile.get("match_keywords", []):
            kw_l = kw.lower()
            if sk and kw_l in sk:
                score += 12
                reasons.append(f"搜索词:{kw}")
            if kw_l in pos_lower:
                score += 18
                reasons.append(f"职位名:{kw}")
            if kw_l in combined:
                score += 3

        for kw in profile.get("specific_keywords", []):
            kw_l = kw.lower()
            if sk and kw_l in sk:
                score += 18
                reasons.append(f"搜索词强命中:{kw}")
            if kw_l in pos_lower:
                score += 32
                reasons.append(f"职位名强命中:{kw}")
            if kw_l in combined:
                score += 8

        for kw in profile.get("preferred_keywords", []):
            kw_l = kw.lower()
            if sk and kw_l in sk:
                score += 8
                reasons.append(f"搜索词偏好:{kw}")
            if kw_l in pos_lower:
                score += 14
                reasons.append(f"职位名偏好:{kw}")
            if kw_l in combined:
                score += 4

        for kw in profile.get("negative_keywords", []):
            kw_l = kw.lower()
            if kw_l in pos_lower:
                score -= 30
                reasons.append(f"职位名负向:{kw}")
            elif kw_l in combined:
                score -= 8

        if score > best_score:
            best_key = profile_key
            best_score = score
            best_reason = "、".join(reasons[:3]) if reasons else "JD弱命中"

    if best_score > 0:
        log.info(f"    📄 画像匹配: 【{best_key}】← {best_reason}，score={best_score}")
        return best_key, RESUME_PROFILES[best_key]

    log.info("    📄 未命中特定画像，使用默认全栈简历")
    return "default", RESUME_PROFILES["default"]

def _keyword_in_text(keyword: str, text: str, compact_text: str = "") -> bool:
    kw = str(keyword or "").lower().strip()
    if not kw:
        return False
    if kw in text:
        return True
    compact_kw = re.sub(r"\s+", "", kw)
    return bool(compact_kw and compact_text and compact_kw in compact_text)


def calculate_job_fit_score(profile_key: str, profile: dict, position: str,
                            company: str, job_desc: str, salary: str = "",
                            search_keyword: str = "") -> tuple[int, str]:
    """给岗位和当前画像打保守适配分，低分用于 AI 调用前跳过。"""
    title = (position or "").lower()
    jd = (job_desc or "").lower()
    company_text = (company or "").lower()
    search = (search_keyword or "").lower()
    combined = f"{title} {company_text} {jd[:900]}"
    compact_title = re.sub(r"\s+", "", title)
    compact_jd = re.sub(r"\s+", "", jd)
    compact_combined = re.sub(r"\s+", "", combined)
    score = 0
    reasons = []

    def add_hits(keywords, title_points, jd_points, search_points, label):
        nonlocal score
        for kw in keywords or []:
            in_title = _keyword_in_text(kw, title, compact_title)
            in_jd = _keyword_in_text(kw, jd, compact_jd)
            in_search = _keyword_in_text(kw, search)
            if in_title:
                score += title_points
                reasons.append(f"职位{label}:{kw}")
            elif in_search:
                score += search_points
                reasons.append(f"搜索{label}:{kw}")
            elif in_jd:
                score += jd_points

    add_hits(profile.get("match_keywords", []), 14, 2, 8, "命中")
    add_hits(profile.get("specific_keywords", []), 22, 6, 12, "强命中")
    add_hits(profile.get("preferred_keywords", []), 12, 5, 8, "偏好")

    for kw in profile.get("negative_keywords", []):
        if _keyword_in_text(kw, title, compact_title):
            score -= 35
            reasons.append(f"职位负向:{kw}")
        elif _keyword_in_text(kw, jd, compact_jd):
            score -= 12
            reasons.append(f"JD负向:{kw}")

    if search and _keyword_in_text(search_keyword, combined, compact_combined):
        score += 4
    if profile_key != "default" and score > 0:
        score += 4

    salary_upper = _parse_salary_upper_bound_k(salary)
    max_salary = CONFIG.get("max_salary_k", 0)
    if salary_upper is not None and max_salary and salary_upper <= max_salary:
        score += 2

    reason_text = "、".join(dict.fromkeys(reasons[:4])) if reasons else "未命中画像关键词"
    return max(0, score), reason_text

def _api_status_code(error: Exception) -> int | None:
    return getattr(error, "status_code", None)


def _mimo_error_hint(error: Exception) -> str:
    status_code = _api_status_code(error)
    if isinstance(error, MiMoAPIError) and not status_code:
        return "请在 .env 中配置有效的 MIMO_API_KEY；也可以设置 MIMO_AI_ENABLED=false 关闭 AI。"
    if status_code in (401, 403):
        return "请检查 .env 中的 MIMO_API_KEY 是否来自当前 MiMo 套餐，并使用控制台显示的专属 MIMO_BASE_URL。"
    if status_code == 429:
        return "请求频率超限，稍后重试或降低投递速度。"
    if status_code == 400:
        return "请求参数被 MiMo 拒绝，请检查模型名和请求体参数。"
    return ""


def _is_non_retryable_api_error(error: Exception) -> bool:
    return _api_status_code(error) in (400, 401, 403)


_MIMO_CLIENT_CACHE = {}


def _get_mimo_client(timeout: int):
    cache_key = (
        AI_CONFIG.get("base_url"),
        AI_CONFIG.get("api_key"),
        AI_CONFIG.get("trust_env", False),
        timeout,
    )
    client = _MIMO_CLIENT_CACHE.get(cache_key)
    if client:
        return client
    http_client = httpx.Client(
        timeout=timeout,
        trust_env=AI_CONFIG.get("trust_env", False),
    )
    client = OpenAI(
        api_key=AI_CONFIG["api_key"],
        base_url=AI_CONFIG["base_url"],
        timeout=timeout,
        max_retries=0,
        http_client=http_client,
    )
    _MIMO_CLIENT_CACHE[cache_key] = client
    return client


def _call_mimo_api(payload: dict, timeout: int = 25, retries: int = 1) -> dict:
    if not AI_CONFIG.get("api_key"):
        raise MiMoAPIError("MIMO_API_KEY 未配置或已被禁用")

    last_error = None
    for attempt in range(retries + 1):
        try:
            client = _get_mimo_client(timeout)
            completion = client.chat.completions.create(**payload)
            return completion.model_dump()
        except OpenAIError as e:
            last_error = e
            if attempt < retries and not _is_non_retryable_api_error(e):
                log.warning(f"    ⚠️ MiMo API第{attempt+1}次调用失败: {e}，1秒后重试...")
                time.sleep(1)
            else:
                break
        except Exception as e:
            last_error = e
            if attempt < retries:
                log.warning(f"    ⚠️ MiMo API第{attempt+1}次调用失败: {e}，1秒后重试...")
                time.sleep(1)
            else:
                break
    raise last_error or RuntimeError("Unknown MiMo API error")

def is_campus_job(job_desc: str, position: str) -> bool:
    """
    检测岗位是否为校招/应届/实习岗。
    返回 True → 校招岗，用学生版简历
    返回 False → 社招岗，用经验版简历
    """
    combined = (position + " " + job_desc[:500]).lower()
    strong_keywords = [
        "校招", "校园招聘", "应届", "应届生", "应届毕业生",
        "实习生", "可实习", "接受实习", "毕业年级",
        "2026届", "2027届", "2025届", "2028届",
        "26届", "27届", "25届", "28届",
    ]
    weak_keywords = [
        "无经验", "不限经验", "经验不限", "培训", "入职培训",
        "带薪培训", "管培生", "培训生", "储备干部", "定向培养",
    ]
    for kw in strong_keywords:
        if kw.lower() in combined:
            return True
    if re.search(r"(?:20)?2[4-9]\s*届", combined):
        return True
    weak_hit = any(kw.lower() in combined for kw in weak_keywords)
    student_context = any(kw in combined for kw in ["毕业", "毕业生", "学校", "在校", "在校生", "可实习", "实习", "转正"])
    if weak_hit and student_context:
        return True
    return False

def _format_profile_facts(profile: dict, is_campus: bool) -> str:
    pitch_key = "campus_pitch" if is_campus else "experienced_pitch"
    pitch = profile.get(pitch_key) or profile.get("skills", "")
    proof_points = "\n".join(f"- {item}" for item in profile.get("proof_points", []))
    avoid_claims = "\n".join(f"- {item}" for item in profile.get("avoid_claims", []))
    return f"""简历总览：{RESUME_BASE_FACTS['summary']}
通用技能：{RESUME_BASE_FACTS['core_stack']}
沟通边界：{RESUME_BASE_FACTS['communication_rules']}
岗位方向：{profile.get('target_job', '软件开发')}
技能栈：{profile.get('skills', '')}
表达口径：{pitch}
可使用的真实项目证据：
{proof_points}
禁止夸大/不要写：
{avoid_claims}"""

_JD_REQUIREMENT_RULES = [
    ("UI/UX设计", ("ui", "ux", "交互设计", "用户体验", "app设计", "界面设计", "原型", "高保真", "低保真")),
    ("品牌/VI设计", ("品牌", "vi", "cis", "logo", "标识", "视觉识别", "品牌延伸")),
    ("信息可视化", ("信息可视化", "数据可视化", "信息图", "数据设计", "图表", "桑基图", "时间轴")),
    ("电商/详情页设计", ("电商", "详情页", "运营设计", "美工", "商品设计", "店铺设计")),
    ("平面/海报设计", ("平面", "海报", "宣传", "物料", "画册", "排版", "版式")),
    ("包装设计", ("包装", "盒型", "结构设计")),
    ("书籍装帧", ("书装", "书籍装帧", "排版", "版式")),
    ("产品摄影", ("摄影", "产品摄影", "拍摄", "修图", "用光")),
    ("插画/IP设计", ("插画", "ip形象", "吉祥物", "卡通", "角色设计")),
    ("视觉传达", ("视觉传达", "视觉设计", "graphic design", "平面设计")),
]

_RISKY_AI_CLAIMS = (
    "精通", "资深", "专家", "团队管理", "带团队",
    "千万级", "百万级", "高并发", "大流量",
    "资深设计总监", "设计负责人", "设计主管", "设计总监",
    "资深设计师", "高级设计师", "主设计师", "首席设计",
    "已上架商业App", "知名品牌合作", "4A广告公司", "国际大奖",
    "红点奖", "iF设计奖", "IDEA奖", "戛纳",
    "千万级用户", "百万级用户", "爆款详情页", "千万级GMV",
)

def _extract_job_requirements(position: str, job_desc: str, limit: int = 3) -> list[dict]:
    text = f"{position or ''} {job_desc or ''}".lower()
    scored = []
    for label, aliases in _JD_REQUIREMENT_RULES:
        hits = []
        score = 0
        for alias in aliases:
            alias_l = alias.lower()
            if alias_l and alias_l in text:
                hits.append(alias)
                score += 2 if alias_l in (position or "").lower() else 1
        if hits:
            scored.append({"label": label, "aliases": aliases, "hits": hits, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]

def _select_relevant_proof_points(profile: dict, requirements: list[dict], limit: int = 2) -> list[str]:
    proof_points = [str(item).strip() for item in profile.get("proof_points", []) if str(item).strip()]
    if not proof_points:
        return []

    aliases = []
    for requirement in requirements:
        aliases.extend(str(alias).lower() for alias in requirement.get("aliases", ()))

    scored = []
    for index, proof in enumerate(proof_points):
        proof_lower = proof.lower()
        score = sum(1 for alias in aliases if alias and alias in proof_lower)
        scored.append((score, -index, proof))

    matched = [proof for score, _, proof in sorted(scored, reverse=True) if score > 0]
    if len(matched) < limit:
        for proof in proof_points:
            if proof not in matched:
                matched.append(proof)
            if len(matched) >= limit:
                break
    return matched[:limit]

def _match_jd_tools(job_desc: str, core_stack: str) -> list[str]:
    """检索 JD 中提及的、候选人已掌握的工具，返回命中工具列表（含别名匹配）。"""
    if not job_desc or not core_stack:
        return []
    jd_lower = (job_desc or "").lower()

    # 候选人掌握的工具及其常见别名（小写匹配）
    tool_aliases = {
        "Photoshop": ["photoshop", "ps"],
        "Illustrator": ["illustrator", "ai"],
        "C4D": ["c4d", "cinema 4d", "cinema4d"],
        "After Effects": ["after effects", "ae", "aftereffect"],
        "Adobe XD": ["xd", "adobe xd"],
        "剪映": ["剪映"],
        "GPT-image2": ["gpt-image2", "gpt image2", "gptimage2"],
        "Nano Banana": ["nano banana", "nanobanana"],
        "Seedream": ["seedream"],
        "即梦": ["即梦"],
        "豆包": ["豆包"],
        "lovart": ["lovart"],
    }

    # 仅保留 core_stack 中确实出现的工具
    core_lower = core_stack.lower()
    candidate_tools = []
    for tool, aliases in tool_aliases.items():
        if any(alias in core_lower for alias in aliases):
            candidate_tools.append(tool)

    # 检索 JD 中提及的、候选人已掌握的工具
    matched = []
    for tool in candidate_tools:
        aliases = tool_aliases[tool]
        if any(alias in jd_lower for alias in aliases):
            matched.append(tool)
    return matched

def _format_requirements_for_prompt(requirements: list[dict]) -> str:
    if not requirements:
        return "- 未提取到明确技术要求，请围绕职位名和当前画像选择最稳妥的匹配点。"
    return "\n".join(
        f"- {item['label']}（命中：{'、'.join(item.get('hits', [])[:4])}）"
        for item in requirements
    )

def _format_proofs_for_prompt(proof_points: list[str]) -> str:
    if not proof_points:
        return "- 当前画像没有可引用项目证据，只能保守表达技能匹配，不要扩写经历。"
    return "\n".join(f"- {item}" for item in proof_points)

def _message_mentions_job_requirement(message: str, requirements: list[dict]) -> bool:
    if not requirements:
        return True
    message_lower = (message or "").lower()
    for requirement in requirements:
        if any(str(alias).lower() in message_lower for alias in requirement.get("aliases", ())):
            return True
        label = str(requirement.get("label", "")).lower()
        if label and label in message_lower:
            return True
    return False

def _validate_ai_greeting(message: str, requirements: list[dict]) -> tuple[bool, str]:
    if not message:
        return False, "空内容"
    for risky in _RISKY_AI_CLAIMS:
        if risky.lower() in message.lower():
            return False, f"包含风险表述：{risky}"
    if not _message_mentions_job_requirement(message, requirements):
        labels = "、".join(item["label"] for item in requirements)
        return False, f"未回应岗位关键词：{labels}"
    return True, ""

def _shorten_text(text: str, max_len: int = 72) -> str:
    text = re.sub(r"\s+", "", str(text or "")).strip("。；;，, ")
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip("。；;，, ") + "。"

def _build_local_fallback_greeting(position: str, profile: dict,
                                   requirements: list[dict],
                                   proof_points: list[str],
                                   is_campus: bool = True) -> str:
    target = _shorten_text(position or profile.get("target_job", "视觉设计岗位"), 24)
    req_text = "、".join(item["label"] for item in requirements[:2]) or "品牌视觉、UI界面设计、信息可视化"
    skills = _shorten_text(profile.get("skills", ""), 42)

    if is_campus:
        opening = f"您好，我是2026届视觉传达设计本科生，想应聘贵公司的{target}岗位。"
    else:
        opening = f"您好，我具备视觉传达设计背景，想应聘贵公司的{target}岗位。"

    body = (
        f"{opening}\n"
        f"我会使用 Photoshop、Illustrator、C4D、AE、XD、剪映等设计工具，"
        "也能结合 GPT-image2、Nano Banana、Seedream 等 AI 工具进行创意发散、视觉生成、素材优化和设计提效。\n"
        f"我的作品方向包含{req_text}等内容，具备一定的版式设计、色彩搭配、视觉风格统一和品牌调性把控能力，"
        "也希望有机会加入团队参与实际项目。\n"
        "期待能进一步沟通，谢谢！"
    )

    return body

def _append_blog_url(message: str) -> str:
    message = str(message or "").strip()
    blog_url = AI_CONFIG["blog_url"]
    if blog_url in message:
        return message
    return f"{message}\n作品集地址：{blog_url}"

def call_mimo_api(job_desc: str, profile: dict, is_campus: bool = True,
                  position: str = "", company: str = "") -> str:
    if not AI_CONFIG["enabled"]:
        return ""

    # 根据校招/社招切换身份描述和 AI 提示
    if is_campus:
        identity = "你是一名2026届视觉传达设计本科应届生，需要在Boss直聘上向HR发送第一条打招呼消息。"
        opening_rule = '招呼语正文必须以「您好，我是2026届视觉传达设计本科生，想应聘贵公司的{position}岗位。」开头。'
        extra_hint = (
            "- 可以自然提到应届、实习、可到岗，但不要显得低姿态\n"
            "- 重点写作品集事实和能上手的设计能力点\n"
        )
    else:
        identity = "你是一名有完整作品集的视觉传达设计求职者，需要在Boss直聘上向HR发送第一条打招呼消息。"
        opening_rule = '招呼语正文必须以「您好，我具备视觉传达设计背景，想应聘贵公司的{position}岗位。」开头。'
        extra_hint = (
            "- 不要提及任何学校、在校、应届、实习等字眼\n"
            "- 可以说设计项目经历、作品交付经历，但不要虚构正式工作年限、公司规模、团队管理、知名品牌合作、国际大奖\n"
        )
    profile_facts = _format_profile_facts(profile, is_campus)
    requirements = _extract_job_requirements(position, job_desc)
    relevant_proofs = _select_relevant_proof_points(profile, requirements)
    matched_tools = _match_jd_tools(job_desc, RESUME_BASE_FACTS.get("core_stack", ""))
    matched_tools_text = "、".join(matched_tools) if matched_tools else "无明确命中"
    fallback_message = _build_local_fallback_greeting(position, profile, requirements, relevant_proofs, is_campus)
    log.info(
        "    🧩 岗位关键词: "
        + ("、".join(item["label"] for item in requirements) if requirements else "未提取到明确关键词")
    )

    prompt = f"""{identity}

【目标岗位】
公司：{company or "目标公司"}
职位：{position or profile.get('target_job', '视觉传达设计')}

【岗位关键要求（必须优先回应）】
{_format_requirements_for_prompt(requirements)}

【JD 中提及且我已掌握的工具（着重讲）】
{matched_tools_text}

【真实项目证据（仅供理解背景，不得在招呼语中提及项目名）】
{_format_proofs_for_prompt(relevant_proofs)}

【我的能力画像】
{profile_facts}

【目标职位描述】
{job_desc[:800]}

【输出格式（严格遵守）】
只输出一段招呼语正文（约200-280字），按以下四段结构生成：
1. 自我介绍 + 「想应聘贵公司的{position or profile.get('target_job', '视觉传达设计')}岗位」
2. 工具能力：列出我会的设计工具（Photoshop、Illustrator、C4D、After Effects、Adobe XD、剪映）和 AI 工具（GPT-image2、Nano Banana、Seedream、即梦、豆包、lovart），并说明用途（创意发散、视觉生成、素材优化、设计提效）。JD 中命中的工具着重讲。
3. 作品方向与能力：列出设计方向（品牌视觉、包装物料、App UI设计、信息可视化、海报及视觉延展等），体现版式设计、色彩搭配、视觉风格统一和品牌调性把控能力。不要提及具体项目名称。
4. 对岗位具体工作的兴趣 + 期待进一步沟通，谢谢。
{opening_rule}

【生成规则】
- {opening_rule}
- 必须使用上方「目标岗位」中的实际职位名「{position or profile.get('target_job', '视觉传达设计')}」填充「想应聘贵公司的XX岗位」，不得使用「视觉设计/品牌设计/电商设计/UI设计相关岗位」等硬编码列表
- JD 中提及且我已掌握的工具着重讲；我不会的工具不要编造，以「愿意学习」方向表达
- 不要在招呼语中提及具体项目名称（如「余光」「甜序」等作品集项目名），只概括列设计方向
- 不要直接以「我的毕业设计是…」或「在校期间我做了…」开头
- 只写证据中已经出现的经历和能力；JD里有但证据里没有的能力，不要硬说自己做过
- 不要堆砌技能名，不要写成简历摘要，不要像模板
- 不要出现「精通」「资深」「负责过千万级/高并发」等无法证明的夸大表述
{extra_hint}- 不要加任何额外解释，直接输出一段内容

请直接输出打招呼消息（仅正文一段）："""

    system_prompt = (
        "你是正在 Boss 直聘求职的设计师本人，要根据简历事实给 HR 写第一条打招呼消息。"
        "严格按用户要求输出中文 Boss 直聘首条沟通消息（仅正文一段），不要输出额外解释。"
        "以求职者第一人称、口语化、自然真诚的语气输出，不暴露 AI 身份，"
        "不出现\"作为 AI\"\"我是 AI 助手\"等表述。"
        "不要使用\"你好\"\"您好\"等问候语开头，直接进入正文内容。"
    )
    payload = {
        "model": AI_CONFIG["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": 4096,
        "temperature": 0.8,
        "top_p": 0.95,
        "stream": False,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    }
    try:
        result = _call_mimo_api(payload, timeout=AI_CONFIG.get("api_timeout", 25),
                                retries=AI_CONFIG.get("api_retry", 1))
        choice = result["choices"][0]
        raw_message = choice.get("message") or {}
        message = (raw_message.get("content") or "").strip()
        message = re.sub(r"<think>.*?</think>", "", message, flags=re.IGNORECASE | re.DOTALL).strip()
        message = re.sub(r"^```(?:text|markdown)?\s*|\s*```$", "", message, flags=re.IGNORECASE).strip()
        message = re.sub(r"\s+", " ", message).strip()
        if not message:
            usage = result.get("usage") or {}
            completion_details = usage.get("completion_tokens_details") or {}
            finish_reason = choice.get("finish_reason")
            log.warning(
                "    ⚠️ MiMo返回空内容: "
                f"finish_reason={finish_reason} "
                f"completion_tokens={usage.get('completion_tokens')} "
                f"reasoning_tokens={completion_details.get('reasoning_tokens')}"
            )
            if finish_reason == "length":
                log.warning(
                    "    ⚠️ 诊断：reasoning 模型思考 token 占用过多，正文无 token 输出。"
                    "如仍失败请进一步增大 max_completion_tokens 或更换非 reasoning 模型。"
                )
            log.info("    🧯 使用本地兜底招呼语：AI返回空内容")
            return fallback_message

        is_valid, invalid_reason = _validate_ai_greeting(message, requirements)
        if not is_valid:
            log.warning(f"    ⚠️ AI招呼语校验未通过: {invalid_reason}")
            log.info("    🧯 使用本地兜底招呼语")
            return fallback_message

        return message
    except Exception as e:
        hint = _mimo_error_hint(e)
        log.warning(f"    ⚠️ AI API调用失败: {e}")
        if hint:
            log.warning(f"    ⚠️ {hint}")
        log.info("    🧯 使用本地兜底招呼语：AI调用失败")
        return fallback_message

def judge_job_relevance_by_ai(position: str, company: str, job_desc: str,
                              core_stack: str) -> tuple[bool, str, list]:
    """调用 mimo 模型判断岗位 JD 是否与候选人掌握的工具/能力相关。
    返回 (是否相关, 原因, 命中的未掌握工具列表)。
    API 失败时默认放行（返回 True），不阻断投递。
    """
    if not AI_CONFIG["enabled"]:
        return True, "AI未启用，默认放行", []
    if not job_desc or not job_desc.strip():
        return True, "JD为空，默认放行", []

    prompt = f"""你是一个求职筛选助手。请根据以下岗位信息，判断该岗位是否与候选人掌握的工具和能力相关。

【候选人掌握的工具栈】
{core_stack}

【目标岗位】
公司：{company or "目标公司"}
职位：{position or "未知职位"}

【职位描述（JD）】
{job_desc[:800]}

【判断规则】
1. 如果 JD 核心要求包含候选人不掌握的工具（如 CAD、3D Max、酷家乐、SolidWorks、UG、ProE、Creo、Revit、BIM、Rhino、AutoCAD、SketchUp、V-Ray、KeyShot、ZBrush、Blender、Maya 等三维/工程/建筑软件），判定为"无关"。
2. 如果岗位方向是室内设计、建筑设计、机械设计、工业设计、服装设计、景观设计、环境设计、结构设计等与视觉传达设计不符的方向，判定为"无关"。
3. 如果 JD 要求的主要工具均在候选人掌握范围内（Photoshop、Illustrator、C4D、After Effects、Adobe XD、剪映，以及 GPT-image2、Nano Banana、Seedream、即梦、豆包、lovart 等 AI 设计工具），判定为"相关"。
4. 如果 JD 主要要求匹配候选人能力，仅在"加分项/了解即可"中提到候选人不掌握的工具，判定为"相关"。
5. 候选人是视觉传达设计方向，擅长平面、品牌、UI、电商、信息可视化等视觉设计。

【输出格式（严格遵守）】
第一行：通过 或 跳过（通过=相关，跳过=无关）
第二行：原因（一句话说明）
第三行：未掌握的工具列表（用顿号分隔，若无则写"无"）

只输出这三行，不要输出任何其他内容。"""

    system_prompt = (
        "你是求职筛选助手，负责判断岗位 JD 与候选人能力是否匹配。"
        "严格按照指定格式输出三行内容，不要输出额外解释。"
    )
    payload = {
        "model": AI_CONFIG["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": 512,
        "temperature": 0.3,
        "top_p": 0.9,
        "stream": False,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    }
    try:
        result = _call_mimo_api(payload, timeout=AI_CONFIG.get("api_timeout", 25),
                                retries=AI_CONFIG.get("api_retry", 1))
        choice = result["choices"][0]
        raw_message = (choice.get("message") or {}).get("content") or ""
        message = raw_message.strip()
        message = re.sub(r"<think>.*?</think>", "", message, flags=re.IGNORECASE | re.DOTALL).strip()
        message = re.sub(r"^```(?:text|markdown)?\s*|\s*```$", "", message, flags=re.IGNORECASE).strip()

        if not message:
            log.warning("    ⚠️ AI JD相关性判断返回空内容，默认放行")
            return True, "AI返回空内容，默认放行", []

        lines = [ln.strip() for ln in message.splitlines() if ln.strip()]
        if not lines:
            return True, "AI输出无法解析，默认放行", []

        verdict_line = lines[0]
        is_relevant = "跳过" not in verdict_line and ("通过" in verdict_line or "相关" in verdict_line)
        reason = lines[1] if len(lines) > 1 else ""
        missing_tools_str = lines[2] if len(lines) > 2 else "无"
        missing_tools = [t.strip() for t in re.split(r"[、,，]", missing_tools_str) if t.strip() and t.strip() != "无"]

        if not is_relevant:
            log.info(f"    🚫 AI判定JD不相关：{reason}（未掌握工具：{missing_tools_str}）")
        else:
            log.info(f"    ✅ AI判定JD相关：{reason}")
        return is_relevant, reason, missing_tools
    except Exception as e:
        hint = _mimo_error_hint(e)
        log.warning(f"    ⚠️ AI JD相关性判断调用失败: {e}")
        if hint:
            log.warning(f"    ⚠️ {hint}")
        log.info("    🧯 AI判断失败，默认放行")
        return True, "AI判断接口失败，默认放行", []

# ══════════════════════════════════════════════
# 主类
# ══════════════════════════════════════════════
class BossApplier:
    def __init__(self, config: dict):
        self.cfg = config
        self.total_applied = 0
        self.daily_applied = 0
        self.log_path = Path(self.cfg["log_file"])
        self.port = self.cfg.get("browser_port", 9222)
        self.applied_history = set()
        self.skipped_history = set()
        self._record_buffer = []
        self._fragment_cache = {}
        self._active_score_cache = {}
        # 实际使用的 scene 参数（嗅探验证后可能回退为 "1"）
        self.active_scene = self.cfg.get("scene_param", "1")
        self._init_log_file()
        self._load_history()

    def _init_log_file(self):
        fields = list(JobRecord.__dataclass_fields__.keys())
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            with open(self.log_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
            return

        try:
            with open(self.log_path, "r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            if not rows:
                with open(self.log_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                return

            first_row = [col.strip("\ufeff") for col in rows[0]]
            has_header = {"company", "position", "status"}.issubset(set(first_row))
            if has_header and first_row == fields:
                return

            normalized_rows = []
            source_fields = first_row if has_header else fields
            data_rows = rows[1:] if has_header else rows
            for values in data_rows:
                if not any(str(v).strip() for v in values):
                    continue
                row = dict(zip(source_fields, values + [""] * max(0, len(source_fields) - len(values))))
                normalized_rows.append({field: row.get(field, "") for field in fields})

            with open(self.log_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(normalized_rows)

            if has_header:
                log.info("🧾 已升级历史记录表头并补齐新字段")
            else:
                log.info("🧾 已为历史记录文件补写表头")
        except Exception as e:
            log.warning(f"⚠️ 检查/修复历史记录表头失败: {e}")

    def _load_history(self):
        if self.log_path.exists():
            try:
                fields = list(JobRecord.__dataclass_fields__.keys())
                with open(self.log_path, "r", encoding="utf-8-sig", newline="") as f:
                    raw_rows = list(csv.reader(f))

                if not raw_rows:
                    log.info("🗂️  本地历史为空")
                    return

                first_row = [col.strip("\ufeff") for col in raw_rows[0]]
                has_header = {"company", "position", "status"}.issubset(set(first_row))
                data_rows = raw_rows[1:] if has_header else raw_rows
                if not has_header:
                    log.warning("⚠️ 历史记录文件缺少表头，已按旧版字段顺序兼容加载")

                loaded_rows = 0
                today = datetime.now().strftime("%Y-%m-%d")
                today_applied = 0
                for values in data_rows:
                    if not any(str(v).strip() for v in values):
                        continue
                    if has_header:
                        row = dict(zip(first_row, values + [""] * max(0, len(first_row) - len(values))))
                    else:
                        row = dict(zip(fields, values + [""] * max(0, len(fields) - len(values))))

                    company = (row.get("company") or "").strip()
                    position = (row.get("position") or "").strip()
                    status = (row.get("status") or "").strip()
                    if not company or not position:
                        continue
                    key = (company, position)
                    loaded_rows += 1
                    if status == "applied":
                        self.applied_history.add(key)
                        if (row.get("time") or "").strip().startswith(today):
                            today_applied += 1
                    if status == "skipped":
                        self.skipped_history.add(key)
                self.daily_applied = today_applied
                log.info(
                    f"🗂️  已加载本地历史: {len(self.applied_history)} 已投递 / {len(self.skipped_history)} 已跳过"
                    f"（扫描 {loaded_rows} 条，今日已投递 {self.daily_applied} 条）"
                )
            except Exception as e:
                log.warning(f"⚠️ 加载历史记录失败: {e}")

    def _save_record(self, record: JobRecord):
        self._record_buffer.append(record)
        if record.status == "applied":
            self.applied_history.add((record.company, record.position))
        if record.status == "skipped":
            self.skipped_history.add((record.company, record.position))
        if len(self._record_buffer) >= 10:
            self._flush_records()

    def _flush_records(self):
        if not self._record_buffer:
            return
        with open(self.log_path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(JobRecord.__dataclass_fields__.keys()))
            for record in self._record_buffer:
                writer.writerow(asdict(record))
        self._record_buffer.clear()

    def _delay(self, min_s: float, max_s: float):
        time.sleep(random.uniform(min_s, max_s))

    def _is_port_open(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            return s.connect_ex(("127.0.0.1", self.port)) == 0

    def _wait_debug_port(self, seconds: int = 20) -> bool:
        for _ in range(seconds):
            if self._is_port_open():
                return True
            time.sleep(1)
        return False

    def _launch_edge_with_profile(self, exe_path: str, user_data_dir: str) -> bool:
        os.makedirs(user_data_dir, exist_ok=True)
        cmd = [exe_path, f"--remote-debugging-port={self.port}",
               f"--user-data-dir={user_data_dir}", "--no-first-run", "--no-default-browser-check"]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self._wait_debug_port()

    def _close_edge_before_launch(self) -> bool:
        if sys.platform != "win32":
            return True
        log.warning("Closing existing Edge processes before automation launch...")
        try:
            subprocess.run(
                ["taskkill", "/IM", "msedge.exe", "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
        except Exception as e:
            log.warning(f"Failed to close Edge processes cleanly: {e}")

        time.sleep(2)
        deadline = time.time() + 10
        while time.time() < deadline:
            if not self._is_port_open():
                return True
            time.sleep(0.5)
        log.error(f"Port {self.port} is still occupied after closing Edge.")
        return False

    def _launch_browser(self):
        if not self._close_edge_before_launch():
            return False
        if self._is_port_open():
            log.error(f"Port {self.port} is occupied before Edge launch.")
            return False
        if self._is_port_open():
            log.info(f"端口 {self.port} 已被占用，直接接管...")
            return True
        exe_path, user_data_dir = detect_browser()
        if not exe_path:
            log.error("未找到 Edge 浏览器！")
            return False
        log.info("正在启动 Edge 浏览器...")
        if self._launch_edge_with_profile(exe_path, user_data_dir):
            return True

        log.error("浏览器启动超时！")
        return False

    def _ensure_logged_in(self, max_wait: int = 120) -> bool:
        log.info("检查 Boss直聘 登录状态...")
        self.main_tab.get("https://www.zhipin.com/web/geek/job")
        self._delay(2, 4)
        deadline = time.time() + max_wait
        while time.time() < deadline:
            is_logged_in = (self.main_tab.ele("css:.user-nav", timeout=1)
                            or self.main_tab.ele("css:.nav-figure", timeout=1))
            if is_logged_in:
                log.info("✅ 检测到已登录！")
                return True
            else:
                log.info("⏳ 尚未登录，请在浏览器中完成扫码/密码登录...")
                time.sleep(5)
        log.error(f"❌ 登录等待超时({max_wait}s)，请检查浏览器状态后重试")
        return False

    # ══════════════════════════════════════════
    # ★ 新增：scene=3 嗅探验证
    # ══════════════════════════════════════════
    def _sniff_and_verify_scene(self):
        """
        监听 joblist.json 接口，验证 scene=3 是否真实生效（返回的数据是否与 scene=1 不同）。
        方法：分别加载 scene=1 和 scene=3 各一次，比较返回的第一条职位 encryptJobId。
        如果两次结果不同 → scene=3 生效；如果相同 → 后端可能不区分，回退 scene=1。
        """
        if not self.cfg.get("scene_sniff_verify", True):
            log.info(f"⏭  跳过 scene 验证，直接使用 scene={self.active_scene}")
            return

        city_code = CITY_CODES.get(self.cfg["city"], "101280600")
        test_kw = self.cfg["keywords"][0]

        log.info("🔬 开始验证 scene=3（最新排序）是否与 scene=1（推荐）结果不同...")

        def _fetch_first_job_id(scene: str) -> str:
            url = f"https://www.zhipin.com/web/geek/job?query={test_kw}&city={city_code}&scene={scene}"
            try:
                self.main_tab.listen.start("wapi/zpgeek/search/joblist.json")
                self.main_tab.get(url)
                resp = self.main_tab.listen.wait(timeout=10)
                self.main_tab.listen.stop()
                if resp and resp.response.body:
                    job_list = resp.response.body.get("zpData", {}).get("jobList", [])
                    if job_list:
                        first_id = job_list[0].get("encryptJobId", "")
                        log.info(f"    scene={scene} → 第1条jobId: {first_id[:12]}...  共{len(job_list)}条")
                        return first_id
            except Exception as e:
                log.warning(f"    scene={scene} 嗅探失败: {e}")
                try:
                    self.main_tab.listen.stop()
                except Exception:
                    pass
            return ""

        id_scene1 = _fetch_first_job_id("1")
        self._delay(2, 3)
        id_scene3 = _fetch_first_job_id("3")

        if not id_scene1 or not id_scene3:
            log.warning("⚠️ 嗅探未拿到数据，可能被限流，保持 scene=3 继续尝试")
            self.active_scene = "3"
            return

        if id_scene1 != id_scene3:
            log.info("✅ 验证通过！scene=3 返回结果与 scene=1 不同，最新排序生效！")
            self.active_scene = "3"
        else:
            log.warning("⚠️ scene=3 与 scene=1 返回结果相同，后端可能未区分此参数")
            log.warning("   → 回退使用 scene=1（推荐排序），改用HR活跃时间作为近似排序")
            self.active_scene = "1"

    def run(self):
        if not self._launch_browser():
            return False
        co = ChromiumOptions()
        co.set_local_port(self.port)
        try:
            self.browser = ChromiumPage(co)
            log.info("✅ 成功接管本地 Edge 浏览器！")
        except Exception as e:
            log.error(f"❌ 无法连接浏览器: {e}")
            return False

        try:
            boss_tab = None
            for tab_id in self.browser.tab_ids:
                tab = self.browser.get_tab(tab_id)
                if tab and "zhipin.com" in tab.url:
                    boss_tab = tab
                    break
            self.main_tab = boss_tab if boss_tab else self.browser.latest_tab

            if not self._ensure_logged_in():
                return False

            # ── scene 验证 ──
            self._sniff_and_verify_scene()

            max_per_day = self.cfg.get("max_apply_per_day", 50)
            campus_str = "校招/应届" if self.cfg.get("is_campus_recruitment") else "全部经验"
            ai_status = "已启用" if AI_CONFIG["enabled"] else "已关闭"
            test_status = "开启（只生成不发送）" if self.cfg.get("test_mode", False) else "关闭"
            log.info(f"🎉 准备就绪！scene={self.active_scene} | 经验要求={campus_str} | AI={ai_status} | 每日上限={max_per_day} | 测试模式={test_status}")

            if AI_CONFIG["enabled"]:
                self._test_api_connection()

            for keyword in self.cfg["keywords"]:
                if self.daily_applied >= max_per_day:
                    log.info(f"🛑 今日已达投递上限 ({max_per_day})，安全退出。")
                    break
                self._search_and_apply(keyword)

            log.info(f"\n🎉 运行结束！本次共投递 {self.total_applied} 个岗位，今日累计 {self.daily_applied} 次")

            return True

        except KeyboardInterrupt:
            log.info("\n⚠️ 用户中断 (Ctrl+C)，正在清理...")
            return False
        finally:
            self._flush_records()
            try:
                for tab in self.browser.tabs:
                    if tab != self.main_tab and "zhipin.com" in (tab.url or ""):
                        tab.close()
            except Exception:
                pass

    def _test_api_connection(self):
        log.info(f"🔌 正在测试MiMo API连通性... model={AI_CONFIG['model']} base_url={AI_CONFIG['base_url']}")
        test_payload = {
            "model": AI_CONFIG["model"],
            "messages": [
                {"role": "system", "content": "You are MiMo, an AI assistant developed by Xiaomi."},
                {"role": "user", "content": "请只回复两个字：可以"},
            ],
            "max_completion_tokens": 64,
            "temperature": 1.0,
            "top_p": 0.95,
            "stream": False,
            "frequency_penalty": 0,
            "presence_penalty": 0,
        }
        try:
            result = _call_mimo_api(test_payload, timeout=10, retries=0)
            reply = result["choices"][0]["message"]["content"].strip()
            log.info(f"✅ API连通正常！测试响应: {reply[:20]}")
        except Exception as e:
            log.warning(f"⚠️ API连通测试失败: {e}")
            hint = _mimo_error_hint(e)
            if hint:
                log.warning(f"⚠️ {hint}")
            AI_CONFIG["enabled"] = False
            log.warning("⚠️ 本次运行已自动关闭 AI 打招呼，避免每个岗位重复 API 失败；修复账号/额度后重启脚本即可恢复。")

    def _search_and_apply(self, keyword: str):
        city_code = CITY_CODES.get(self.cfg["city"], "101280600")

        log.info(f"\n{'='*40}")
        log.info(f"🔍 关键词:【{keyword}】 城市:【{self.cfg['city']}】 scene={self.active_scene}")
        log.info(f"{'='*40}")

        # ── ★ 构造 URL（含 scene 参数）──────────────────────────
        target_url = (
            f"https://www.zhipin.com/web/geek/job"
            f"?query={keyword}&city={city_code}&scene={self.active_scene}"
        )
        if self.cfg.get("is_campus_recruitment"):
            exp_param = self.cfg.get("experience_param", "102")
            target_url += f"&experience={exp_param}"
            log.info("🎓 已开启校招/应届生过滤")

        self.main_tab.get(target_url)
        self._delay(2, 4)

        try:
            self.main_tab.wait.ele_loaded(
                'xpath://*[contains(@class, "job-name") or contains(@class, "job-card")]',
                timeout=8,
            )
        except Exception:
            pass

        page_num = 1
        keyword_applied_count = 0
        target_amount = self.cfg["max_apply_per_keyword"]
        max_per_day = self.cfg.get("max_apply_per_day", 50)
        seen_card_keys = set()

        def _card_keys(card_list: list) -> set:
            keys = set()
            for item in card_list:
                key = self._job_card_key(item)
                if key:
                    keys.add(key)
            return keys

        while keyword_applied_count < target_amount and self.daily_applied < max_per_day:
            log.info(f"  📄 第 {page_num} 页 (进度: {keyword_applied_count}/{target_amount})...")
            self._delay(1, 2)
            self._scroll_until_stable()

            cards = self._get_job_cards()

            if not cards:
                log.warning("⚠️ 未找到职位列表，可能被限流，跳过此关键词。")
                break

            # ── scene=1 时按 HR 活跃时间辅助排序（scene=3 已按最新排好）──
            if self.active_scene != "3":
                cards = self._sort_cards_by_active_time(cards)
            known_card_keys = _card_keys(cards)

            stale_restart = False
            stable_rounds = 0
            while (keyword_applied_count < target_amount
                   and self.daily_applied < max_per_day
                   and stable_rounds < 3):
                next_card = None
                next_key = ""
                for card in cards:
                    card_key = self._job_card_key(card)
                    if card_key and card_key not in seen_card_keys:
                        next_card = card
                        next_key = card_key
                        break

                if not next_card:
                    self._scroll_job_list_step()
                    refreshed_cards = self._get_job_cards()
                    fresh_keys = _card_keys(refreshed_cards)
                    has_unseen = any(key and key not in seen_card_keys for key in fresh_keys)
                    if not has_unseen:
                        stable_rounds += 1
                    else:
                        stable_rounds = 0
                        cards = refreshed_cards
                        known_card_keys.update(fresh_keys)
                        if self.active_scene != "3":
                            cards = self._sort_cards_by_active_time(cards)
                    continue

                try:
                    self._scroll_card_into_view(next_card)
                    applied = self._process_job_card(next_card, keyword)
                    seen_card_keys.add(next_key)
                    if applied:
                        keyword_applied_count += 1
                        self.total_applied += 1
                        self.daily_applied += 1
                    self._scroll_job_list_step()
                    refreshed_cards = self._get_job_cards()
                    fresh_keys = _card_keys(refreshed_cards)
                    has_new_batch = any(key and key not in known_card_keys for key in fresh_keys)
                    if has_new_batch:
                        cards = refreshed_cards
                        known_card_keys.update(fresh_keys)
                    if has_new_batch and self.active_scene != "3":
                        cards = self._sort_cards_by_active_time(cards)
                    stable_rounds = 0
                except Exception as e:
                    if "失效" in str(e) or "stale" in str(e).lower():
                        log.warning("⚠️ 页面元素失效，重新获取卡片列表...")
                        stale_restart = True
                        break
                    raise
            if stale_restart:
                continue

            if self.daily_applied >= max_per_day:
                log.info(f"🛑 今日已达投递上限 ({max_per_day})，安全退出。")
                return
            if keyword_applied_count >= target_amount:
                log.info(f"🎯 【{keyword}】已达投递上限，切换下一词。")
                break

            next_btn = self.main_tab.ele("css:.options-pages a.next")
            if not next_btn or "disabled" in (next_btn.attr("class") or ""):
                log.info("  已到最后一页。")
                break

            next_btn.click()
            page_num += 1
            self._delay(*self.cfg["page_turn_interval"])
            try:
                self.main_tab.wait.ele_loaded('xpath://*[contains(@class, "job-name")]', timeout=5)
            except Exception:
                pass

    def _get_job_cards(self) -> list:
        cards = self.main_tab.eles("css:.job-card-wrapper")
        if not cards:
            cards = self.main_tab.eles("css:.job-card-box")
        if not cards:
            cards = self.main_tab.eles('xpath://li[contains(@class, "job-card")]')
        if not cards:
            cards = self.main_tab.eles('xpath://*[contains(@class, "job-list")]/li')
        return cards

    def _job_card_snapshot(self, card) -> dict:
        try:
            data = card.run_js("""
                function clean(value) {
                    return String(value || '').replace(/\\s+/g, ' ').trim();
                }
                function firstText(selectors, rejectJobLink) {
                    for (var s = 0; s < selectors.length; s++) {
                        var nodes = this.querySelectorAll(selectors[s]);
                        for (var i = 0; i < nodes.length; i++) {
                            var href = nodes[i].getAttribute && (nodes[i].getAttribute('href') || '');
                            if (rejectJobLink && href.indexOf('/job_detail/') >= 0) continue;
                            var text = clean(nodes[i].innerText || nodes[i].textContent);
                            if (text) return text;
                        }
                    }
                    return '';
                }
                function decodeSalaryText(node) {
                    function decode(child) {
                        if (child.nodeType === 3) {
                            return child.nodeValue || '';
                        }
                        if (child.nodeType !== 1) {
                            return '';
                        }
                        var cls = child.className;
                        if (cls && typeof cls === 'object' && cls.baseVal !== undefined) {
                            cls = cls.baseVal;
                        }
                        cls = String(cls || '');
                        var m = cls.match(/icon-num-(\\d)/);
                        if (m) return m[1];
                        if (/icon-num-point|icon-num-dot/.test(cls)) return '.';
                        if (/icon-num-minus|icon-num-dash/.test(cls)) return '-';
                        if (/icon-num-/.test(cls)) return '';
                        var content = '';
                        try {
                            content = window.getComputedStyle(child, '::before').content || '';
                        } catch (e) {
                            content = '';
                        }
                        if (content && content !== 'none' && content !== 'normal') {
                            var text = String(content);
                            var out = '';
                            for (var k = 0; k < text.length; k++) {
                                var code = text.charCodeAt(k);
                                if (code >= 0xE031 && code <= 0xE03A) {
                                    out += String(code - 0xE031);
                                } else {
                                    out += text.charAt(k);
                                }
                            }
                            return out;
                        }
                        var sub = '';
                        for (var j = 0; j < child.childNodes.length; j++) {
                            sub += decode(child.childNodes[j]);
                        }
                        return sub;
                    }
                    var result = '';
                    for (var i = 0; i < node.childNodes.length; i++) {
                        result += decode(node.childNodes[i]);
                    }
                    return result.replace(/\\s+/g, ' ').trim();
                }
                function firstHref(selectors) {
                    for (var s = 0; s < selectors.length; s++) {
                        var node = this.querySelector(selectors[s]);
                        if (!node) continue;
                        var href = node.getAttribute('href') || '';
                        if (href) return href;
                    }
                    return '';
                }
                return {
                    position: firstText.call(this, ['.job-name', '.job-title', '[class*="job-name"]', '[class*="job-title"]'], false),
                    company: firstText.call(this, [
                        '.company-name', '.company-info .name', '.company-info a',
                        '.job-card-right .company-name', '.job-card-right a',
                        '.job-card-footer a', '.job-card-footer .company-info',
                        '.brand-name', '.company-title', '.company-text',
                        '[class*="company"] a', '[class*="company"] [class*="name"]',
                        'a[href*="/gongsi/"]', 'a[href*="/company/"]'
                    ], true),
                    salary: (function(){ var n = this.querySelector('.salary') || this.querySelector('[class*="salary"]'); return n ? decodeSalaryText(n) : ''; }).call(this),
                    hr_name: firstText.call(this, ['.boss-name', '.info-public', '[class*="boss-name"]'], false),
                    hr_active: firstText.call(this, ['.boss-active-time', '.active-time', '[class*="boss-active-time"]'], false),
                    href: firstHref.call(this, ['a.job-card-left', 'a[href*="/job_detail/"]', 'a'])
                };
            """)
            if not isinstance(data, dict):
                return {}
            result = {k: str(v or "").strip() for k, v in data.items()}
            if result.get("company"):
                result["company"] = self._pick_company_text(result["company"])
            return result
        except Exception:
            return {}

    def _job_card_key(self, card, snapshot: dict | None = None) -> str:
        snapshot = snapshot if snapshot is not None else self._job_card_snapshot(card)
        href = (snapshot or {}).get("href", "")
        if href:
            return f"url:{href}"
        try:
            link = (card.ele("css:a.job-card-left", timeout=0.3)
                    or card.ele('xpath:.//a[contains(@href, "/job_detail/")]', timeout=0.3)
                    or card.ele("css:a", timeout=0.3))
            href = link.attr("href") or ""
            if href:
                return f"url:{href}"
        except Exception:
            pass
        position = (snapshot or {}).get("position", "")
        company = (snapshot or {}).get("company", "")
        if position or company:
            return f"job:{company}|{position}"
        try:
            position = _get_text(self._find_job_name(card))
            company = _get_text(self._find_company_name(card))
            if position or company:
                return f"job:{company}|{position}"
        except Exception:
            pass
        try:
            text = re.sub(r"\s+", " ", card.text or "").strip()
            if text:
                return f"text:{text[:120]}"
        except Exception:
            pass
        return ""

    def _scroll_card_into_view(self, card):
        try:
            card.run_js("this.scrollIntoView({block: 'center', inline: 'nearest'});")
            self._delay(0.2, 0.5)
        except Exception:
            pass

    def _scroll_job_list_step(self):
        try:
            self.main_tab.scroll.down(600)
        except Exception:
            try:
                self.main_tab.run_js("window.scrollBy(0, 600);")
            except Exception:
                pass
        self._delay(0.4, 0.9)

    def _scroll_until_stable(self):
        log.info("    ⏬ 正在滚动加载完整岗位列表...")
        prev_count = 0
        stable_rounds = 0
        for _ in range(10):
            self.main_tab.scroll.down(800)
            self._delay(0.6, 1.2)
            current = self.main_tab.run_js(
                "return document.querySelectorAll('.job-card-wrapper, .job-card-box, li.job-card').length;"
            ) or 0
            if current == prev_count:
                stable_rounds += 1
                if stable_rounds >= 2:
                    break
            else:
                stable_rounds = 0
                prev_count = current
        self.main_tab.scroll.to_top()
        self._delay(0.5, 1.0)

    # ══════════════════════════════════════════
    # HR活跃时间排序（scene=1 回退时使用）
    # ══════════════════════════════════════════
    def _parse_active_score(self, active_text: str) -> int:
        if not active_text:
            return 50
        t = active_text.strip()
        if any(k in t for k in ["刚刚", "分钟"]):
            return 100
        if any(k in t for k in ["今日", "今天", "小时"]):
            return 90
        if any(k in t for k in ["3天", "三天", "2天", "两天"]):
            return 70
        if any(k in t for k in ["本周", "7天", "一周"]):
            return 60
        if any(k in t for k in ["本月", "30天", "一月"]):
            return 40
        if any(k in t for k in ["半年", "季度"]):
            return 10
        if any(k in t for k in ["一年", "年前"]):
            return 5
        return 50

    def _sort_cards_by_active_time(self, cards: list) -> list:
        try:
            def _score(card):
                try:
                    snapshot = self._job_card_snapshot(card)
                    card_key = self._job_card_key(card, snapshot)
                    cache_key = card_key or f"id:{id(card)}"
                    if cache_key in self._active_score_cache:
                        return self._active_score_cache[cache_key]
                    score = self._parse_active_score(snapshot.get("hr_active", ""))
                    self._active_score_cache[cache_key] = score
                    return score
                except Exception:
                    return 50
            scored = sorted(cards, key=_score, reverse=True)
            log.info(f"    🕐 已按HR活跃时间辅助排序（{len(scored)}张卡片）")
            return scored
        except Exception as e:
            log.warning(f"    ⚠️ 排序失败，使用原顺序: {e}")
            return cards

    # ══════════════════════════════════════════
    # 卡片元素查找器
    # ══════════════════════════════════════════
    def _find_job_name(self, card):
        return (card.ele("css:.job-name", timeout=1)
                or card.ele("css:.job-title", timeout=1)
                or card.ele('xpath:.//*[contains(@class,"job-name")]', timeout=1)
                or card.ele('xpath:.//*[contains(@class,"job-title")]', timeout=1))

    def _make_text_ele(self, text: str):
        class _FakeEle:
            pass
        ele = _FakeEle()
        ele.text = text
        return ele

    def _pick_company_text(self, raw_text: str) -> str:
        text = re.sub(r"\s+", "\n", str(raw_text or "")).strip()
        bad_exact = {
            "", "猎头", "HR", "BOSS直聘", "查看详情", "立即沟通", "继续沟通",
            "公司主页", "公司介绍", "公司信息", "工商信息", "查看更多", "查看全部", "在招职位", "招聘职位",
            "不需要融资", "未融资", "已上市",
        }
        bad_parts = ["职位", "薪资", "经验", "本科", "大专", "学历", "薪", "K", "元/天"]
        for line in re.split(r"[\r\n]+", text):
            item = line.strip(" -_/｜|·,，.。:：;；")
            if not item or item in bad_exact:
                continue
            if len(item) < 2 or len(item) > 50:
                continue
            if any(part in item for part in bad_parts):
                continue
            return item
        return ""

    def _pick_company_from_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        patterns = [
            r'"(?:brandName|companyName|companyShortName|brandFullName|brand_name|company_name)"\s*:\s*"([^"]{2,100})"',
            r'<a[^>]+href=["\'][^"\']*(?:/gongsi/|/company/)[^"\']*["\'][^>]*>([^<]{2,100})</a>',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, raw_html, flags=re.IGNORECASE):
                value = match.group(1)
                try:
                    value = json.loads(f'"{value}"')
                except Exception:
                    value = re.sub(r"<[^>]+>", "", value)
                name = self._pick_company_text(value)
                if name:
                    return name
        return ""

    def _find_company_name(self, card):
        selectors = [
            "css:.company-name", "css:.company-info .name", "css:.company-info a",
            "css:.job-card-right .company-name", "css:.job-card-right a",
            "css:.job-card-footer a", "css:.job-card-footer .company-info", "css:.job-card-footer [class*=company]",
            "css:.brand-name", "css:.company-title", "css:.company-text", "css:.company",
            'xpath:.//*[contains(@class,"company-name")]',
            'xpath:.//*[contains(@class,"company-info")]//a',
            'xpath:.//*[contains(@class,"company-info")]',
            'xpath:.//*[contains(@class,"job-card-right")]//a',
            'xpath:.//*[contains(@class,"job-card-footer")]//a',
            'xpath:.//*[contains(@class,"job-card-footer")]//*[contains(@class,"company")]',
            'xpath:.//a[contains(@href,"/gongsi/")]',
            'xpath:.//a[contains(@href,"/company/")]',
        ]
        for sel in selectors:
            try:
                ele = card.ele(sel, timeout=0.5)
                href = ele.attr("href") or ""
                if "/job_detail/" in href:
                    continue
                name = self._pick_company_text(_get_full_text(ele))
                if name:
                    return self._make_text_ele(name)
            except Exception:
                continue
        try:
            result = card.run_js("""
                function pick(raw) {
                    var badExact = {'':1, '猎头':1, 'HR':1, 'BOSS直聘':1, '查看详情':1, '立即沟通':1, '继续沟通':1, '公司主页':1, '公司介绍':1, '公司信息':1, '工商信息':1, '查看更多':1, '查看全部':1, '在招职位':1, '招聘职位':1, '不需要融资':1, '未融资':1, '已上市':1};
                    var badParts = ['职位', '薪资', '经验', '本科', '大专', '学历', '薪', 'K', '元/天'];
                    var lines = String(raw || '').split(/[\\r\\n]+/);
                    for (var i = 0; i < lines.length; i++) {
                        var item = lines[i].trim().replace(/^[-_/｜|·,，.。:：;；]+|[-_/｜|·,，.。:：;；]+$/g, '');
                        if (!item || badExact[item] || item.length < 2 || item.length > 50) continue;
                        var bad = false;
                        for (var j = 0; j < badParts.length; j++) {
                            if (item.indexOf(badParts[j]) >= 0) { bad = true; break; }
                        }
                        if (!bad) return item;
                    }
                    return '';
                }
                var selectors = [
                    '.company-name', '.company-info .name', '.company-info a',
                    '.job-card-right .company-name', '.job-card-right a',
                    '.job-card-footer a', '.brand-name', '.company-title',
                    '[class*="company"] a', '[class*="company"] [class*="name"]',
                    '[class*="brand"] a', '[class*="brand"] [class*="name"]'
                ];
                for (var s = 0; s < selectors.length; s++) {
                    var nodes = this.querySelectorAll(selectors[s]);
                    for (var i = 0; i < nodes.length; i++) {
                        var href = nodes[i].getAttribute('href') || '';
                        if (href.indexOf('/job_detail/') >= 0) continue;
                        var name = pick(nodes[i].innerText || nodes[i].textContent);
                        if (name) return name;
                    }
                }
                var links = this.querySelectorAll('a[href*="/gongsi/"], a[href*="/company/"]');
                for (var k = 0; k < links.length; k++) {
                    var name2 = pick(links[k].innerText || links[k].textContent);
                    if (name2) return name2;
                }
                return null;
            """)
            name = self._pick_company_text(result)
            if name:
                return self._make_text_ele(name)
        except Exception:
            pass
        try:
            name = self._pick_company_from_html(card.html)
            if name:
                return self._make_text_ele(name)
        except Exception:
            pass
        return None

    def _find_company_name_from_detail(self, detail_tab) -> str:
        selectors = [
            "css:.company-name", "css:.company-info .name", "css:.company-info a",
            "css:.company-title", "css:.company-card a", "css:.sider-company a",
            "css:.job-detail-company a", "css:.job-company-info a",
            "css:.company-new .name", "css:.company-box .name", "css:.sider-company .name",
            "css:.company-info-box a", "css:[ka*=company]",
            'xpath://a[contains(@href,"/gongsi/")]',
            'xpath://a[contains(@href,"/company/")]',
            'xpath://*[contains(@class,"company-name")]',
            'xpath://*[contains(@class,"company-info")]//a',
            'xpath://*[contains(@class,"company") and contains(@class,"name")]',
        ]
        for sel in selectors:
            try:
                ele = detail_tab.ele(sel, timeout=0.8)
                name = self._pick_company_text(_get_full_text(ele))
                if name:
                    return name
            except Exception:
                continue
        try:
            result = detail_tab.run_js("""
                function pick(raw) {
                    var badExact = {'':1, '猎头':1, 'HR':1, 'BOSS直聘':1, '查看详情':1, '立即沟通':1, '继续沟通':1, '公司主页':1, '公司介绍':1, '公司信息':1, '工商信息':1, '查看更多':1, '查看全部':1, '在招职位':1, '招聘职位':1, '不需要融资':1, '未融资':1, '已上市':1};
                    var badParts = ['职位', '薪资', '经验', '本科', '大专', '学历', '薪', 'K', '元/天'];
                    var lines = String(raw || '').split(/[\\r\\n]+/);
                    for (var i = 0; i < lines.length; i++) {
                        var item = lines[i].trim().replace(/^[-_/｜|·,，.。:：;；]+|[-_/｜|·,，.。:：;；]+$/g, '');
                        if (!item || badExact[item] || item.length < 2 || item.length > 50) continue;
                        var bad = false;
                        for (var j = 0; j < badParts.length; j++) {
                            if (item.indexOf(badParts[j]) >= 0) { bad = true; break; }
                        }
                        if (!bad) return item;
                    }
                    return '';
                }
                var selectors = [
                    '.company-name', '.company-info .name', '.company-info a',
                    '.company-title', '.company-card a', '.sider-company a',
                    '.job-detail-company a', '.job-company-info a',
                    '[class*="company"] a', '[class*="company"] [class*="name"]'
                ];
                for (var s = 0; s < selectors.length; s++) {
                    var nodes = document.querySelectorAll(selectors[s]);
                    for (var i = 0; i < nodes.length; i++) {
                        var href = nodes[i].getAttribute('href') || '';
                        if (href.indexOf('/job_detail/') >= 0) continue;
                        var name = pick(nodes[i].innerText || nodes[i].textContent);
                        if (name) return name;
                    }
                }
                return null;
            """)
            name = self._pick_company_text(result)
            if name:
                return name
        except Exception:
            pass
        try:
            return self._pick_company_from_html(detail_tab.html)
        except Exception:
            return ""

    def _find_salary(self, card):
        return (card.ele("css:.salary", timeout=1)
                or card.ele("css:.red.salary", timeout=1)
                or card.ele('xpath:.//*[contains(@class,"salary")]', timeout=1)
                or card.ele('xpath:.//*[contains(text(), "K") or contains(text(), "薪") or contains(text(), "元/天")]', timeout=1))

    def _find_hr_name(self, card):
        return (card.ele("css:.boss-name", timeout=1)
                or card.ele("css:.info-public", timeout=1)
                or card.ele('xpath:.//*[contains(@class,"boss-name")]', timeout=1))

    def _pick_hr_name_text(self, raw_text: str) -> str:
        text = re.sub(r"\s+", " ", str(raw_text or "")).strip()
        if not text:
            return ""
        match = re.search(r"[\u4e00-\u9fa5]{1,4}(女士|先生|老师)", text)
        if match:
            return match.group(0)
        parts = re.split(r"[\s|｜·,，/]+", text)
        bad_parts = {"", "HR", "招聘", "招聘者", "人事", "猎头顾问", "经理", "主管", "负责人"}
        for part in parts:
            item = part.strip()
            if 2 <= len(item) <= 8 and item not in bad_parts:
                return item
        return ""

    def _clean_hr_name(self, raw_text: str, company_name: str = "", position: str = "") -> str:
        name = self._pick_hr_name_text(raw_text)
        if not name:
            return ""
        compact_name = self._compact_identity_text(name)
        generic = {"招聘", "招聘者", "人事", "hr", "猎头顾问", "经理", "主管", "负责人", "顾问", "专员", "总监"}
        if not compact_name or compact_name in generic:
            return ""

        compact_company = self._compact_identity_text(company_name)
        if compact_company and (
            compact_name == compact_company
            or compact_name in compact_company
            or compact_company in compact_name
        ):
            return ""

        compact_position = self._compact_identity_text(position)
        if compact_position and (
            compact_name == compact_position
            or (len(compact_name) >= 3 and compact_name in compact_position)
        ):
            return ""

        company_markers = ("公司", "科技", "集团", "有限", "股份", "信息", "软件", "网络")
        has_person_suffix = bool(re.search(r"(女士|先生|老师)$", name))
        if not has_person_suffix and any(marker in compact_name for marker in company_markers):
            return ""
        return name

    def _find_hr_name_from_detail(self, detail_tab) -> str:
        selectors = [
            "css:.job-boss-info .name", "css:.boss-info .name", "css:.boss-name",
            "css:.job-boss-name", "css:[class*=boss] [class*=name]",
            "xpath://*[contains(@class,'boss') and contains(@class,'name')]",
            "xpath://*[contains(@class,'boss')]//*[contains(@class,'name')]",
        ]
        for sel in selectors:
            try:
                ele = detail_tab.ele(sel, timeout=0.8)
                name = self._pick_hr_name_text(_get_full_text(ele))
                if name:
                    return name
            except Exception:
                continue
        try:
            text = detail_tab.run_js("""
                var nodes = document.querySelectorAll('[class*="boss"], [class*="recruit"], [class*="job-detail"]');
                for (var i = 0; i < nodes.length; i++) {
                    var raw = (nodes[i].innerText || nodes[i].textContent || '').trim();
                    if (!raw || raw.length > 300) continue;
                    var m = raw.match(/[\\u4e00-\\u9fa5]{1,4}(女士|先生|老师)/);
                    if (m) return m[0];
                }
                return '';
            """)
            return self._pick_hr_name_text(text)
        except Exception:
            return ""

    def _find_hr_active(self, card, timeout=1):
        return (card.ele("css:.boss-active-time", timeout=timeout)
                or card.ele("css:.active-time", timeout=timeout)
                or card.ele('xpath:.//*[contains(@class,"boss-active-time")]', timeout=timeout))

    def _scrape_job_description(self, detail_tab) -> str:
        selectors = [
            "css:.job-detail-card .job-sec-text", "css:.job-sec-text",
            "css:.job-detail-section", "css:.job-description", "css:.detail-content",
            'xpath://*[contains(@class,"job-sec-text")]',
        ]
        best_text = ""
        for sel in selectors:
            try:
                ele = detail_tab.ele(sel, timeout=2)
                if ele:
                    text = ele.text.strip()
                    if len(text) > len(best_text):
                        best_text = text
            except Exception:
                continue
        if best_text:
            log.info(f"    📋 成功抓取职位描述（{len(best_text)}字）")
            if len(best_text) < 30:
                log.warning(f"    ⚠️ JD 过短（{len(best_text)}字），可能抓取不完整")
        else:
            log.warning("    ⚠️ 职位描述未找到")
        return best_text

    def _wait_for_vue_render(self, tab, max_wait: float = 8.0):
        deadline = time.time() + max_wait
        last_progress_log = 0.0
        log.info(f"    ⏳ 等待聊天页Vue组件渲染（最多{max_wait:.0f}s）...")
        while time.time() < deadline:
            try:
                is_ready = tab.run_js("""
                    var bodyText = document.body.innerText || '';
                    var hasInput = !!document.querySelector('[contenteditable="true"], textarea, [placeholder*="说点"], [placeholder*="发送"]');
                    var hasChatUI = !!document.querySelector('[class*="chat"], [class*="message"], [class*="dialog"], [class*="im"]');
                    var hasAvatar = !!document.querySelector('[class*="avatar"], img[class*="avatar"], [class*="user-name"], [class*="name"]');
                    var hasText = bodyText.length > 500;
                    return !!(hasInput || (hasChatUI && (hasAvatar || hasText)));
                """)
                if is_ready:
                    log.info("    ✅ 聊天页Vue组件渲染完成")
                    return True
            except Exception:
                pass
            now = time.time()
            if now - last_progress_log >= 3:
                remain = max(0, deadline - now)
                log.info(f"    ⏳ 聊天页仍在渲染/加载，继续等待（剩余约{remain:.0f}s）")
                last_progress_log = now
            time.sleep(0.8)
        log.warning(f"    ⚠️ Vue渲染等待超时({max_wait}s)，强制继续")
        return False

    # ══════════════════════════════════════════
    # ★ 核心修复：聊天发送（v19_fixed保留）
    # ══════════════════════════════════════════
    def _try_send_in_current_tab(self, tab, ai_message: str, company_name: str = "", hr_name: str = "") -> bool:
        if not company_name or company_name == "未知公司":
            log.warning("    ⚠️ 缺少公司名，当前tab不发送AI消息，避免复用错误会话输入框")
            return False
        self._wait_for_vue_render(tab, max_wait=8)
        chat_input = self._find_chat_input(tab)
        if chat_input:
            log.info("    💬 在当前tab直接找到输入框，无需跳转")
            log.info("    🔍 当前tab发送前按公司/招聘人确认联系人...")
            if not self._active_chat_matches_company(tab, company_name, hr_name):
                contact = self._click_first_contact(tab, company_name, hr_name)
                if contact:
                    self._delay(1.0, 1.5)
                    chat_input = self._find_chat_input(tab)
                else:
                    log.warning("    ⚠️ 当前tab联系人未通过公司校验，不直接发送")
                    return False
            if not self._active_chat_matches_company(tab, company_name, hr_name):
                log.warning("    ⚠️ 当前tab最终发送前公司校验失败，跳过AI消息")
                return False
            return self._send_message(tab, chat_input, ai_message)
        return False

    def _goto_chat_and_send(self, from_tab, ai_message: str, company_name: str = "", hr_name: str = ""):
        chat_url = "https://www.zhipin.com/web/geek/chat"
        try:
            if not company_name or company_name == "未知公司":
                log.warning("    ⚠️ 缺少公司名，放弃聊天页fallback发送，避免发错联系人")
                return False

            current_url = ""
            try:
                current_url = from_tab.url or ""
            except Exception:
                pass
            sent = False

            if "zhipin.com/web/geek/chat" in current_url:
                log.info("    💬 当前tab已在聊天页，跳过重新导航，直接发送...")
                chat_input = self._find_chat_input(from_tab)
                if chat_input:
                    if company_name and company_name != "未知公司":
                        log.info("    🔍 当前聊天页已有输入框，先按公司/招聘人确认联系人...")
                        if not self._active_chat_matches_company(from_tab, company_name, hr_name):
                            contact = self._click_first_contact(from_tab, company_name, hr_name)
                            if contact:
                                self._delay(1.5, 2.0)
                                chat_input = self._find_chat_input(from_tab)
                            else:
                                log.warning("    ⚠️ 当前聊天页联系人未通过公司校验，跳过本条AI消息")
                                return False
                        if not self._active_chat_matches_company(from_tab, company_name, hr_name):
                            log.warning("    ⚠️ 当前聊天页最终发送前公司校验失败，跳过本条AI消息")
                            return False
                    return self._send_message(from_tab, chat_input, ai_message)
                log.warning("    ⚠️ 已在聊天页但输入框未找到，尝试激活联系人...")
                if self._click_first_contact(from_tab, company_name, hr_name):
                    self._delay(1.5, 2.0)
                    chat_input = self._find_chat_input(from_tab)
                    if chat_input:
                        if not self._active_chat_matches_company(from_tab, company_name, hr_name):
                            log.warning("    ⚠️ 激活联系人后最终公司校验失败，跳过本条AI消息")
                            return False
                        return self._send_message(from_tab, chat_input, ai_message)
                log.warning("    ⚠️ 聊天页激活联系人失败，跳过本条AI消息")
                return False

            log.info(f"    🚀 导航到聊天页: {chat_url}")
            from_tab.get(chat_url)
            self._wait_for_vue_render(from_tab, max_wait=10)
            self._delay(1, 1.5)

            chat_input = self._find_chat_input(from_tab)
            if chat_input:
                if company_name and company_name != "未知公司":
                    log.info("    💬 跳转后右侧对话已展开，先按公司/招聘人确认联系人")
                    if not self._active_chat_matches_company(from_tab, company_name, hr_name):
                        contact = self._click_first_contact(from_tab, company_name, hr_name)
                        if contact:
                            self._delay(1.5, 2.0)
                            chat_input = self._find_chat_input(from_tab)
                        else:
                            log.warning("    ⚠️ 跳转后右侧会话未通过公司校验，放弃当前输入框")
                            return False
                else:
                    log.info("    💬 跳转后右侧对话已展开，直接找到输入框")
            else:
                log.info("    🔍 跳转后右侧未展开，按公司名匹配联系人列表...")
                contact = self._click_first_contact(from_tab, company_name, hr_name)
                if contact:
                    self._delay(1.5, 2.0)
                    chat_input = self._find_chat_input(from_tab)
                else:
                    log.warning("    ⚠️ 联系人列表未匹配目标公司，不再使用当前聊天输入框，避免发错人")
                    return False

            if chat_input:
                if not self._active_chat_matches_company(from_tab, company_name, hr_name):
                    log.warning("    ⚠️ 最终发送前公司校验失败，跳过AI消息发送")
                    sent = False
                else:
                    sent = self._send_message(from_tab, chat_input, ai_message)
            else:
                log.warning("    ⚠️ 最终未找到输入框，跳过AI消息发送")
                try:
                    from_tab.get_screenshot("chat_error_screenshot.png")
                    log.warning("    📸 网页快照已保存至 chat_error_screenshot.png")
                except Exception:
                    pass
                sent = False

            try:
                from_tab.back()
                self._delay(0.8, 1.2)
            except Exception:
                pass
            return sent

        except Exception as e:
            log.warning(f"    ⚠️ 导航聊天页异常: {e}")
            return False

    def _company_match_fragments(self, company_name: str) -> list:
        cache_key = (company_name or "").strip()
        if cache_key in self._fragment_cache:
            return self._fragment_cache[cache_key]
        name = cache_key
        if not name or name == "未知公司":
            return []
        compact = re.sub(r"[\s()（）【】\[\]《》<>·,，.。:：;；|｜_-]+", "", name)
        city_names = (
            "北京", "上海", "天津", "重庆", "深圳", "广州", "杭州", "成都", "武汉", "南京",
            "西安", "苏州", "东莞", "佛山", "长沙", "郑州", "合肥", "厦门", "青岛", "济南",
            "宁波", "无锡", "珠海", "中山", "惠州",
        )
        variants = []

        def add_variant(value: str):
            value = value.strip()
            if value and value not in variants:
                variants.append(value)

        add_variant(compact)
        without_province = re.sub(r"^[\u4e00-\u9fa5]{2,4}省", "", compact)
        add_variant(without_province)
        for city in city_names:
            for source in [compact, without_province]:
                if source.startswith(city + "市"):
                    add_variant(source[len(city) + 1:])
                elif source.startswith(city):
                    add_variant(source[len(city):])

        suffixes = [
            "有限责任公司", "股份有限公司", "科技有限公司", "信息技术有限公司",
            "网络科技有限公司", "有限公司", "科技", "信息技术", "网络", "公司",
        ]
        for item in list(variants):
            for suffix in suffixes:
                if item.endswith(suffix) and len(item) > len(suffix):
                    add_variant(item[:-len(suffix)])

        city_fragments = set(city_names) | {f"{city}市" for city in city_names}
        stop_fragments = city_fragments | {
            "科技", "信息", "网络", "公司", "有限", "责任", "股份", "深圳市", "上海市", "北京市",
            "有限公司", "科技有限", "信息技术", "网络科技", "软件公司",
        }
        fragments = []
        for item in variants:
            for length in [10, 8, 6, 5, 4, 3, 2]:
                if len(item) >= length:
                    frag = item[:length]
                    if frag in stop_fragments:
                        continue
                    if any(frag.startswith(city + "市") or frag == city for city in city_names):
                        continue
                    if len(frag) < 3 and len(item) > 2:
                        continue
                    if len(frag) <= 3 and (frag.endswith("市") or frag.endswith("省")):
                        continue
                    fragments.append(frag)
        result = list(dict.fromkeys([x for x in fragments if len(x) >= 2]))
        self._fragment_cache[cache_key] = result
        return result

    def _is_company_contact_text(self, text: str, company_name: str) -> tuple:
        compact_text = re.sub(r"\s+", "", text or "")
        for frag in self._company_match_fragments(company_name):
            if frag and frag in compact_text:
                return True, frag
        return False, ""

    def _preview_text(self, text: str, limit: int = 80) -> str:
        preview = re.sub(r"\s+", " ", str(text or "")).strip()
        return preview[:limit] if preview else "空文本"

    def _compact_identity_text(self, text: str) -> str:
        return re.sub(r"[\s()（）【】\[\]《》<>·,，.。:：;；|｜_-]+", "", str(text or "")).lower()

    def _hr_fragment_is_reliable(self, hr_name: str, company_name: str) -> tuple:
        frag = self._hr_name_fragment(hr_name)
        if not frag or len(frag) < 2:
            return False, frag
        compact_frag = self._compact_identity_text(frag)
        compact_company = self._compact_identity_text(company_name)
        generic = {"招聘", "招聘者", "人事", "hr", "经理", "主管", "顾问", "负责人", "专员", "总监"}
        if not compact_frag or compact_frag in generic:
            return False, frag
        if compact_company and (compact_frag == compact_company or compact_frag in compact_company or compact_company in compact_frag):
            return False, frag
        if self._is_company_contact_text(frag, company_name)[0]:
            return False, frag
        return True, frag

    def _active_chat_matches_company(self, tab, company_name: str, hr_name: str = "") -> bool:
        if not company_name or company_name == "未知公司":
            return False
        text = ""
        preview = ""
        try:
            payload = tab.run_js("""
                var vw = window.innerWidth || document.documentElement.clientWidth || 1200;
                var chunks = [];

                function visible(node) {
                    if (!node) return false;
                    var rect = node.getBoundingClientRect();
                    if (rect.width < 40 || rect.height < 10) return false;
                    var style = window.getComputedStyle(node);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                }

                function cleanText(node) {
                    return (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                }

                function addText(node, maxLen) {
                    if (!visible(node)) return;
                    if (node.closest('[contenteditable="true"], textarea, [class*="editor"], [class*="input"]')) return;
                    var text = cleanText(node);
                    if (!text || text.length > maxLen) return;
                    if (chunks.indexOf(text) < 0) chunks.push(text);
                }

                var rightSelectors = [
                    '.chat-header', '.message-header', '.dialog-header',
                    '.chat-main .user-name', '.chat-main [class*="company"]',
                    '[class*="chat"][class*="header"]',
                    '[class*="message"][class*="header"]',
                    '[class*="conversation"][class*="header"]',
                    '[class*="user-info"]'
                ];
                for (var i = 0; i < rightSelectors.length; i++) {
                    var nodes = document.querySelectorAll(rightSelectors[i]);
                    for (var j = 0; j < nodes.length; j++) {
                        var node = nodes[j];
                        var rect = node.getBoundingClientRect();
                        if (rect.left < vw * 0.30) continue;
                        if (rect.top > 340) continue;
                        if (node.closest('[class*="message-list"], [class*="message-content"], [class*="bubble"], [class*="msg-item"]')) continue;
                        addText(node, 500);
                    }
                }

                var leftSelectors = [
                    '.chat-list li.active',
                    '.chat-list [class*="active"]',
                    '[class*="chat-list"] [class*="active"]',
                    '[class*="contact-list"] [class*="active"]',
                    '[class*="conversation"][class*="active"]',
                    '[class*="selected"]'
                ];
                for (var a = 0; a < leftSelectors.length; a++) {
                    var activeNodes = document.querySelectorAll(leftSelectors[a]);
                    for (var b = 0; b < activeNodes.length; b++) {
                        var active = activeNodes[b];
                        var ar = active.getBoundingClientRect();
                        if (ar.top < 100 || ar.left > Math.min(620, vw * 0.55)) continue;
                        addText(active, 280);
                    }
                }

                if (!chunks.length) {
                    var topNodes = document.querySelectorAll('header, section, div, span, a');
                    for (var k = 0; k < topNodes.length; k++) {
                        var n = topNodes[k];
                        var r = n.getBoundingClientRect();
                        if (r.left < vw * 0.30 || r.top < 60 || r.top > 300) continue;
                        if (r.width < 40 || r.height < 10) continue;
                        if (n.closest('[class*="message-list"], [class*="message-content"], [class*="bubble"], [class*="msg-item"], [contenteditable="true"], textarea')) continue;
                        addText(n, 240);
                        if (chunks.length >= 8) break;
                    }
                }

                var previewChunks = [];
                var previewNodes = document.querySelectorAll('.chat-main, .chat-content, [class*="chat-detail"], [class*="dialog"]');
                for (var p = 0; p < previewNodes.length; p++) {
                    var pn = previewNodes[p];
                    var pr = pn.getBoundingClientRect();
                    if (pr.width < 200 || pr.height < 60 || pr.left < vw * 0.30) continue;
                    var pt = cleanText(pn);
                    if (pt && pt.length < 1500) previewChunks.push(pt);
                    if (previewChunks.length >= 2) break;
                }

                return {
                    target: chunks.join('\\n').slice(0, 1200),
                    preview: (previewChunks.join('\\n') || chunks.join('\\n')).slice(0, 1200)
                };
            """)
            if isinstance(payload, dict):
                text = payload.get("target") or ""
                preview = payload.get("preview") or text
            else:
                text = str(payload or "")
                preview = text
            matched, frag = self._is_company_contact_text(text, company_name)
            if matched:
                hr_reliable, hr_frag = self._hr_fragment_is_reliable(hr_name, company_name)
                hr_matched, real_hr_frag = self._is_hr_contact_text(text, hr_name) if hr_reliable else (False, "")
                if hr_reliable and not hr_matched:
                    log.warning(f"    ⚠️ 当前会话命中公司「{frag}」，但未命中招聘人「{hr_frag}」，跳过发送")
                    return False
                if hr_reliable and hr_matched:
                    log.info(f"    ✅ 当前会话公司「{frag}」+招聘人「{real_hr_frag}」双校验通过")
                else:
                    if not self.cfg.get("allow_company_only_when_hr_unreliable", True):
                        log.warning(f"    ⚠️ 当前会话命中公司「{frag}」，但招聘人「{hr_frag or hr_name or '-'}」不可靠，跳过发送")
                        return False
                    log.info(f"    ✅ 当前会话命中公司片段「{frag}」，招聘人「{hr_frag or hr_name or '-'}」不可靠/未抓到，按公司校验放行")
                return True
        except Exception:
            pass
        log.info(f"    ↪️ 当前会话标题/选中联系人未命中「{company_name}」，可见文本:「{self._preview_text(text or preview, 70)}」")
        return False

    def _click_contact(self, tab, contact, index: int) -> bool:
        clicked = False
        try:
            contact.click()
            clicked = True
        except Exception:
            pass
        try:
            tab.run_js("""
                var el = arguments[0];
                if (!el) return false;
                var row = el.closest('li, [class*="item"], [class*="conversation"], [class*="contact"]') || el;
                row.scrollIntoView({block: 'center', inline: 'nearest'});
                row.click();
                row.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                return true;
            """, contact)
            return True
        except Exception as e:
            if clicked:
                return True
            try:
                tab.run_js("arguments[0].click()", contact)
                return True
            except Exception:
                log.warning(f"    ⚠️ 点击第{index}项联系人失败: {e}")
                return False

    def _is_chat_contact_candidate(self, ele) -> bool:
        try:
            text = _get_full_text(ele)
            compact = re.sub(r"\s+", "", text or "")
            if len(compact) < 4 or len(compact) > 260:
                return False
            bad_parts = [
                "搜索30天内的联系人", "AI筛选", "未读", "新招呼", "更多",
                "与您进行过沟通的Boss都会在左侧列表中显示", "暂无联系人", "没有更多",
            ]
            if any(part in compact for part in bad_parts):
                return False
            rect = ele.run_js("""
                var r = this.getBoundingClientRect();
                var vw = window.innerWidth || document.documentElement.clientWidth || 1200;
                return {left:r.left, top:r.top, width:r.width, height:r.height, vw:vw};
            """)
            if not rect:
                return False
            left = float(rect.get("left", 9999))
            top = float(rect.get("top", 9999))
            width = float(rect.get("width", 0))
            height = float(rect.get("height", 0))
            vw = float(rect.get("vw", 1200))
            if top < 120:
                return False
            if left > min(620, vw * 0.55):
                return False
            if width < 160 or width > 560:
                return False
            if height < 36 or height > 135:
                return False
            row_hints = ["HR", "招聘", "女士", "先生", "经理", "主管", "总监", "刚刚", "昨天", "沟通", ":"]
            return any(hint in text for hint in row_hints)
        except Exception:
            return False

    def _get_chat_contact_candidates(self, tab, limit: int = 20) -> list:
        candidates = []
        seen = set()

        def _add_candidate(ele) -> bool:
            if not self._is_chat_contact_candidate(ele):
                return False
            try:
                rect = ele.run_js("var r = this.getBoundingClientRect(); return Math.round(r.left) + ':' + Math.round(r.top);")
                key = str(rect)
            except Exception:
                key = str(id(ele))
            if key in seen:
                return False
            seen.add(key)
            candidates.append(ele)
            return len(candidates) >= limit

        try:
            js_candidates = tab.run_js("""
                var out = [];
                var seen = new Set();
                var nodes = document.querySelectorAll('li, div');
                var vw = window.innerWidth || document.documentElement.clientWidth || 1200;
                var badParts = ['搜索30天内的联系人', 'AI筛选', '未读', '新招呼', '更多',
                    '与您进行过沟通的Boss都会在左侧列表中显示', '暂无联系人', '没有更多'];
                function compactText(el) {
                    return (el.innerText || el.textContent || '').replace(/\\s+/g, '').trim();
                }
                function isBadText(text) {
                    if (text.length < 4 || text.length > 260) return true;
                    for (var i = 0; i < badParts.length; i++) {
                        if (text.indexOf(badParts[i]) >= 0) return true;
                    }
                    return false;
                }
                function hasHint(raw) {
                    var hints = ['HR', '招聘', '女士', '先生', '经理', '主管', '总监', '刚刚', '昨天', '沟通', ':'];
                    for (var i = 0; i < hints.length; i++) {
                        if (raw.indexOf(hints[i]) >= 0) return true;
                    }
                    return false;
                }
                for (var i = 0; i < nodes.length; i++) {
                    var node = nodes[i];
                    var r = node.getBoundingClientRect();
                    if (r.top < 120 || r.left > Math.min(620, vw * 0.55)) continue;
                    if (r.width < 160 || r.width > 560 || r.height < 36 || r.height > 135) continue;
                    var style = window.getComputedStyle(node);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    var raw = (node.innerText || node.textContent || '').trim();
                    var text = raw.replace(/\\s+/g, '').trim();
                    if (isBadText(text) || !hasHint(raw)) continue;
                    var key = Math.round(r.left) + ':' + Math.round(r.top) + ':' + Math.round(r.width) + ':' + Math.round(r.height);
                    if (seen.has(key)) continue;
                    seen.add(key);
                    out.push(node);
                    if (out.length >= arguments[0]) break;
                }
                return out;
            """, limit)
            for ele in js_candidates or []:
                if _add_candidate(ele):
                    break
        except Exception:
            pass
        if len(candidates) < limit:
            selectors = [
                'css:.chat-list li',
                'css:.chat-list [class*="item"]',
                'css:[class*="chat-list"] li',
                'css:[class*="conversation"]',
                'css:[class*="contact-list"] li',
                'css:[class*="message-list"] li',
                'css:[class*="user-list"] li',
                'xpath://div[contains(@class,"chat-list")]//*[self::li or contains(@class,"item")]',
                'xpath://div[contains(@class,"contact-list") or contains(@class,"message-list") or contains(@class,"user-list")]//li',
                'xpath://ul[contains(@class,"list")]/li',
                'xpath://li[contains(@class,"item")]',
            ]
            for sel in selectors:
                try:
                    for ele in tab.eles(sel, timeout=0.2)[:limit * 3]:
                        if _add_candidate(ele):
                            return candidates
                except Exception:
                    continue
        if candidates:
            previews = " | ".join(self._preview_text(_get_full_text(ele), 35) for ele in candidates[:3])
            log.info(f"    📋 已识别聊天联系人候选 {len(candidates)} 项，前几项: {previews}")
        else:
            log.warning("    ⚠️ 未识别到有效聊天联系人行（已排除搜索框/提示文案/容器）")
        return candidates

    def _hr_name_fragment(self, hr_name: str) -> str:
        raw = re.sub(r"\s+", "", hr_name or "")
        if not raw:
            return ""
        match = re.search(r"[\u4e00-\u9fa5]{1,4}(女士|先生|老师)", raw)
        if match:
            return match.group(0)
        raw = re.sub(r"(招聘者|招聘|HR|人事|经理|主管|顾问|负责人|总监|专员|在线|刚刚活跃|今日活跃).*", "", raw, flags=re.IGNORECASE)
        return raw[:6] if len(raw) >= 2 else ""

    def _is_hr_contact_text(self, text: str, hr_name: str) -> tuple:
        frag = self._hr_name_fragment(hr_name)
        if not frag:
            return False, ""
        compact_text = re.sub(r"\s+", "", text or "")
        if frag not in compact_text:
            return False, ""
        sent_hints = ("[送达]", "[已读]", "送达", "已读", "很高兴与您联系", "看到贵司", "您好")
        if len(frag) >= 3 or any(hint in compact_text for hint in sent_hints):
            return True, frag
        return False, ""

    def _click_first_contact(self, tab, company_name: str = "", hr_name: str = "") -> bool:
        """
        从聊天列表第一项开始逐个点击，点开后校验右侧会话是否为目标公司。
        第 N 项不匹配就继续第 N+1 项，避免 fallback 导航后把 AI 消息发给错误 HR。
        """
        if not company_name or company_name == "未知公司":
            log.warning("    ⚠️ 缺少公司名，无法校验聊天联系人，跳过AI消息发送")
            return False

        limit = max(1, int(self.cfg.get("chat_contact_scan_limit", 8)))
        candidates = self._get_chat_contact_candidates(tab, limit=limit)
        if not candidates:
            log.warning("    ⚠️ 未找到任何联系人列表项，跳过点击")
            return False

        for index, contact in enumerate(candidates[:limit], start=1):
            text = _get_full_text(contact)
            preview = (text or "空文本").replace("\n", " ")[:30]
            matched, frag = self._is_company_contact_text(text, company_name)
            hr_reliable, _ = self._hr_fragment_is_reliable(hr_name, company_name)
            hr_matched, hr_frag = self._is_hr_contact_text(text, hr_name) if hr_reliable else (False, "")
            if matched or (hr_reliable and hr_matched):
                match_label = f"公司片段「{frag}」" if matched else f"招聘人「{hr_frag}」"
                log.info(f"    ✅ 第{index}项列表文本命中{match_label}，点击该联系人")
                if not self._click_contact(tab, contact, index):
                    continue
                self._delay(1.0, 1.6)
                if self._active_chat_matches_company(tab, company_name, hr_name):
                    log.info(f"    ✅ 第{index}项点击后右侧会话校验通过，准备发送AI消息")
                    return True
                log.info(f"    ↪️ 第{index}项列表文本虽命中但右侧未通过最终校验，继续检查下一项")
                continue

            log.info(f"    🔍 点击第{index}项「{preview}」，打开后校验是否为「{company_name}」")
            if not self._click_contact(tab, contact, index):
                continue
            self._delay(1.0, 1.6)
            if self._active_chat_matches_company(tab, company_name, hr_name):
                log.info(f"    ✅ 第{index}项会话校验通过，准备发送AI消息")
                return True
            log.info(f"    ↪️ 第{index}项不是目标公司，继续检查下一项")

        log.warning(f"    ⚠️ 前{min(len(candidates), limit)}项均未校验为公司「{company_name}」，跳过AI消息发送，避免发错人")
        return False

    def _find_chat_contact(self, tab, company_name: str = ""):
        if company_name and company_name != "未知公司":
            for frag in self._company_match_fragments(company_name):
                contact = tab.ele(f'text:{frag}', timeout=2)
                if contact:
                    log.info(f"    🎯 通过文本片段「{frag}」定位到联系人")
                    return contact
        log.warning("    ⚠️ 未匹配到目标公司联系人，跳过第一项兜底")
        return None

    def _find_chat_input(self, tab):
        log.info("    🔎 正在扫描聊天输入框...")
        def _is_usable_chat_input(ele) -> bool:
            try:
                return bool(ele.run_js("""
                    var el = this;
                    var rect = el.getBoundingClientRect();
                    var style = window.getComputedStyle(el);
                    if (rect.width <= 50 || rect.height <= 10) return false;
                    if (style.display === 'none' || style.visibility === 'hidden') return false;
                    if (el.closest('[class*="search"], [class*="filter"], [class*="comment"], [class*="resume"], [class*="upload"], [class*="attach"], [class*="profile"], [class*="job-detail"]')) return false;
                    var chatShell = el.closest('.chat-editor-area, .chat-box, .chat-main, [class*="chat"], [class*="message"], [class*="dialog"], [class*="im"]');
                    var parent = el.closest('.chat-editor-area, .chat-box, [class*="editor"], [class*="input"], [class*="footer"]') || el.parentElement;
                    var hasSend = !!(parent && parent.querySelector('.btn-send, [class*="send"], button'));
                    return !!(chatShell || hasSend);
                """))
            except Exception:
                return False

        try:
            result = tab.run_js("""
                var selectors = [
                    '.chat-editor-area [contenteditable="true"]',
                    '.chat-box [contenteditable="true"]',
                    '.chat-textarea',
                    '#chat-input',
                    'textarea.chat-input',
                    '[contenteditable="true"]',
                    'textarea'
                ];
                var els = [];
                for (var s = 0; s < selectors.length; s++) {
                    var nodes = document.querySelectorAll(selectors[s]);
                    for (var n = 0; n < nodes.length; n++) els.push(nodes[n]);
                }
                function usable(el) {
                    var rect = el.getBoundingClientRect();
                    var style = window.getComputedStyle(el);
                    if (rect.width <= 50 || rect.height <= 10) return false;
                    if (style.display === 'none' || style.visibility === 'hidden') return false;
                    if (el.closest('[class*="search"], [class*="filter"], [class*="comment"], [class*="resume"], [class*="upload"], [class*="attach"], [class*="profile"], [class*="job-detail"]')) return false;
                    var chatShell = el.closest('.chat-editor-area, .chat-box, .chat-main, [class*="chat"], [class*="message"], [class*="dialog"], [class*="im"]');
                    var parent = el.closest('.chat-editor-area, .chat-box, [class*="editor"], [class*="input"], [class*="footer"]') || el.parentElement;
                    var hasSend = !!(parent && parent.querySelector('.btn-send, [class*="send"], button'));
                    return !!(chatShell || hasSend);
                }
                var seen = new Set();
                for (var i = 0; i < els.length; i++) {
                    var el = els[i];
                    if (seen.has(el)) continue;
                    seen.add(el);
                    if (usable(el)) {
                        return el;
                    }
                }
                return null;
            """)
            if result:
                log.info("    🎯 JS快速扫描找到输入框")
                return result
        except Exception:
            pass
        fast_selectors = [
            'css:.chat-editor-area [contenteditable="true"]',
            'css:.chat-box [contenteditable]',
            'css:#chat-input',
            'css:textarea.chat-input',
            'css:.chat-textarea',
        ]
        for sel in fast_selectors:
            try:
                ele = tab.ele(sel, timeout=0.3)
                if ele and ele.is_displayed and _is_usable_chat_input(ele):
                    log.info(f"    🎯 快速定位到输入框: {sel}")
                    return ele
            except Exception:
                continue
        fallback_selectors = [
            'css:[contenteditable="true"]',
            'css:.base-input',
            'css:textarea',
            'xpath://*[@contenteditable="true" or name()="textarea"]'
        ]
        for sel in fallback_selectors:
            try:
                ele = tab.ele(sel, timeout=0.8)
                if ele and ele.is_displayed and _is_usable_chat_input(ele):
                    log.info(f"    🎯 兜底定位到输入框: {sel}")
                    return ele
            except Exception:
                continue
        log.info("    ↪️ 本轮未定位到可见聊天输入框")
        return None

    def _send_message(self, tab, chat_input, ai_message: str) -> bool:
        try:
            chat_input.click()
            self._delay(0.5, 1.0)
            chat_input.clear()
            log.info("    ⌨️ 正在逐字模拟真人输入AI消息...")
            _typed = []
            for ch in ai_message:
                self._delay(AI_CONFIG["typing_char_delay"], AI_CONFIG["typing_char_delay"])
                try:
                    chat_input.input(ch)
                    _typed.append(ch)
                except Exception as e:
                    log.warning(f"    ⚠️ 逐字输入异常，回退一次性输入剩余文本: {e}")
                    try:
                        chat_input.input(ai_message[len("".join(_typed)):])
                    except Exception:
                        pass
                    break
            self._delay(0.8, 1.5)
            try:
                chat_input.run_js("this.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:arguments[0]}))", ai_message)
            except Exception:
                pass
            send_btn = (tab.ele("css:.btn-send", timeout=1)
                        or tab.ele("text=发送", timeout=1)
                        or tab.ele('xpath://*[text()="发送"]', timeout=1)
                        or tab.ele('xpath://*[contains(@class,"send")]', timeout=1))
            if send_btn:
                try:
                    send_btn.click()
                except Exception:
                    chat_input.key_down("Enter")
                    chat_input.key_up("Enter")
            else:
                chat_input.key_down("Enter")
                chat_input.key_up("Enter")
            # 概率性失效兜底：再追加一次 Enter 键发送
            try:
                chat_input.click()
                self._delay(0.1, 0.2)
                chat_input.key_down("Enter")
                chat_input.key_up("Enter")
            except Exception:
                pass
            self._delay(AI_CONFIG["post_send_delay"], AI_CONFIG["post_send_delay"] + 1)
            log.info("    💬 AI消息发送成功！")
            return True
        except Exception as e:
            log.warning(f"    ⚠️ 消息发送异常: {e}")
            return False

    # ══════════════════════════════════════════
    # 核心：处理单个岗位卡片
    # ══════════════════════════════════════════
    def _process_job_card(self, card, keyword: str = "") -> bool:
        card_text = card.text or ""
        if "已沟通" in card_text or "继续沟通" in card_text:
            log.info("    ⏭  跳过 → UI界面已显示「已沟通」")
            return False

        record = JobRecord(time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), city=self.cfg["city"])
        detail_tab = None
        try:
            snapshot = self._job_card_snapshot(card)

            raw_position = snapshot.get("position") or _get_text(self._find_job_name(card)) or "未知职位"
            record.position = _strip_salary_from_position(raw_position)
            record.company = snapshot.get("company") or _get_text(self._find_company_name(card)) or "未知公司"
            record.salary = _decode_boss_obfuscated_digits(snapshot.get("salary") or "") or _get_full_text(self._find_salary(card)) or "未知薪资"
            raw_hr_name = snapshot.get("hr_name") or _get_text(self._find_hr_name(card))
            record.hr_name = self._clean_hr_name(raw_hr_name, record.company, record.position)
            record.hr_active = snapshot.get("hr_active") or _get_text(self._find_hr_active(card))
            if raw_hr_name and not record.hr_name:
                log.info(f"    🧹 列表页招聘人「{raw_hr_name}」疑似公司/职位/泛称，已清空")

            if record.company == "未知公司":
                log.warning(f"    ⚠️ 列表页公司名读取失败，将打开详情页补抓。HTML片段:\n{card.html[:1200]}\n{'─'*50}")

            log.info(f"    [{record.company}] {record.position}  {record.salary}  HR:{record.hr_name or '-'}  活跃:{record.hr_active or '-'}")

            skip_checked = False
            if record.company != "未知公司":
                reason = self._should_skip(record)
                skip_checked = True
                if reason:
                    log.info(f"    ⏭  跳过 → {reason}")
                    record.status, record.reason = "skipped", reason
                    self._save_record(record)
                    return False

            href = snapshot.get("href", "")
            if not href:
                job_link_ele = (card.ele("css:a.job-card-left", timeout=1)
                                or card.ele('xpath:.//a[contains(@href, "/job_detail/")]', timeout=1)
                                or card.ele("css:a", timeout=1))
                href = job_link_ele.attr("href") if job_link_ele else ""
            if not href:
                log.info("    ⏭  跳过 → 找不到详情链接")
                return False

            record.url = f"https://www.zhipin.com{href}" if href.startswith("/") else href

            detail_tab = self.browser.new_tab(record.url)
            try:
                detail_tab.wait.ele_loaded("css:.job-detail-card", timeout=5)
            except Exception:
                pass
            self._delay(1, 2)

            if not record.hr_name:
                detail_hr = self._find_hr_name_from_detail(detail_tab)
                cleaned_detail_hr = self._clean_hr_name(detail_hr, record.company, record.position)
                if cleaned_detail_hr:
                    record.hr_name = cleaned_detail_hr
                    log.info(f"    👤 详情页补抓招聘人: {record.hr_name}")
                elif detail_hr:
                    log.info(f"    🧹 详情页招聘人「{detail_hr}」疑似公司/职位/泛称，已清空")

            if record.company == "未知公司":
                detail_company = self._find_company_name_from_detail(detail_tab)
                if detail_company:
                    record.company = detail_company
                    log.info(f"    🏢 详情页补抓公司名: {record.company}")
                else:
                    log.warning("    ⚠️ 详情页仍未抓到公司名，本条将以未知公司记录")
            if record.hr_name:
                cleaned_hr = self._clean_hr_name(record.hr_name, record.company, record.position)
                if not cleaned_hr:
                    log.info(f"    🧹 招聘人「{record.hr_name}」与公司/职位冲突，已清空")
                record.hr_name = cleaned_hr

            if not skip_checked:
                reason = self._should_skip(record)
                if reason:
                    log.info(f"    ⏭  跳过 → {reason}")
                    record.status, record.reason = "skipped", reason
                    self._save_record(record)
                    detail_tab.close()
                    return False

            job_desc = self._scrape_job_description(detail_tab)

            jd_skip_reason = self._should_skip_by_jd(job_desc)
            if jd_skip_reason:
                log.info(f"    ⏭  跳过 → {jd_skip_reason}")
                record.status, record.reason = "skipped", jd_skip_reason
                self._save_record(record)
                detail_tab.close()
                return False

            job_is_campus = is_campus_job(job_desc, record.position)
            profile_key, profile = select_resume_profile(
                record.position, record.company, job_desc,
                search_keyword=keyword,
            )
            record.resume_type = f"{profile_key}_{'campus' if job_is_campus else 'experienced'}"
            fit_score, fit_reason = calculate_job_fit_score(
                profile_key, profile, record.position, record.company,
                job_desc, record.salary, search_keyword=keyword,
            )
            log.info(f"    🧭 岗位适配分: {fit_score}（画像={profile_key}，{fit_reason}）")
            min_fit_score = int(self.cfg.get("min_fit_score", 0) or 0)
            if min_fit_score > 0 and fit_score < min_fit_score:
                reason = f"岗位适配分过低（{fit_score} < {min_fit_score}，{fit_reason}）"
                log.info(f"    ⏭  跳过 → {reason}")
                record.status, record.reason = "skipped", reason
                self._save_record(record)
                detail_tab.close()
                return False

            if job_is_campus:
                log.info("    🎓 检测到校招/应届岗，使用学生版简历")
            else:
                log.info("    💼 检测到社招岗，使用项目/实习经历口径")

            if AI_CONFIG["enabled"] and AI_CONFIG.get("jd_relevance_filter_enabled", True):
                log.info("    🤖 正在用AI判断JD与候选人能力是否相关...")
                is_relevant, ai_reason, missing_tools = judge_job_relevance_by_ai(
                    record.position, record.company, job_desc,
                    RESUME_BASE_FACTS.get("core_stack", ""),
                )
                if not is_relevant:
                    tools_text = "、".join(missing_tools) if missing_tools else "未列出"
                    reason = f"AI判定JD不相关：{ai_reason}（未掌握工具：{tools_text}）"
                    if self.cfg.get("test_mode", False):
                        print("\n" + "═" * 60)
                        print("【测试模式】AI JD 相关性筛选 → 跳过（不投递）")
                        print(f"公司：{record.company} | 职位：{record.position} | HR：{record.hr_name or '-'}")
                        print("─" * 60)
                        print(f"AI判定：跳过")
                        print(f"原因：{ai_reason}")
                        print(f"未掌握工具：{tools_text}")
                        print("═" * 60 + "\n")
                    log.info(f"    ⏭  跳过 → {reason}")
                    record.status, record.reason = "skipped", reason
                    self._save_record(record)
                    detail_tab.close()
                    return False

            apply_btn = (detail_tab.ele("css:.btn-startchat", timeout=2)
                         or detail_tab.ele("立即沟通", timeout=2)
                         or detail_tab.ele("css:.op-btn-chat", timeout=2))

            if not apply_btn:
                log.info("    ⚠️  跳过 → 未找到沟通按钮")
                record.status, record.reason = "skipped", "未找到沟通按钮"
                detail_tab.close()
                self._save_record(record)
                return False

            ai_message = ""
            if AI_CONFIG["enabled"]:
                log.info(f"    🤖 正在生成AI打招呼语（{AI_CONFIG['model']}）...")
                ai_message = call_mimo_api(
                    job_desc, profile, is_campus=job_is_campus,
                    position=record.position, company=record.company,
                )
                if ai_message:
                    record.ai_greeting = ai_message
                    log.info(f"    💡 AI生成内容: {ai_message[:60]}...")
                else:
                    log.info("    ⚠️ AI生成失败，将仅发送默认招呼语")

            if self.cfg.get("test_mode", False):
                print("\n" + "═" * 60)
                print(f"【测试模式】AI 招呼语（不发送、不投递）")
                print(f"公司：{record.company} | 职位：{record.position} | HR：{record.hr_name or '-'}")
                print("─" * 60)
                print(ai_message if ai_message else "（AI 生成失败，无招呼语）")
                print("═" * 60 + "\n")
                record.status, record.reason = "test_only", "test_mode 未发送"
                self._save_record(record)
                detail_tab.close()
                return False

            apply_btn.run_js("this.scrollIntoView({block:'center'})")
            self._delay(0.3, 0.5)
            # 方法1: DrissionPage 原生点击（模拟真实鼠标）
            try:
                detail_tab.actions.move_to(apply_btn).click()
            except Exception:
                try:
                    apply_btn.click()
                except Exception:
                    apply_btn.run_js("this.click()")
            self._delay(1, 1.5)
            log.info(f"    🔍 点击后URL: {detail_tab.url}")

            dialog = detail_tab.ele("css:.dialog-con", timeout=2) or detail_tab.ele("css:.modal-con", timeout=2)
            confirm_btn = None
            if dialog:
                confirm_btn = (dialog.ele("css:.btn-sure", timeout=1)
                               or dialog.ele("css:.btn-primary", timeout=1)
                               or dialog.ele("css:button", timeout=1))
            if not confirm_btn:
                # 兜底：在页面上找弹窗区域内的确认按钮
                confirm_btn = (detail_tab.ele("css:.dialog-con .btn-sure", timeout=1)
                               or detail_tab.ele("css:.modal-con .btn-sure", timeout=1)
                               or detail_tab.ele("css:.dialog .btn-sure", timeout=1))

            if confirm_btn:
                log.info(f"    📌 检测到首次沟通弹窗，点击确认按钮... 标签={confirm_btn.tag} 文本={confirm_btn.text}")
                confirm_btn.run_js("this.scrollIntoView({block:'center'})")
                self._delay(0.2, 0.3)
                # 优先用 actions 模拟真实点击
                try:
                    detail_tab.actions.move_to(confirm_btn).click()
                except Exception:
                    try:
                        confirm_btn.click()
                    except Exception:
                        confirm_btn.run_js("this.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}))")
                self._delay(1.5, 2.0)
                # 如果弹窗还在，再试一次
                if detail_tab.ele("css:.dialog-con", timeout=1) or detail_tab.ele("css:.modal-con", timeout=1):
                    confirm_btn.run_js("this.click()")
                    self._delay(1, 1.5)
                if ai_message:
                    sent = self._try_send_in_current_tab(detail_tab, ai_message, record.company, record.hr_name)
                    if not sent:
                        log.warning("    ⚠️ 当前tab未找到输入框，尝试fallback导航...")
                        sent = self._goto_chat_and_send(detail_tab, ai_message, record.company, record.hr_name)
                        if not sent:
                            log.warning("    ⚠️ AI消息未发送成功，仅记录投递动作")
            else:
                log.info("    📌 未检测到弹窗，等待页面跳转后发送...")
                self._delay(1.5, 2.0)
                if ai_message:
                    sent = self._try_send_in_current_tab(detail_tab, ai_message, record.company, record.hr_name)
                    if not sent:
                        log.warning("    ⚠️ 当前tab未找到输入框，尝试fallback导航...")
                        sent = self._goto_chat_and_send(detail_tab, ai_message, record.company, record.hr_name)
                        if not sent:
                            log.warning("    ⚠️ AI消息未发送成功，仅记录投递动作")

            record.status = "applied"
            log.info(f"    ✅ 投递成功！[{record.company}] {record.position}")
            self._save_record(record)

            detail_tab.close()
            self._delay(self.cfg["apply_interval_min"], self.cfg["apply_interval_max"])
            return True

        except Exception as e:
            log.warning(f"    ❌ 投递异常: {e}")
            record.status, record.reason = "failed", str(e)
            self._save_record(record)
            if detail_tab:
                try:
                    detail_tab.close()
                except Exception:
                    pass
            return False

    def _is_anonymous_company_name(self, company_name: str) -> bool:
        compact = re.sub(r"\s+", "", company_name or "")
        if not compact or compact == "未知公司":
            return False
        markers = self.cfg.get("anonymous_company_markers", [])
        if any(marker and marker in compact for marker in markers):
            return True
        return bool(re.search(r"某.{0,18}(公司|集团|企业|平台|厂|银行|证券|软件|科技|计算机|互联网|ICT|终端)", compact))

    def _headhunter_skip_reason(self, record: JobRecord) -> str:
        if not self.cfg.get("skip_anonymous_headhunter_jobs", True):
            return ""
        company = record.company or ""
        company_lower = company.lower()
        position_lower = (record.position or "").lower()
        if self._is_anonymous_company_name(company):
            return "匿名代招/猎头岗位（公司名不可校验）"
        position_only_keywords = {"猎头", "代招", "rpo"}
        for kw in self.cfg.get("headhunter_keywords", []):
            if not kw:
                continue
            kw_lower = kw.lower()
            if kw_lower in company_lower or (kw_lower in position_only_keywords and kw_lower in position_lower):
                return f"疑似猎头/代招岗位（命中「{kw}」）"
        return ""

    def _should_skip(self, record: JobRecord) -> str:
        if (record.company, record.position) in self.applied_history:
            return "本地历史记录已投递过"
        if (record.company, record.position) in self.skipped_history:
            return "本地历史记录曾跳过"
        headhunter_reason = self._headhunter_skip_reason(record)
        if headhunter_reason:
            return headhunter_reason
        max_salary = self.cfg.get("max_salary_k", 13)
        if max_salary > 0:
            salary_upper = _parse_salary_upper_bound_k(record.salary)
            if salary_upper is not None and salary_upper > max_salary:
                return f"薪资过高（{record.salary}，上限 {salary_upper}K > {max_salary}K）"
        min_salary = self.cfg.get("min_salary_k", 0)
        if min_salary > 0:
            salary_lower_bound = _parse_salary_upper_bound_k(record.salary)
            if salary_lower_bound is not None and salary_lower_bound < min_salary:
                return f"薪资过低（{record.salary}，下限 {salary_lower_bound}K < {min_salary}K）"
        combined = (record.position + " " + record.company).lower()
        for kw in self.cfg["skip_keywords"]:
            if kw.lower() in combined:
                return f"含跳过词「{kw}」"
        if self.cfg["require_keywords"]:
            if not any(kw.lower() in record.position.lower() for kw in self.cfg["require_keywords"]):
                return "不含必要关键词"
        if self.cfg["skip_if_not_active"]:
            for hint in ["半年前", "一年前", "很久前"]:
                if hint in record.hr_active:
                    return f"HR不活跃（{record.hr_active}）"
        return ""

    def _should_skip_by_jd(self, job_desc: str) -> str:
        if not job_desc:
            return ""
        jd_lower = job_desc.lower()
        jd_keywords = self.cfg.get("jd_skip_keywords", [])
        for kw in jd_keywords:
            if kw and kw.lower() in jd_lower:
                return f"JD含跳过词「{kw}」"
        return ""


# ══════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  Boss直聘 自动投递 v22 (视觉传达设计-王文静)")
    print(f"  AI模型: {AI_CONFIG['model']}")
    print(f"  AI打招呼: {'已启用' if AI_CONFIG['enabled'] else '已关闭'}")
    print(f"  AI JD筛选: {'已启用' if (AI_CONFIG['enabled'] and AI_CONFIG.get('jd_relevance_filter_enabled', True)) else '已关闭'}")
    print(f"  排序模式: scene={CONFIG['scene_param']} (3=最新, 1=推荐)")
    print(f"  经验要求: {'校招/应届' if CONFIG['is_campus_recruitment'] else '全岗位（自动识别校招/社招）'}")
    print(f"  投递间隔: {CONFIG['apply_interval_min']}~{CONFIG['apply_interval_max']}s")
    if AI_CONFIG["enabled"]:
        api_key_preview = AI_CONFIG["api_key"][:8] + "****" if AI_CONFIG["api_key"] else "未配置"
        print(f"  API Key: {api_key_preview}")
    print("=" * 60)

    run_pid = _claim_single_instance()
    try:
        applier = BossApplier(CONFIG)
        if applier.run() is False:
            sys.exit(1)
    finally:
        _release_single_instance(run_pid)
