"""
Boss直聘 自动投递脚本 v21
────────────────────────────────────────────────
v21 更新项：
1. 【新增】scene=3 最新排序支持，CONFIG 中可配置 scene_param
2. 【新增】启动时自动嗅探 API 实际参数，验证 scene=3 是否生效
3. 【优化】简历画像细分为 Java/Python AI/Python自动化/全栈/前端/Android
4. 【修复】聊天页 fallback 按公司名逐项校验，避免发错联系人
5. 【修复】历史 CSV 表头兼容升级，今日上限读取本地历史
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
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from DrissionPage import ChromiumOptions, ChromiumPage

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
                key, value = key.strip(), value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                if key not in os.environ:
                    os.environ[key] = value

_load_env()

if not os.environ.get("DASHSCOPE_API_KEY"):
    print("[WARNING] DASHSCOPE_API_KEY 未在 .env 中设置，AI 问候语功能将被禁用")

# ══════════════════════════════════════════════
# 投递配置区
# ══════════════════════════════════════════════
CONFIG = {
    # ── 关键词（短词，覆盖面更广）──────────────────────────────
    "keywords": [
        "java",
        "python",
        "后端开发",
        "前端开发",
        "全栈开发",
        "软件开发",
        "Android",
        "小程序开发",
    ],

    "city": "深圳",
    "max_apply_per_keyword": 10,
    "max_apply_per_day": 150,

    "apply_interval_min": 2,
    "apply_interval_max": 3,
    "page_turn_interval": (2, 3),

    # ── 校招开关（v20 关闭，不再限制应届）─────────────────────
    "is_campus_recruitment": False,
    "experience_param": "102",         # is_campus_recruitment=True 时才生效

    # ── ★ 最新排序（scene 参数）────────────────────────────────
    # scene=1: 推荐（默认算法排序）
    # scene=3: 最新（按发布时间倒序，手机端「最新」tab对应值）
    # 启动时会自动嗅探验证是否生效，失败则回退 scene=1
    "scene_param": "3",
    "scene_sniff_verify": True,        # True=启动时验证 scene=3 是否真实生效

    # ── 过滤规则──────────────────────────────────────────────
    "skip_keywords": [
        # 硬件 / 电气 / 芯片
        "硬件工程师", "硬件开发", "电气工程师", "电路设计", "PCB",
        "射频", "芯片", "FPGA", "单片机", "电子工程师",
        # 机械 / 结构
        "结构工程师", "机械工程师", "机械自动化工程师", "电气自动化工程师", "设备自动化工程师",
        "电力工程师", "强电", "弱电安装",
        # 无人机硬件
        "无人机硬件", "飞控硬件", "无人机电气",
        # 制造 / 装配
        "装配工程师", "装配", "焊接", "制造工程师", "生产工程师",
        "质量工程师", "品质工程师", "工艺工程师", "维修工程师",
        # 非技术岗
        "销售", "运营", "产品经理", "市场", "客服", "行政",
        "财务", "会计", "人事", "HR",
        # 外包 / 驻场
        "外包", "驻场", "外派",
    ],
    "require_keywords": [],             # 留空=不限制，否则职位名必须含其中之一
    "skip_if_not_active": True,
    "skip_anonymous_headhunter_jobs": True,  # 跳过匿名代招/猎头岗，避免聊天页无法按真实公司校验
    "chat_contact_scan_limit": 8,       # fallback 聊天列表最多检查几项，防止被新消息挤下去后长时间空转
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
}

# ══════════════════════════════════════════════
# AI 配置区
# ══════════════════════════════════════════════
AI_CONFIG = {
    "api_key": os.environ.get("DASHSCOPE_API_KEY", ""),
    "model": os.environ.get("DASHSCOPE_MODEL", "qwen3.7-max"),
    "api_url": os.environ.get("DASHSCOPE_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"),
    "api_timeout": 25,
    "api_retry": 1,
    "post_send_delay": 2,
    "enabled": bool(os.environ.get("DASHSCOPE_API_KEY")),
}

# ══════════════════════════════════════════════
# 简历画像配置
# ══════════════════════════════════════════════
RESUME_PROFILES = {
    "android": {
        "match_keywords": ["安卓", "android", "kotlin", "移动端", "app开发", "手机端", "原生", "app"],
        "specific_keywords": ["android", "kotlin", "移动端", "app开发", "原生", "retrofit"],
        "target_job": "Android原生开发",
        "skills": "Android Java/Kotlin、Material Design 3、Retrofit2、WebSocket、后端接口联调。",
        "campus_pitch": "应届/实习口径：独立完成装修管理App，熟悉Android Java/Kotlin、Retrofit2、WebSocket和Material Design 3，也有Java后端重构经历。",
        "experienced_pitch": "经验版表达：突出移动端完整项目交付、接口联调、实时通信和Java后端协作能力，不主动强调应届身份。",
        "proof_points": [
            "装修管理App：独立完成移动端核心流程，使用Material Design 3、Retrofit2、WebSocket。",
            "Java后端重构：参与安卓与Web后端整合，推动多个版本上线。",
            "能同时理解移动端体验、接口协议和后端数据流。",
        ],
        "avoid_claims": ["不要声称做过大型商业App上架", "不要虚构团队管理经历"],
    },
    "java_backend": {
        "match_keywords": ["java", "后端", "spring", "springboot", "spring boot", "服务端", "后台开发", "接口", "mysql", "jpa"],
        "specific_keywords": ["spring", "springboot", "spring boot", "jpa", "rbac", "websocket", "mysql", "权限", "接口", "后端"],
        "target_job": "Java后端开发",
        "skills": "Spring Boot 3、Spring Data JPA、RESTful API、RBAC、WebSocket、MySQL、乐观锁。",
        "campus_pitch": "应届/实习口径：有5个月Java实习经历，做过Spring Boot 3、JPA、RESTful API、RBAC权限、WebSocket实时推送和数据库乐观锁。",
        "experienced_pitch": "经验版表达：突出Java后端项目交付、系统重构、权限模型、接口设计、MySQL和稳定性意识，不主动强调在校/实习。",
        "proof_points": [
            "后端重构：主导安卓与Web后端系统整合重构，推动V1.0.0-V1.0.83多版本上线。",
            "权限与实时能力：实现RBAC权限模型、WebSocket实时推送、RESTful接口。",
            "数据一致性：用数据库乐观锁处理并发更新，熟悉MySQL/JPA落地。",
        ],
        "avoid_claims": ["不要虚构微服务大规模生产经验", "不要说精通JVM，除非JD强要求且只轻描淡写"],
    },
    "python_ai_app": {
        "match_keywords": ["python", "ai", "人工智能", "大模型", "llm", "prompt", "agent", "deepseek", "通义", "openai", "aigc"],
        "specific_keywords": ["ai", "人工智能", "大模型", "llm", "prompt", "agent", "deepseek", "通义", "aigc"],
        "target_job": "Python后端/AI应用开发",
        "skills": "Python、AI API集成、Prompt设计、任务流编排、SQLite/MySQL、并发安全。",
        "campus_pitch": "应届/实习口径：独立完成AI网文写作自动化系统，熟悉Python、DeepSeek/通义千问API集成、Prompt流程和SQLite/MySQL并发安全。",
        "experienced_pitch": "经验版表达：突出AI应用从0到1交付、大模型API接入、任务流拆解、数据落库和工程化稳定性，不主动强调应届身份。",
        "proof_points": [
            "AI网文写作自动化系统：独立设计任务流，完成大模型API接入、生成流程控制和数据落库。",
            "模型集成：对接DeepSeek/通义千问，关注Prompt结构、重试、异常兜底和输出质量。",
            "数据与并发：有SQLite/MySQL并发安全设计经验，也能结合Java后端思路做工程化。",
        ],
        "avoid_claims": ["不要声称训练或微调过大模型", "不要虚构LangChain/向量库经验，除非JD只是泛泛提到可学习"],
    },
    "python_automation": {
        "match_keywords": ["python", "自动化", "爬虫", "脚本", "数据处理", "数据清洗", "采集", "selenium", "接口自动化", "办公自动化"],
        "specific_keywords": ["自动化", "爬虫", "脚本", "数据处理", "数据清洗", "采集", "selenium", "接口自动化"],
        "target_job": "Python自动化/数据处理",
        "skills": "Python脚本、流程自动化、接口对接、数据处理、SQLite/MySQL、异常重试。",
        "campus_pitch": "应届/实习口径：做过AI自动化系统和脚本化流程，熟悉Python接口调用、数据处理、异常重试和SQLite/MySQL落库。",
        "experienced_pitch": "经验版表达：突出Python自动化流程设计、接口对接、数据清洗/落库、异常兜底和可维护脚本能力。",
        "proof_points": [
            "自动化系统：独立拆解任务流程，处理API调用、状态记录、失败重试和结果持久化。",
            "数据处理：有SQLite/MySQL落库与并发安全经验，能做清洗、去重、状态追踪。",
            "工程习惯：关注日志、异常兜底、配置化和重复任务提效。",
        ],
        "avoid_claims": ["不要虚构高并发爬虫集群经验", "不要承诺绕过风控或反爬"],
    },
    "fullstack": {
        "match_keywords": ["全栈", "软件开发", "系统开发", "平台开发", "web开发", "管理系统", "前后端", "vue", "react", "node"],
        "specific_keywords": ["全栈", "前后端", "管理系统", "平台开发", "vue", "react", "web开发"],
        "target_job": "全栈/软件开发",
        "skills": "Java/Python后端、Vue3基础、Android、RESTful API、数据库设计、项目交付。",
        "campus_pitch": "应届/实习口径：有Java/Python全栈背景，做过后端重构、Android App和AI自动化系统，能从接口、数据库到前端联调推进落地。",
        "experienced_pitch": "经验版表达：突出跨端项目交付、后端接口设计、数据库建模、前后端联调和问题闭环能力。",
        "proof_points": [
            "跨端经历：Java后端、Android App、Python AI自动化都有完整项目经验。",
            "后端能力：RESTful接口、RBAC权限、WebSocket、数据库并发控制。",
            "交付能力：能拆需求、做接口、处理数据、联调页面并推动版本上线。",
        ],
        "avoid_claims": ["不要把自己说成资深前端", "React/Vue只在JD需要时轻量提及"],
    },
    "frontend": {
        "match_keywords": ["前端", "vue", "vue3", "react", "typescript", "javascript", "html", "css", "小程序", "uniapp"],
        "specific_keywords": ["前端", "vue", "vue3", "react", "typescript", "javascript", "小程序", "uniapp"],
        "target_job": "前端/前后端联调",
        "skills": "Vue3/前端基础、RESTful接口联调、后端数据结构理解、Android UI经验。",
        "campus_pitch": "应届/实习口径：有前端基础和跨端项目经验，理解后端接口、权限数据和移动端交互，能快速参与Vue/React页面联调。",
        "experienced_pitch": "经验版表达：突出前后端联调、接口理解、业务页面落地和跨端协作，不把自己包装成纯资深前端。",
        "proof_points": [
            "有Android界面和交互项目经验，对组件、状态和接口联调不陌生。",
            "Java后端经历帮助理解RESTful接口、权限模型和数据结构。",
            "可承接后台管理、业务表单、接口联调和问题定位。",
            "有vue3基础，能快速参与Vue/React页面联调。"
        ],
        "avoid_claims": ["不要声称精通React/Vue源码", "不要虚构大型前端工程经验"],
    },
    "default": {
        "match_keywords": [],
        "specific_keywords": [],
        "target_job": "软件开发",
        "skills": "Java/Python、Spring Boot、Android、AI API、数据库、接口设计。",
        "campus_pitch": "应届/实习口径：具备Java/Python全栈开发能力，做过后端重构、Android App和AI自动化系统，有完整项目交付意识。",
        "experienced_pitch": "经验版表达：突出软件开发通用能力、后端接口、数据库、自动化工具和跨技术栈项目落地。",
        "proof_points": [
            "Java后端：Spring Boot、JPA、RBAC、WebSocket、MySQL。",
            "Python/AI：AI API集成、任务流、SQLite/MySQL并发安全。",
            "跨端：Android App、接口联调、版本迭代。",
        ],
        "avoid_claims": ["不要泛泛说学习能力强，必须用项目事实支撑"],
    },
}

PROFILE_PRIORITY = [
    "java_backend",
    "python_ai_app",
    "python_automation",
    "fullstack",
    "android",
    "frontend",
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

_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_stream_handler)

_file_handler = logging.handlers.RotatingFileHandler(
    "boss_auto_apply.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_file_handler)


class QwenAPIError(RuntimeError):
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
        return ele.text.strip() if ele else ""
    except Exception:
        return ""

def _get_full_text(ele) -> str:
    if not ele:
        return ""
    try:
        result = ele.run_js("return this.textContent.trim()")
        text = str(result).strip() if result else ""
        return text if text else _get_text(ele)
    except Exception:
        return _get_text(ele)

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

        if score > best_score:
            best_key = profile_key
            best_score = score
            best_reason = "、".join(reasons[:3]) if reasons else "JD弱命中"

    if best_score > 0:
        log.info(f"    📄 画像匹配: 【{best_key}】← {best_reason}，score={best_score}")
        return best_key, RESUME_PROFILES[best_key]

    log.info("    📄 未命中特定画像，使用默认全栈简历")
    return "default", RESUME_PROFILES["default"]

def _qwen_api_error_from_http(error: urllib.error.HTTPError) -> QwenAPIError:
    response_text = error.read().decode("utf-8", errors="replace")
    error_code = ""
    message = response_text.strip() or str(error)
    try:
        data = json.loads(response_text)
        detail = data.get("error", {}) if isinstance(data, dict) else {}
        if isinstance(detail, dict):
            error_code = str(detail.get("code") or detail.get("type") or "")
            message = str(detail.get("message") or message)
    except Exception:
        pass

    parts = [f"HTTP {error.code}"]
    if error_code:
        parts.append(error_code)
    if message:
        parts.append(message)
    return QwenAPIError(" - ".join(parts), error.code, error_code, response_text)


def _qwen_error_hint(error: Exception) -> str:
    if isinstance(error, QwenAPIError):
        if error.error_code == "AllocationQuota.FreeTierOnly":
            return (
                "原因：该模型免费额度已耗尽，且阿里百炼控制台开启了“仅使用免费额度”。"
                "处理：到阿里百炼控制台关闭“仅使用免费额度”或开通付费调用后重启脚本。"
            )
        if error.status_code in (401, 403):
            return "请检查 API Key 是否有效、Key 所属地域/Base URL 是否一致、业务空间权限/IP 白名单/账户余额是否正常。"
    return ""


def _is_non_retryable_qwen_error(error: Exception) -> bool:
    return isinstance(error, QwenAPIError) and error.status_code in (400, 401, 403)


_no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _call_qwen_api(payload: dict, timeout: int = 25, retries: int = 1) -> dict:
    data = json.dumps(payload).encode("utf-8")
    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                AI_CONFIG["api_url"], data=data,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {AI_CONFIG['api_key']}"},
                method="POST",
            )
            with _no_proxy_opener.open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_error = _qwen_api_error_from_http(e)
            if attempt < retries and not _is_non_retryable_qwen_error(last_error):
                log.warning(f"    ⚠️ API第{attempt+1}次调用失败: {last_error}，1秒后重试...")
                time.sleep(1)
            else:
                break
        except Exception as e:
            last_error = e
            if attempt < retries:
                log.warning(f"    ⚠️ API第{attempt+1}次调用失败: {e}，1秒后重试...")
                time.sleep(1)
    raise last_error or RuntimeError("Unknown API error")

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
    return f"""岗位方向：{profile.get('target_job', '软件开发')}
技能栈：{profile.get('skills', '')}
表达口径：{pitch}
可使用的真实项目证据：
{proof_points}
禁止夸大/不要写：
{avoid_claims}"""

def call_qwen_api(job_desc: str, profile: dict, is_campus: bool = True,
                  position: str = "", company: str = "") -> str:
    if not AI_CONFIG["enabled"]:
        return ""

    # 根据校招/社招切换身份描述和 AI 提示
    if is_campus:
        identity = "你是一名正在求职的应届生，需要在Boss直聘上向HR发送第一条打招呼消息。"
        extra_hint = (
            "- 可以自然提到应届、实习、可到岗，但不要显得低姿态\n"
            "- 重点写项目事实和能上手的技术点\n"
        )
    else:
        identity = "你是一名按1~2年开发经验口径沟通的求职者，需要在Boss直聘上向HR发送第一条打招呼消息。"
        extra_hint = (
            "- 不要提及任何学校、在校、应届、实习等字眼\n"
            "- 可以说项目经历、开发经历、交付经历，但不要虚构公司规模、团队管理、用户量\n"
        )
    profile_facts = _format_profile_facts(profile, is_campus)

    prompt = f"""{identity}

【目标岗位】
公司：{company or "目标公司"}
职位：{position or profile.get('target_job', '软件开发')}

【我的能力画像】
{profile_facts}

【目标职位描述】
{job_desc[:800]}

【生成规则】
- 先理解JD最关键的1~2个要求，再从“真实项目证据”里选最匹配的2个点
- 写成一段自然的Boss直聘首条沟通消息，正文70~100字；稍后系统会另附博客链接
- 结构：看到岗位/方向 → 我做过的相关项目事实 → 能匹配岗位的技术点 → 期待进一步交流
- 不要堆砌技能名，不要写成简历摘要，不要像模板
- 开头不要用“您好”，不要称呼“贵司”超过1次
- 不要出现“精通”“资深”“负责过千万级/高并发”等无法证明的夸大表述
{extra_hint}- 不要加任何额外解释，直接输出消息正文

请直接输出打招呼消息："""

    payload = {
        "model": AI_CONFIG["model"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200, "temperature": 0.8, "stream": False, "enable_thinking": False,
    }
    try:
        result = _call_qwen_api(payload, timeout=AI_CONFIG.get("api_timeout", 25),
                                retries=AI_CONFIG.get("api_retry", 1))
        message = result["choices"][0]["message"]["content"].strip()
        message = re.sub(r"<think>.*?</think>", "", message, flags=re.IGNORECASE | re.DOTALL).strip()
        message = re.sub(r"^```(?:text|markdown)?\s*|\s*```$", "", message, flags=re.IGNORECASE).strip()
        message = re.sub(r"\s+", " ", message).strip()
        if not message:
            return ""
        message = f"{message}\n个人博客(含项目展示)：http://119.29.249.127"
        
        return message
    except Exception as e:
        hint = _qwen_error_hint(e)
        log.warning(f"    ⚠️ AI API调用失败: {e}")
        if hint:
            log.warning(f"    ⚠️ {hint}")
        return ""

# ══════════════════════════════════════════════
# 主类
# ══════════════════════════════════════════════
class BossApplier:
    def __init__(self, config: dict):
        self.cfg = config
        self.total_applied = 0
        self.daily_applied = 0
        self.log_path = Path(self.cfg["log_file"])
        self.port = 9222
        self.applied_history = set()
        self.skipped_history = set()
        self._record_buffer = []
        self._fragment_cache = {}
        # 实际使用的 scene 参数（嗅探验证后可能回退为 "1"）
        self.active_scene = self.cfg.get("scene_param", "1")
        # 当前正在搜索的关键词（传给画像选择器用）
        self.current_keyword = ""
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
            return s.connect_ex(("127.0.0.1", self.port)) == 0

    def _launch_browser(self):
        if self._is_port_open():
            log.info(f"端口 {self.port} 已被占用，直接接管...")
            return True
        exe_path, user_data_dir = detect_browser()
        if not exe_path:
            log.error("未找到 Edge 浏览器！")
            return False
        log.info("正在启动 Edge 浏览器...")
        cmd = [exe_path, f"--remote-debugging-port={self.port}",
               f"--user-data-dir={user_data_dir}", "--no-first-run", "--no-default-browser-check"]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(15):
            if self._is_port_open():
                return True
            time.sleep(1)
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
            return
        co = ChromiumOptions()
        co.set_local_port(self.port)
        try:
            self.browser = ChromiumPage(co)
            log.info("✅ 成功接管本地 Edge 浏览器！")
        except Exception as e:
            log.error(f"❌ 无法连接浏览器: {e}")
            return

        try:
            boss_tab = None
            for tab_id in self.browser.tab_ids:
                tab = self.browser.get_tab(tab_id)
                if tab and "zhipin.com" in tab.url:
                    boss_tab = tab
                    break
            self.main_tab = boss_tab if boss_tab else self.browser.latest_tab

            if not self._ensure_logged_in():
                return

            # ── scene 验证 ──
            self._sniff_and_verify_scene()

            max_per_day = self.cfg.get("max_apply_per_day", 50)
            campus_str = "校招/应届" if self.cfg.get("is_campus_recruitment") else "全部经验"
            ai_status = "已启用" if AI_CONFIG["enabled"] else "已关闭"
            log.info(f"🎉 准备就绪！scene={self.active_scene} | 经验要求={campus_str} | AI={ai_status} | 每日上限={max_per_day}")

            if AI_CONFIG["enabled"]:
                self._test_api_connection()

            for keyword in self.cfg["keywords"]:
                if self.daily_applied >= max_per_day:
                    log.info(f"🛑 今日已达投递上限 ({max_per_day})，安全退出。")
                    break
                self._search_and_apply(keyword)

            log.info(f"\n🎉 运行结束！本次共投递 {self.total_applied} 个岗位，今日累计 {self.daily_applied} 次")

        except KeyboardInterrupt:
            log.info("\n⚠️ 用户中断 (Ctrl+C)，正在清理...")
        finally:
            self._flush_records()
            try:
                for tab in self.browser.tabs:
                    if tab != self.main_tab and "zhipin.com" in (tab.url or ""):
                        tab.close()
            except Exception:
                pass

    def _test_api_connection(self):
        log.info("🔌 正在测试阿里云API连通性...")
        test_payload = {
            "model": AI_CONFIG["model"],
            "messages": [{"role": "user", "content": "回复'ok'"}],
            "max_tokens": 10, "enable_thinking": False,
        }
        try:
            result = _call_qwen_api(test_payload, timeout=10, retries=0)
            reply = result["choices"][0]["message"]["content"].strip()
            log.info(f"✅ API连通正常！测试响应: {reply[:20]}")
        except Exception as e:
            log.warning(f"⚠️ API连通测试失败: {e}")
            hint = _qwen_error_hint(e)
            if hint:
                log.warning(f"⚠️ {hint}")
            AI_CONFIG["enabled"] = False
            log.warning("⚠️ 本次运行已自动关闭 AI 打招呼，避免每个岗位重复 API 失败；修复账号/额度后重启脚本即可恢复。")

    def _search_and_apply(self, keyword: str):
        city_code = CITY_CODES.get(self.cfg["city"], "101280600")

        self.current_keyword = keyword          # ★ 记录当前搜索词
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

            stale_restart = False
            for card in cards:
                if keyword_applied_count >= target_amount or self.daily_applied >= max_per_day:
                    break
                try:
                    if self._process_job_card(card):
                        keyword_applied_count += 1
                        self.total_applied += 1
                        self.daily_applied += 1
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
                    active_ele = self._find_hr_active(card, timeout=0.3)
                    return self._parse_active_score(_get_text(active_ele))
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
            'xpath://*[contains(@class,"job-sec") and not(contains(@class,"job-sec-keyword"))]',
        ]
        best_text = ""
        for sel in selectors:
            try:
                ele = detail_tab.ele(sel, timeout=2)
                if ele:
                    text = ele.text.strip()
                    if len(text) > len(best_text):
                        best_text = text
                    if len(best_text) > 100:
                        break
            except Exception:
                continue
        if best_text:
            log.info(f"    📋 成功抓取职位描述（{len(best_text)}字）")
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
        self._wait_for_vue_render(tab, max_wait=8)
        chat_input = self._find_chat_input(tab)
        if chat_input:
            log.info("    💬 在当前tab直接找到输入框，无需跳转")
            if company_name and company_name != "未知公司":
                log.info("    🔍 当前tab发送前按公司名确认联系人...")
                if not self._active_chat_matches_company(tab, company_name):
                    contact = self._click_first_contact(tab, company_name, hr_name)
                    if contact:
                        self._delay(1.0, 1.5)
                        chat_input = self._find_chat_input(tab)
                    else:
                        log.warning("    ⚠️ 当前tab联系人未通过公司校验，不直接发送")
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
                        log.info("    🔍 当前聊天页已有输入框，先按公司名确认联系人...")
                        if not self._active_chat_matches_company(from_tab, company_name):
                            contact = self._click_first_contact(from_tab, company_name, hr_name)
                            if contact:
                                self._delay(1.5, 2.0)
                                chat_input = self._find_chat_input(from_tab)
                            else:
                                log.warning("    ⚠️ 当前聊天页联系人未通过公司校验，跳过本条AI消息")
                                return False
                    return self._send_message(from_tab, chat_input, ai_message)
                log.warning("    ⚠️ 已在聊天页但输入框未找到，尝试激活联系人...")
                if self._click_first_contact(from_tab, company_name, hr_name):
                    self._delay(1.5, 2.0)
                    chat_input = self._find_chat_input(from_tab)
                    if chat_input:
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
                    log.info("    💬 跳转后右侧对话已展开，先按公司名确认联系人")
                    if not self._active_chat_matches_company(from_tab, company_name):
                        contact = self._click_first_contact(from_tab, company_name, hr_name)
                        if contact:
                            self._delay(1.5, 2.0)
                            chat_input = self._find_chat_input(from_tab)
                        else:
                            chat_input = None
                else:
                    log.info("    💬 跳转后右侧对话已展开，直接找到输入框")
            else:
                log.info("    🔍 跳转后右侧未展开，按公司名匹配联系人列表...")
                contact = self._click_first_contact(from_tab, company_name, hr_name)
                if contact:
                    self._delay(1.5, 2.0)
                    chat_input = self._find_chat_input(from_tab)
                else:
                    self._delay(0.5, 1)
                    chat_input = self._find_chat_input(from_tab)

            if chat_input:
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

        stop_fragments = set(city_names) | {"科技", "信息", "网络", "公司", "有限", "责任", "股份"}
        fragments = []
        for item in variants:
            for length in [10, 8, 6, 5, 4, 3, 2]:
                if len(item) >= length:
                    frag = item[:length]
                    if frag not in stop_fragments:
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

    def _active_chat_matches_company(self, tab, company_name: str) -> bool:
        if not company_name or company_name == "未知公司":
            return False
        text = ""
        try:
            text = tab.run_js("""
                var selectors = [
                    '.chat-header', '.message-header', '.dialog-header',
                    '.chat-main .user-name', '.chat-main [class*="company"]',
                    '[class*="chat"][class*="header"]',
                    '[class*="message"][class*="header"]'
                ];
                var vw = window.innerWidth || document.documentElement.clientWidth || 1200;
                for (var i = 0; i < selectors.length; i++) {
                    var nodes = document.querySelectorAll(selectors[i]);
                    for (var j = 0; j < nodes.length; j++) {
                        var node = nodes[j];
                        var rect = node.getBoundingClientRect();
                        if (rect.width < 80 || rect.height < 12) continue;
                        if (rect.left < vw * 0.30) continue;
                        var text = (node.innerText || node.textContent || '').trim();
                        if (text && text.length < 500) return text;
                    }
                }
                var chunks = [];
                var rightNodes = document.querySelectorAll('.chat-main, .chat-content, .message-content, [class*="chat-detail"], [class*="dialog"]');
                for (var k = 0; k < rightNodes.length; k++) {
                    var n = rightNodes[k];
                    var r = n.getBoundingClientRect();
                    if (r.width < 200 || r.height < 80 || r.left < vw * 0.30) continue;
                    var t = (n.innerText || n.textContent || '').trim();
                    if (t && t.length < 2000) chunks.push(t);
                    if (chunks.length >= 3) break;
                }
                if (chunks.length) return chunks.join('\\n').slice(0, 2000);
                return '';
            """)
            matched, frag = self._is_company_contact_text(text, company_name)
            if matched:
                log.info(f"    ✅ 右侧当前会话命中公司片段「{frag}」")
                return True
        except Exception:
            pass
        log.info(f"    ↪️ 右侧当前会话未命中「{company_name}」，可见标题/会话文本:「{self._preview_text(text, 70)}」")
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
        candidates = []
        seen = set()
        for sel in selectors:
            try:
                for ele in tab.eles(sel)[:limit * 3]:
                    if not self._is_chat_contact_candidate(ele):
                        continue
                    try:
                        rect = ele.run_js("var r = this.getBoundingClientRect(); return Math.round(r.left) + ':' + Math.round(r.top);")
                        key = str(rect)
                    except Exception:
                        key = id(ele)
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(ele)
                    if len(candidates) >= limit:
                        return candidates
            except Exception:
                continue
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
                if not self._is_chat_contact_candidate(ele):
                    continue
                key = id(ele)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(ele)
                if len(candidates) >= limit:
                    break
        except Exception:
            pass
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
            hr_matched, hr_frag = self._is_hr_contact_text(text, hr_name)
            if matched or hr_matched:
                match_label = f"公司片段「{frag}」" if matched else f"招聘人「{hr_frag}」"
                log.info(f"    ✅ 第{index}项列表文本命中{match_label}，点击该联系人")
                if not self._click_contact(tab, contact, index):
                    continue
                self._delay(1.0, 1.6)
                return True

            log.info(f"    🔍 点击第{index}项「{preview}」，打开后校验是否为「{company_name}」")
            if not self._click_contact(tab, contact, index):
                continue
            self._delay(1.0, 1.6)
            if self._active_chat_matches_company(tab, company_name):
                log.info(f"    ✅ 第{index}项校验通过，准备发送AI消息")
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
        selectors = [
            'css:[contenteditable="true"]', 'css:textarea.chat-input',
            'css:#chat-input', 'css:.chat-editor-area', 'css:.base-input',
            'css:.chat-box [contenteditable]', 'css:.chat-textarea', 'css:textarea',
            'xpath://*[@contenteditable="true" or name()="textarea"]'
        ]
        for sel in selectors:
            try:
                ele = tab.ele(sel, timeout=1.5)
                if ele and ele.is_displayed:
                    log.info(f"    🎯 定位到输入框: {sel}")
                    return ele
            except Exception:
                continue
        try:
            result = tab.run_js("""
                var els = document.querySelectorAll('[contenteditable="true"], textarea');
                for (var i = 0; i < els.length; i++) {
                    var el = els[i];
                    var rect = el.getBoundingClientRect();
                    var style = window.getComputedStyle(el);
                    if (rect.width > 50 && rect.height > 10 && style.display !== 'none' && style.visibility !== 'hidden') {
                        return el;
                    }
                }
                return null;
            """)
            if result:
                log.info("    🎯 JS扫描找到输入框")
                return result
        except Exception:
            pass
        log.info("    ↪️ 本轮未定位到可见聊天输入框")
        return None

    def _send_message(self, tab, chat_input, ai_message: str) -> bool:
        try:
            chat_input.click()
            self._delay(0.5, 1.0)
            chat_input.clear()
            log.info("    ⌨️ 正在模拟真人输入AI消息...")
            chat_input.input(ai_message)
            self._delay(0.8, 1.5)
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
            self._delay(AI_CONFIG["post_send_delay"], AI_CONFIG["post_send_delay"] + 1)
            log.info("    💬 AI消息发送成功！")
            return True
        except Exception as e:
            log.warning(f"    ⚠️ 消息发送异常: {e}")
            return False

    # ══════════════════════════════════════════
    # 核心：处理单个岗位卡片
    # ══════════════════════════════════════════
    def _process_job_card(self, card) -> bool:
        card_text = card.text or ""
        if "已沟通" in card_text or "继续沟通" in card_text:
            log.info("    ⏭  跳过 → UI界面已显示「已沟通」")
            return False

        record = JobRecord(time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), city=self.cfg["city"])
        detail_tab = None
        try:
            job_ele = self._find_job_name(card)
            company_ele = self._find_company_name(card)
            salary_ele = self._find_salary(card)

            record.position = _get_text(job_ele) or "未知职位"
            record.company = _get_text(company_ele) or "未知公司"
            record.salary = _get_full_text(salary_ele) or "未知薪资"
            record.hr_name = _get_text(self._find_hr_name(card))
            record.hr_active = _get_text(self._find_hr_active(card))

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

            job_link_ele = (card.ele("css:a.job-card-left", timeout=1)
                            or card.ele('xpath:.//a[contains(@href, "/job_detail/")]', timeout=1)
                            or card.ele("css:a", timeout=1))
            if not job_link_ele:
                log.info("    ⏭  跳过 → 找不到详情链接")
                return False

            href = job_link_ele.attr("href") or ""
            record.url = f"https://www.zhipin.com{href}" if href.startswith("/") else href

            detail_tab = self.browser.new_tab(record.url)
            try:
                detail_tab.wait.ele_loaded("css:.job-detail-card", timeout=5)
            except Exception:
                pass
            self._delay(1, 2)

            if not record.hr_name:
                detail_hr = self._find_hr_name_from_detail(detail_tab)
                if detail_hr:
                    record.hr_name = detail_hr
                    log.info(f"    👤 详情页补抓招聘人: {record.hr_name}")

            if record.company == "未知公司":
                detail_company = self._find_company_name_from_detail(detail_tab)
                if detail_company:
                    record.company = detail_company
                    log.info(f"    🏢 详情页补抓公司名: {record.company}")
                else:
                    log.warning("    ⚠️ 详情页仍未抓到公司名，本条将以未知公司记录")

            if not skip_checked:
                reason = self._should_skip(record)
                if reason:
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
                job_desc = self._scrape_job_description(detail_tab)

                # ── ★ v21: 智能判断校招/社招岗 ──
                job_is_campus = is_campus_job(job_desc, record.position)
                profile_key, profile = select_resume_profile(
                    record.position, record.company, job_desc,
                    search_keyword=self.current_keyword,
                )

                # 校招/社招只切换表达口径，不修改全局画像
                if job_is_campus:
                    log.info(f"    🎓 检测到校招/应届岗，使用学生版简历")
                    record.resume_type = f"{profile_key}_campus"
                else:
                    log.info(f"    💼 检测到社招岗，使用经验版简历（1~2年包装）")
                    record.resume_type = f"{profile_key}_experienced"

                log.info(f"    🤖 正在生成AI打招呼语（{AI_CONFIG['model']}）...")
                ai_message = call_qwen_api(
                    job_desc, profile, is_campus=job_is_campus,
                    position=record.position, company=record.company,
                )
                if ai_message:
                    record.ai_greeting = ai_message
                    log.info(f"    💡 AI生成内容: {ai_message[:60]}...")
                else:
                    log.info("    ⚠️ AI生成失败，将仅发送默认招呼语")

            apply_btn.click()
            self._delay(0.8, 1.5)

            confirm_btn = (detail_tab.ele("css:.dialog-con .btn-sure", timeout=2)
                           or detail_tab.ele("继续沟通", timeout=2)
                           or detail_tab.ele("继续投递", timeout=2))

            if confirm_btn:
                log.info("    📌 检测到首次沟通弹窗，点击「继续沟通」...")
                confirm_btn.click()
                self._delay(2, 3)
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


# ══════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  Boss直聘 自动投递 v21 (智能校招/社招双模式)")
    print(f"  AI模型: {AI_CONFIG['model']}")
    print(f"  AI打招呼: {'已启用' if AI_CONFIG['enabled'] else '已关闭'}")
    print(f"  排序模式: scene={CONFIG['scene_param']} (3=最新, 1=推荐)")
    print(f"  经验要求: {'校招/应届' if CONFIG['is_campus_recruitment'] else '全岗位（自动识别校招/社招）'}")
    print(f"  投递间隔: {CONFIG['apply_interval_min']}~{CONFIG['apply_interval_max']}s")
    if AI_CONFIG["enabled"]:
        api_key_preview = AI_CONFIG["api_key"][:8] + "****" if AI_CONFIG["api_key"] else "未配置"
        print(f"  API Key: {api_key_preview}")
    print("=" * 60)

    applier = BossApplier(CONFIG)
    applier.run()
