from pathlib import Path
import json
import re
import uuid
from contextlib import contextmanager
from functools import wraps
from flask import jsonify

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from ai.matching import (
    match_cv_jd,
    calculate_skill_matching,
)

from ai.llm_questions import (
    generate_llm_questions,
)

from database.connection import get_connection


bp = Blueprint("main", __name__)


# ============================================================
# 1. 5 TIÊU CHÍ ĐÁNH GIÁ CHUẨN
# ============================================================

EVALUATION_CRITERIA = [
    ("Knowledge / Technical Knowledge", 20),
    ("Problem Solving", 20),
    ("JD Fit", 20),
    ("Communication", 20),
    ("Cultural Fit", 20),
]

CRITERION_EVIDENCE = {
    "Knowledge / Technical Knowledge": {
        "keywords": [
            "kiến thức chuyên môn",
            "cơ sở dữ liệu",
            "postgresql",
            "sql",
            "truy vấn",
            "lập trình",
            "thuật toán",
            "thiết kế",
            "triển khai",
            "kiểm thử",
        ],
        "actions": [
            "sử dụng",
            "xây dựng",
            "thiết kế",
            "triển khai",
            "kiểm tra",
            "tối ưu",
        ],
    },

    "Problem Solving": {
        "keywords": [
            "vấn đề",
            "khó khăn",
            "nguyên nhân",
            "phân tích",
            "giải pháp",
            "xử lý",
            "khắc phục",
            "kiểm tra",
            "debug",
            "sự cố",
        ],
        "actions": [
            "phân tích nguyên nhân",
            "tìm nguyên nhân",
            "đề xuất phương án",
            "kiểm tra lỗi",
            "khắc phục lỗi",
            "xử lý vấn đề",
        ],
    },

    "JD Fit": {
        "keywords": [
            "yêu cầu công việc",
            "vị trí ứng tuyển",
            "mô tả công việc",
            "kỹ năng yêu cầu",
            "kinh nghiệm liên quan",
            "nhiệm vụ",
            "trách nhiệm",
        ],
        "actions": [
            "đáp ứng yêu cầu",
            "thực hiện nhiệm vụ",
            "áp dụng kỹ năng",
            "đảm nhận công việc",
        ],
    },

    "Communication": {
        "keywords": [
            "communication",
            "giao tiếp",
            "trao đổi",
            "trình bày",
            "diễn đạt",
            "lắng nghe",
            "phản hồi",
            "thuyết phục",
            "thảo luận",
            "phối hợp",
            "truyền đạt",
        ],
        "actions": [
            "chủ động trao đổi",
            "làm rõ yêu cầu",
            "trình bày phương án",
            "lắng nghe ý kiến",
            "phản hồi kịp thời",
            "thống nhất phương án",
        ],
    },

    "Cultural Fit": {
        "keywords": [
            "làm việc nhóm",
            "phối hợp",
            "hợp tác",
            "tôn trọng",
            "trách nhiệm",
            "thích nghi",
            "đồng nghiệp",
            "chia sẻ",
            "hỗ trợ",
        ],
        "actions": [
            "hỗ trợ thành viên",
            "phối hợp với nhóm",
            "tiếp nhận phản hồi",
            "chia sẻ công việc",
            "giải quyết xung đột",
        ],
    },
}

# ============================================================
# 2. ROLE DATA
# ============================================================

ROLES = {
    "Sales Executive": {
        "industry": "Kinh doanh",
        "levels": ["Junior", "Middle", "Senior"],
        "hard": [
            "Sales",
            "CRM",
            "Negotiation",
            "Product Knowledge",
        ],
        "soft": [
            "Communication",
            "Persuasion",
            "Customer Orientation",
            "Problem Solving",
        ],
        "questions": [
            "Hãy giới thiệu một sản phẩm bạn từng bán và cách bạn xác định nhu cầu khách hàng.",
            "Khách hàng nói sản phẩm của công ty có giá quá cao. Bạn sẽ xử lý như thế nào?",
            "Hãy kể về một thương vụ khó và cách bạn thuyết phục khách hàng đi đến quyết định.",
            "Nếu tháng này doanh số thấp hơn KPI, bạn sẽ phân tích và hành động như thế nào?",
        ],
    },

    "Software Developer": {
        "industry": "Công nghệ thông tin",
        "levels": [
            "Intern",
            "Junior",
            "Middle",
            "Senior",
        ],
        "hard": [
            "Programming",
            "Database",
            "API",
            "Git",
            "Software Design",
        ],
        "soft": [
            "Problem Solving",
            "Communication",
            "Learning Ability",
        ],
        "questions": [
            "Hãy mô tả một dự án phần mềm bạn từng tham gia và vai trò của bạn.",
            "Hãy kể về một lỗi khó bạn từng gặp và cách bạn tìm nguyên nhân, khắc phục.",
            "Nếu API đang phản hồi chậm, bạn sẽ kiểm tra và tối ưu theo những bước nào?",
            "Khi phải học một công nghệ mới trong thời gian ngắn, bạn sẽ tiếp cận ra sao?",
        ],
    },

    "Data Analyst": {
        "industry": "Data",
        "levels": [
            "Junior",
            "Middle",
            "Senior",
        ],
        "hard": [
            "SQL",
            "Excel",
            "Data Visualization",
            "Statistics",
            "Python",
        ],
        "soft": [
            "Analytical Thinking",
            "Communication",
            "Problem Solving",
        ],
        "questions": [
            "Hãy mô tả một bài toán dữ liệu bạn từng giải quyết.",
            "Nếu báo cáo cho thấy doanh số giảm mạnh, bạn sẽ phân tích nguyên nhân như thế nào?",
            "Bạn kiểm tra chất lượng dữ liệu trước khi phân tích bằng những bước nào?",
            "Bạn sẽ trình bày một insight phức tạp cho người không chuyên dữ liệu ra sao?",
        ],
    },

    "Digital Marketing Executive": {
        "industry": "Marketing",
        "levels": [
            "Junior",
            "Middle",
            "Senior",
        ],
        "hard": [
            "Content Marketing",
            "Meta Ads",
            "TikTok",
            "SEO",
            "Campaign Analytics",
        ],
        "soft": [
            "Creativity",
            "Communication",
            "Analytical Thinking",
        ],
        "questions": [
            "Hãy xây dựng ý tưởng cho một chiến dịch ra mắt sản phẩm mới.",
            "Một campaign có nhiều lượt tiếp cận nhưng ít chuyển đổi. Bạn sẽ xử lý thế nào?",
            "Bạn đánh giá hiệu quả một chiến dịch digital marketing dựa trên những chỉ số nào?",
            "Hãy kể về một ý tưởng nội dung bạn từng triển khai và kết quả đạt được.",
        ],
    },

    "HR Executive": {
        "industry": "Nhân sự",
        "levels": [
            "Junior",
            "Middle",
            "Senior",
        ],
        "hard": [
            "Recruitment",
            "HR Operations",
            "Labor Law",
            "Interviewing",
        ],
        "soft": [
            "Communication",
            "Empathy",
            "Conflict Resolution",
            "Problem Solving",
        ],
        "questions": [
            "Bạn sẽ đánh giá một ứng viên phù hợp với vị trí tuyển dụng dựa trên những yếu tố nào?",
            "Nếu nhân viên và quản lý có mâu thuẫn kéo dài, bạn sẽ xử lý ra sao?",
            "Hãy mô tả cách bạn tổ chức một quy trình tuyển dụng từ lúc nhận JD đến onboarding.",
            "Bạn sẽ làm gì khi ứng viên rất phù hợp nhưng kỳ vọng lương vượt ngân sách?",
        ],
    },

    "Customer Service": {
        "industry": "Dịch vụ khách hàng",
        "levels": [
            "Junior",
            "Middle",
            "Senior",
        ],
        "hard": [
            "Customer Service",
            "CRM",
            "Complaint Handling",
        ],
        "soft": [
            "Communication",
            "Empathy",
            "Problem Solving",
            "Customer Orientation",
        ],
        "questions": [
            "Một khách hàng tức giận vì đơn hàng giao trễ. Bạn sẽ xử lý cuộc trao đổi như thế nào?",
            "Hãy kể về một trường hợp bạn biến một khách hàng không hài lòng thành khách hàng tiếp tục sử dụng dịch vụ.",
            "Nếu chưa thể giải quyết ngay yêu cầu của khách hàng, bạn sẽ giao tiếp như thế nào?",
            "Bạn quản lý lịch sử và thông tin khách hàng bằng cách nào?",
        ],
    },

    "UI/UX Designer": {
        "industry": "Thiết kế",
        "levels": [
            "Junior",
            "Middle",
            "Senior",
        ],
        "hard": [
            "Figma",
            "UI Design",
            "UX Research",
            "Prototyping",
            "Design System",
        ],
        "soft": [
            "Creativity",
            "Communication",
            "User Empathy",
            "Problem Solving",
        ],
        "questions": [
            "Hãy mô tả quy trình bạn thường dùng để giải quyết một bài toán UX.",
            "Nếu người dùng không hoàn thành được một bước quan trọng trên sản phẩm, bạn sẽ tìm nguyên nhân thế nào?",
            "Bạn cân bằng giữa yêu cầu kinh doanh và trải nghiệm người dùng ra sao?",
            "Hãy giới thiệu một sản phẩm hoặc case design mà bạn tự hào nhất.",
        ],
    },

    "Accountant": {
        "industry": "Kế toán",
        "levels": [
            "Junior",
            "Middle",
            "Senior",
        ],
        "hard": [
            "Accounting",
            "Excel",
            "Financial Reporting",
            "Tax",
            "Accounts Receivable",
            "Accounts Payable",
        ],
        "soft": [
            "Analytical Thinking",
            "Attention to Detail",
            "Communication",
            "Problem Solving",
        ],
        "questions": [
            "Hãy giới thiệu kinh nghiệm kế toán phù hợp nhất của bạn với vị trí này và nêu rõ kết quả bạn đã đạt được.",
            "Bạn đã từng lập hoặc kiểm tra báo cáo kế toán nào? Hãy mô tả vai trò và kết quả cụ thể.",
            "Nếu số liệu giữa sổ chi tiết và sổ tổng hợp không khớp, bạn sẽ kiểm tra và xử lý như thế nào?",
            "Bạn thực hiện đối chiếu công nợ phải thu hoặc phải trả như thế nào để hạn chế sai sót?",
        ],
    },

    "Financial Analyst": {
        "industry": "Tài chính",
        "levels": [
            "Junior",
            "Middle",
            "Senior",
        ],
        "hard": [
            "Financial Analysis",
            "Excel",
            "Financial Modeling",
            "Accounting",
        ],
        "soft": [
            "Analytical Thinking",
            "Communication",
            "Attention to Detail",
        ],
        "questions": [
            "Bạn sẽ phân tích nguyên nhân lợi nhuận của doanh nghiệp giảm như thế nào?",
            "Hãy mô tả một mô hình tài chính hoặc báo cáo bạn từng xây dựng.",
            "Nếu dữ liệu giữa hai báo cáo không khớp, bạn sẽ kiểm tra từ đâu?",
            "Bạn trình bày một kết luận tài chính cho lãnh đạo không chuyên tài chính như thế nào?",
        ],
    },
}


# Tất cả role đều dùng chung 5 tiêu chí
for role in ROLES.values():
    role["criteria"] = list(EVALUATION_CRITERIA)


# ============================================================
# 3. TEXT SIGNALS
# ============================================================

FILLERS = [
    "ờ",
    "ừ",
    "à",
    "uh",
    "um",
    "ừm",
    "kiểu như",
    "nói chung là",
    "thì là",
    "à thì",
    "ờ thì",
]


SIGNALS = {
    "Knowledge / Technical Knowledge": [
        "kiến thức",
        "chuyên môn",
        "kỹ thuật",
        "technical",
        "programming",
        "python",
        "java",
        "javascript",
        "sql",
        "postgresql",
        "mysql",
        "api",
        "database",
        "git",
        "docker",
        "spring",
        "framework",
        "công nghệ",
        "thuật toán",
        "kiến trúc",
        "software design",
        "thiết kế phần mềm",
    ],

    "Problem Solving": [
        "phân tích",
        "nguyên nhân",
        "vấn đề",
        "giải pháp",
        "xử lý",
        "khắc phục",
        "kiểm tra",
        "đánh giá",
        "debug",
        "tìm lỗi",
        "thử nghiệm",
        "phương án",
        "ưu tiên",
        "rủi ro",
    ],

    "JD Fit": [
        "jd",
        "yêu cầu",
        "vị trí",
        "công việc",
        "nhiệm vụ",
        "kinh nghiệm",
        "kỹ năng",
        "dự án",
        "vai trò",
        "trách nhiệm",
        "phù hợp",
    ],

    "Communication": [
        "giao tiếp",
        "trao đổi",
        "trình bày",
        "giải thích",
        "lắng nghe",
        "thuyết phục",
        "phản hồi",
        "diễn đạt",
        "rõ ràng",
        "thảo luận",
        "phối hợp",
    ],

    "Cultural Fit": [
        "làm việc nhóm",
        "đồng đội",
        "teamwork",
        "phối hợp",
        "tôn trọng",
        "trách nhiệm",
        "chủ động",
        "thích nghi",
        "học hỏi",
        "phản hồi",
        "giá trị",
        "văn hóa",
        "đạo đức",
        "cam kết",
        "kỷ luật",
        "hỗ trợ",
        "chia sẻ",
    ],
}

# ============================================================
# 4. DATABASE
# ============================================================

@contextmanager
def db():
    """
    Tạo PostgreSQL connection và tự động:
    - commit nếu thành công
    - rollback nếu lỗi
    - close connection
    """
    conn = get_connection()

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# 5. LOGIN REQUIRED
# ============================================================

def login_required(role=None):
    def deco(fn):

        @wraps(fn)
        def wrapped(*args, **kwargs):

            if not session.get("user_id"):
                return redirect(
                    url_for("main.login")
                )

            if role and session.get("role") != role:
                return redirect(
                    url_for("main.dashboard")
                )

            return fn(*args, **kwargs)

        return wrapped

    return deco


# ============================================================
# 6. HELPER JSON
# ============================================================

def json_load(value, default=None):
    if default is None:
        default = {}

    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    try:
        return json.loads(value)
    except Exception:
        return default


# ============================================================
# 7. CLEAN TEXT
# ============================================================

def clean_text(text):
    text = re.sub(
        r"\s+",
        " ",
        (text or "").strip()
    )

    for filler in sorted(
        FILLERS,
        key=len,
        reverse=True
    ):
        text = re.sub(
            rf"(?i)(?<!\w){re.escape(filler)}(?!\w)",
            " ",
            text,
        )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


# ============================================================
# 8. STANDARDIZE SKILLS
# ============================================================

def standardize_skills(text):
    t = (text or "").lower()

    aliases = {
        "customer care": "Customer Service",
        "chăm sóc khách hàng": "Customer Service",
        "cskh": "Customer Service",

        "giao tiếp": "Communication",
        "communication": "Communication",

        "đàm phán": "Negotiation",
        "negotiation": "Negotiation",

        "thuyết phục": "Persuasion",
        "persuasion": "Persuasion",

        "giải quyết vấn đề": "Problem Solving",
        "problem solving": "Problem Solving",

        "phân tích dữ liệu": "Analytical Thinking",
        "analytical thinking": "Analytical Thinking",

        "quản trị quan hệ khách hàng": "CRM",
        "crm": "CRM",

        "spring boot": "Spring Boot",
        "spring": "Spring",

        "postgresql": "PostgreSQL",
        "mysql": "MySQL",

        "kế toán": "Accounting",
        "accounting": "Accounting",
        "hạch toán": "Accounting",

        "báo cáo tài chính": "Financial Reporting",
        "financial reporting": "Financial Reporting",

        "kê khai thuế": "Tax",
        "thuế": "Tax",

        "misa": "MISA",

        "python": "Python",
        "java": "Java",
        "javascript": "JavaScript",

        "docker": "Docker",
        "kubernetes": "Kubernetes",

        "git": "Git",
        "github": "GitHub",

        "sql": "SQL",
        "excel": "Excel",

        "figma": "Figma",
        "seo": "SEO",

        "meta ads": "Meta Ads",
        "tiktok": "TikTok",
    }

    found = []

    for alias, skill in aliases.items():
        if alias in t and skill not in found:
            found.append(skill)

    for role in ROLES.values():

        for skill in (
            role.get("hard", [])
            + role.get("soft", [])
        ):
            if skill.lower() in t and skill not in found:
                found.append(skill)

    return found


# ============================================================
# 9. EXTRACT DOCUMENT
# ============================================================

def extract_document(path):
    ext = Path(path).suffix.lower()

    try:

        if ext == ".pdf":

            from pypdf import PdfReader

            return "\n".join(
                page.extract_text() or ""
                for page in PdfReader(path).pages
            ).strip()

        if ext == ".docx":

            from docx import Document

            return "\n".join(
                p.text
                for p in Document(path).paragraphs
            ).strip()

    except Exception as exc:
        current_app.logger.exception(
            "Không thể đọc document: %s",
            exc
        )

    return ""


# ============================================================
# 10. INFER JOB
# ============================================================

def infer_job(jd):

    raw = jd or ""
    text = raw.lower()

    head = " ".join(
        re.split(r"[\n\r]+", raw)[:8]
    ).lower()

    title_rules = [

        (
            "Accountant",
            [
                "kế toán",
                "accountant",
                "accounting staff",
                "nhân viên kế toán",
                "chuyên viên kế toán",
                "kế toán viên",
            ],
        ),

        (
            "Sales Executive",
            [
                "sales executive",
                "sales representative",
                "nhân viên kinh doanh",
                "chuyên viên kinh doanh",
                "sales",
                "kinh doanh",
            ],
        ),

        (
            "Software Developer",
            [
                "software developer",
                "backend developer",
                "frontend developer",
                "full stack developer",
                "lập trình viên",
                "software engineer",
                "developer",
            ],
        ),

        (
            "Data Analyst",
            [
                "data analyst",
                "chuyên viên phân tích dữ liệu",
                "phân tích dữ liệu",
            ],
        ),

        (
            "Digital Marketing Executive",
            [
                "digital marketing",
                "marketing executive",
                "chuyên viên marketing",
                "nhân viên marketing",
            ],
        ),

        (
            "HR Executive",
            [
                "hr executive",
                "human resources",
                "nhân sự",
                "chuyên viên tuyển dụng",
                "recruitment specialist",
            ],
        ),

        (
            "Customer Service",
            [
                "customer service",
                "chăm sóc khách hàng",
                "customer care",
                "nhân viên chăm sóc khách hàng",
            ],
        ),

        (
            "UI/UX Designer",
            [
                "ui/ux designer",
                "ux designer",
                "ui designer",
                "product designer",
                "figma designer",
            ],
        ),

        (
            "Financial Analyst",
            [
                "financial analyst",
                "financial analysis",
                "chuyên viên phân tích tài chính",
                "phân tích tài chính",
            ],
        ),
    ]

    for name, phrases in title_rules:

        if any(
            phrase in head
            for phrase in phrases
        ):
            return name

    signal_rules = {

        "Accountant": [
            "hạch toán",
            "sổ cái",
            "sổ chi tiết",
            "đối chiếu công nợ",
            "công nợ phải thu",
            "công nợ phải trả",
            "báo cáo tài chính",
            "kê khai thuế",
            "thuế gtgt",
            "misa",
        ],

        "Financial Analyst": [
            "financial analyst",
            "financial modeling",
            "financial model",
            "forecast tài chính",
            "financial planning",
            "budgeting",
            "valuation",
            "dự báo tài chính",
            "phân tích tài chính",
        ],

        "Sales Executive": [
            "pipeline",
            "lead",
            "chốt sales",
            "doanh số",
            "kpi sales",
            "prospecting",
            "sales target",
            "khách hàng tiềm năng",
        ],

        "Software Developer": [
            "api",
            "backend",
            "frontend",
            "spring boot",
            "microservices",
            "git",
            "database",
            "lập trình",
            "code",
        ],

        "Data Analyst": [
            "sql",
            "dashboard",
            "power bi",
            "tableau",
            "data visualization",
            "phân tích dữ liệu",
            "insight",
        ],

        "Digital Marketing Executive": [
            "meta ads",
            "google ads",
            "tiktok ads",
            "seo",
            "campaign",
            "digital marketing",
            "content marketing",
        ],

        "HR Executive": [
            "tuyển dụng",
            "recruitment",
            "onboarding",
            "c&b",
            "chấm công",
            "hồ sơ nhân sự",
            "labor law",
        ],

        "Customer Service": [
            "ticket",
            "complaint",
            "khiếu nại",
            "customer service",
            "chăm sóc khách hàng",
            "csat",
            "sla",
        ],

        "UI/UX Designer": [
            "figma",
            "wireframe",
            "prototype",
            "ux research",
            "design system",
            "user flow",
            "ui/ux",
        ],
    }

    scores = {}

    for name, signals in signal_rules.items():

        scores[name] = sum(
            3 if len(sig.split()) > 1 else 1
            for sig in signals
            if sig in text
        )

    if not scores:
        return "Custom Position"

    best = max(
        scores,
        key=scores.get
    )

    if scores[best] >= 3:

        if (
            scores.get("Accountant", 0)
            >= scores.get("Financial Analyst", 0)
            and scores["Accountant"] >= 3
        ):
            return "Accountant"

        return best

    return "Custom Position"


# ============================================================
# 11. BUILD JOB PROFILE
# ============================================================

def build_custom_profile(
    jd,
    position=None,
    level="Junior",
):

    inferred = (
        position
        or infer_job(jd)
    )

    base = ROLES.get(inferred)

    if base:

        profile = {
            **base,
            "position": inferred,
            "level": level,
            "criteria": list(
                EVALUATION_CRITERIA
            ),
        }

        profile["display_position"] = (
            "Kế toán"
            if inferred == "Accountant"
            else inferred
        )

        return profile

    skills = standardize_skills(jd)

    if not skills:
        skills = [
            "Communication",
            "Problem Solving",
            "JD Fit",
        ]

    soft_candidates = {
        "Communication",
        "Problem Solving",
        "Analytical Thinking",
        "Creativity",
        "Customer Orientation",
        "Learning Ability",
    }

    soft = [
        s
        for s in skills
        if s in soft_candidates
    ]

    hard = [
        s
        for s in skills
        if s not in soft
    ]

    return {
        "position": inferred,
        "display_position": inferred,
        "industry": "Tùy chỉnh",
        "levels": [level],
        "hard": hard,
        "soft": soft,
        "criteria": list(
            EVALUATION_CRITERIA
        ),
        "questions": [],
    }


# ============================================================
# 12. SENTENCES
# ============================================================

def _sentences(text):

    return [
        x.strip(" .;,-")
        for x in re.split(
            r"[\n.!?;]+",
            text or ""
        )
        if x.strip()
    ]


# ============================================================
# 13. RULE-BASED QUESTIONS
# ============================================================

def build_interview_questions(
    profile,
    cv_text="",
    jd_text="",
):

    cv_skills = standardize_skills(
        cv_text
    )

    jd_skills = standardize_skills(
        jd_text
    )

    hard = profile.get(
        "hard",
        []
    )

    soft = profile.get(
        "soft",
        []
    )

    cv_lower = (
        cv_text or ""
    ).lower()

    matched = [
        s
        for s in jd_skills
        if s in cv_skills
    ]

    gaps = [
        s
        for s in jd_skills
        if s not in cv_skills
    ]

    if not gaps:

        gaps = [
            s
            for s in hard
            if s.lower()
            not in cv_lower
        ][:3]

    evidence = cv_skills[:3]

    questions = []

    position = profile.get(
        "display_position",
        profile.get(
            "position",
            "vị trí này"
        ),
    )

    # 01
    if evidence:

        questions.append(
            f"Trong CV của bạn có "
            f"{', '.join(evidence)}. "
            f"Hãy giới thiệu kinh nghiệm phù hợp nhất "
            f"của bạn với vị trí {position} "
            f"và vai trò cụ thể của bạn."
        )

    else:

        questions.append(
            f"Hãy giới thiệu kinh nghiệm phù hợp nhất "
            f"của bạn với vị trí {position} "
            f"và nêu rõ kết quả bạn đã đạt được."
        )

    # 02
    if evidence:

        questions.append(
            f"Hãy chọn một dự án hoặc công việc "
            f"trong CV có sử dụng {evidence[0]}. "
            f"Bạn đã làm gì, gặp khó khăn gì "
            f"và kết quả cuối cùng ra sao?"
        )

    else:

        questions.append(
            "Hãy chọn một dự án hoặc công việc nổi bật "
            "trong CV, mô tả vai trò của bạn "
            "và kết quả cụ thể."
        )

    # 03 - 05
    for skill in (
        gaps[:2]
        + matched[:1]
    ):

        if skill in gaps:

            questions.append(
                f"JD yêu cầu {skill}. "
                f"Hiện CV chưa thể hiện rõ kinh nghiệm này. "
                f"Nếu được giao công việc liên quan đến "
                f"{skill}, bạn sẽ tiếp cận "
                f"và chứng minh năng lực như thế nào?"
            )

        else:

            questions.append(
                f"Bạn đã có {skill} trong CV. "
                f"Hãy mô tả một tình huống thực tế "
                f"bạn sử dụng kỹ năng này "
                f"và cách bạn đo lường kết quả."
            )

    # Scenario
    focus = (
        gaps
        + hard
        + [
            c
            for c, _ in profile.get(
                "criteria",
                []
            )
        ]
    )[:2]

    for skill in focus:

        questions.append(
            f"Giả sử bạn gặp một vấn đề khó "
            f"liên quan đến {skill} trong công việc này, "
            f"bạn sẽ phân tích nguyên nhân, "
            f"đưa ra phương án và kiểm tra kết quả "
            f"như thế nào?"
        )

    questions.append(
        f"Hãy kể một lần bạn gặp vấn đề "
        f"trong công việc liên quan đến vị trí "
        f"{position}. "
        f"Bạn đã xử lý thế nào "
        f"và rút ra bài học gì?"
    )

    questions.append(
        "Nếu nhận được phản hồi rằng cách làm hiện tại "
        "chưa đáp ứng yêu cầu của JD, "
        "bạn sẽ thay đổi kế hoạch làm việc như thế nào?"
    )

    questions.append(
        f"Nếu được nhận vào vị trí {position}, "
        "bạn sẽ ưu tiên cải thiện kỹ năng nào "
        "trong 30 ngày đầu tiên và vì sao?"
    )

    # Deduplicate
    result = []
    seen = set()

    for q in questions:

        q = q.strip()

        if (
            q
            and q.lower() not in seen
        ):

            seen.add(q.lower())
            result.append(q)

    fallbacks = [

        f"Hãy mô tả cách bạn sẽ hoàn thành "
        f"một nhiệm vụ quan trọng của vị trí "
        f"{profile.get('position', position)} "
        "từ lúc nhận yêu cầu đến khi bàn giao.",

        "Hãy nêu một kết quả cụ thể "
        "bạn tự hào nhất và bằng chứng cho kết quả đó.",

    ]

    for q in fallbacks:

        if len(result) >= 10:
            break

        result.append(q)

    return result[:10]


# ============================================================
# 14. QUESTION FOCUS
# ============================================================
def question_focus(question, profile):
    """
    Xác định các tiêu chí đánh giá phù hợp với câu hỏi.

    Trả về danh sách tiêu chí trong EVALUATION_CRITERIA.
    Việc xác định dựa trên từ khóa và cụm từ liên quan.
    """

    question_text = str(question or "").lower().strip()
    profile = profile or {}

    criteria = profile.get("criteria", []) or []

    criterion_names = [
        str(item[0])
        for item in criteria
        if isinstance(item, (list, tuple)) and item
    ]

    # Nếu profile không cung cấp tiêu chí,
    # sử dụng danh sách tiêu chí của hệ thống.
    if not criterion_names:
        criterion_names = [
            criterion
            for criterion, _ in EVALUATION_CRITERIA
        ]

    # Các cụm từ gợi ý cho từng nhóm năng lực.
    focus_keywords = {
        "Communication": [
            "communication",
            "giao tiếp",
            "trao đổi",
            "trình bày",
            "diễn đạt",
            "lắng nghe",
            "thuyết phục",
            "phản hồi",
            "thảo luận",
            "phối hợp",
            "truyền đạt",
        ],

        "Problem Solving": [
            "problem solving",
            "giải quyết vấn đề",
            "xử lý vấn đề",
            "khắc phục lỗi",
            "phân tích nguyên nhân",
            "tìm nguyên nhân",
            "đề xuất giải pháp",
            "giải pháp",
            "debug",
            "xử lý sự cố",
        ],

        "Knowledge / Technical Knowledge": [
            "technical knowledge",
            "kiến thức chuyên môn",
            "kiến thức kỹ thuật",
            "công nghệ",
            "thuật toán",
            "lập trình",
            "cơ sở dữ liệu",
            "postgresql",
            "sql",
            "python",
            "java",
            "framework",
        ],

        "JD Fit": [
            "jd fit",
            "yêu cầu công việc",
            "mô tả công việc",
            "vị trí ứng tuyển",
            "kỹ năng yêu cầu",
            "phù hợp với jd",
            "kinh nghiệm liên quan",
            "yêu cầu của vị trí",
        ],

        "Cultural Fit": [
            "cultural fit",
            "phù hợp văn hóa",
            "văn hóa doanh nghiệp",
            "làm việc nhóm",
            "xung đột trong nhóm",
            "thích nghi",
            "giá trị cá nhân",
            "môi trường làm việc",
            "hợp tác với đồng nghiệp",
        ],
    }

    # Chuẩn hóa tên tiêu chí để tránh sai khác
    # do viết hoa hoặc khoảng trắng.
    def normalize(value):
        return re.sub(
            r"\s+",
            " ",
            str(value or "").lower().strip(),
        )

    normalized_question = normalize(question_text)

    matched = []

    for criterion in criterion_names:
        normalized_criterion = normalize(criterion)

        keywords = focus_keywords.get(
            criterion,
            [normalized_criterion],
        )

        # Tên tiêu chí được dùng làm từ khóa bổ sung.
        keywords = list(keywords) + [normalized_criterion]

        if any(
            normalize(keyword) in normalized_question
            for keyword in keywords
            if normalize(keyword)
        ):
            matched.append(criterion)

    # Chỉ bổ sung tiêu chí khi có bằng chứng từ câu hỏi.
    # Không tự động thêm ba tiêu chí mặc định khi không khớp.
    return matched[:3]

# ============================================================
# 15. TOKENIZER
# ============================================================

def _tokens(text):

    stop = {
        "hãy",
        "bạn",
        "có",
        "thể",
        "mô",
        "tả",
        "giới",
        "thiệu",
        "kinh",
        "nghiệm",
        "phù",
        "hợp",
        "nhất",
        "với",
        "vị",
        "trí",
        "này",
        "nêu",
        "rõ",
        "kết",
        "quả",
        "đã",
        "được",
        "của",
        "một",
        "trong",
        "và",
        "theo",
        "như",
        "nào",
        "nếu",
        "sẽ",
        "từng",
        "làm",
        "việc",
        "cho",
        "đến",
        "khi",
        "ra",
        "sao",
        "the",
    }

    vals = re.findall(
        r"[a-zA-ZÀ-ỹ0-9+#./-]{2,}",
        (text or "").lower(),
    )

    return {
        v
        for v in vals
        if v not in stop
    }


# ============================================================
# 16. RELEVANCE SCORE
# ============================================================
def _relevance_score(answer, question, profile):
    """
    Ước tính độ liên quan của câu trả lời với câu hỏi.

    Lưu ý:
        Đây là heuristic dựa trên từ khóa, không phải
        đánh giá ngữ nghĩa bằng mô hình AI.

    Trả về:
        relevance: Điểm 0-100.
        q_hits: Từ khóa câu hỏi khớp với câu trả lời.
        target_hits: Từ khóa mục tiêu khớp với câu trả lời.
    """
    answer = str(answer or "").strip()
    question = str(question or "").strip()
    profile = profile or {}

    if not answer or not question:
        return 0.0, [], []

    # --------------------------------------------------
    # 1. Chuẩn hóa token
    # --------------------------------------------------
    a = {
        str(token).lower()
        for token in _tokens(answer)
    }

    q = {
        str(token).lower()
        for token in _tokens(question)
    }

    answer_skills = {
        str(skill).strip().lower()
        for skill in standardize_skills(answer)
        if str(skill).strip()
    }

    question_skills = {
        str(skill).strip().lower()
        for skill in standardize_skills(question)
        if str(skill).strip()
    }

    # Tách kỹ năng thành token để tránh lỗi so sánh
    # cụm nhiều từ với từng token riêng lẻ.
    answer_skill_tokens = set()

    for skill in answer_skills:
        answer_skill_tokens.update(_tokens(skill))

    question_skill_tokens = set()

    for skill in question_skills:
        question_skill_tokens.update(_tokens(skill))

    # --------------------------------------------------
    # 2. Tập từ mục tiêu từ CV, JD và vị trí ứng tuyển
    # --------------------------------------------------
    hard_skills = profile.get("hard", []) or []
    soft_skills = profile.get("soft", []) or []

    position = str(profile.get("position", "") or "")
    jd_text = str(profile.get("jd_text", "") or "")
    cv_text = str(profile.get("cv_text", "") or "")

    target_parts = [
        position,
        jd_text,
        cv_text,
        " ".join(map(str, hard_skills)),
        " ".join(map(str, soft_skills)),
    ]

    criteria = profile.get("criteria", []) or []

    for item in criteria:
        if isinstance(item, (list, tuple)) and item:
            target_parts.append(str(item[0]))

    target_tokens = {
        str(token).lower()
        for token in _tokens(" ".join(target_parts))
    }

    # --------------------------------------------------
    # 3. Loại từ phổ biến ít có giá trị phân biệt
    # --------------------------------------------------
    stop_words = {
        "của", "và", "là", "có", "đã", "được",
        "cho", "trong", "với", "một", "những",
        "bạn", "em", "tôi", "hãy", "nào", "gì",
        "thì", "khi", "để", "về", "ra", "theo",
        "các", "như", "này", "đó", "mình",
        "the", "and", "for", "with", "your",
        "what", "how", "are", "you",
    }

    meaningful_q = q - stop_words
    meaningful_a = a - stop_words

    # --------------------------------------------------
    # 4. Độ khớp từ khóa của câu hỏi
    # --------------------------------------------------
    question_hits = meaningful_a & meaningful_q

    if meaningful_q:
        question_ratio = min(
            1.0,
            len(question_hits) / len(meaningful_q)
        )
    else:
        question_ratio = 0.0

    # --------------------------------------------------
    # 5. Độ khớp kỹ năng
    # --------------------------------------------------
    skill_hits = answer_skills & question_skills

    # Tính cả token kỹ năng để giảm lỗi khi so sánh
    # kỹ năng nhiều từ.
    skill_token_hits = (
        answer_skill_tokens & question_skill_tokens
    )

    if question_skills:
        skill_ratio = (
            0.7 * len(skill_hits)
            / max(1, len(question_skills))
            +
            0.3 * len(skill_token_hits)
            / max(1, len(question_skill_tokens))
        )

        skill_ratio = min(1.0, skill_ratio)
    else:
        skill_ratio = 0.0

    # --------------------------------------------------
    # 6. Độ khớp với hồ sơ ứng viên và JD
    # --------------------------------------------------
    target_hits = meaningful_a & target_tokens

    # Không sử dụng toàn bộ CV/JD làm yếu tố quyết định,
    # vì các tài liệu này có thể chứa nhiều từ không liên quan.
    target_ratio = min(
        1.0,
        len(target_hits) / 6.0
    )

    # --------------------------------------------------
    # 7. Kết hợp các thành phần
    # --------------------------------------------------
    if question_skills:
        relevance_ratio = (
            0.65 * question_ratio
            + 0.25 * skill_ratio
            + 0.10 * target_ratio
        )
    else:
        relevance_ratio = (
            0.85 * question_ratio
            + 0.15 * target_ratio
        )

    relevance = 100 * relevance_ratio

    # --------------------------------------------------
    # 8. Giới hạn câu trả lời quá ngắn
    # --------------------------------------------------
    answer_word_count = len(
        re.findall(r"\w+", answer, re.UNICODE)
    )

    if answer_word_count < 3:
        relevance = min(relevance, 5)

    elif answer_word_count < 6:
        relevance = min(relevance, 20)

    return (
        round(max(0.0, min(100.0, relevance)), 1),
        sorted(question_hits),
        sorted(target_hits)[:12],
    )

# ============================================================
# 17. ANALYZE ANSWER
# ============================================================
def analyze_answer(answer, question, profile):
    # ========================================================
    # 1. CHUẨN HÓA ĐẦU VÀO
    # ========================================================
    text = clean_text(answer or "")
    lower = text.lower().strip()
    question = (question or "").strip()
    profile = profile or {}

    focus = question_focus(question, profile)

    word_count = len(
        re.findall(r"\w+", text, re.UNICODE)
    )

    relevance, q_hits, target_hits = _relevance_score(
        text,
        question,
        profile,
    )

    answer_skills = {
        str(skill).strip().lower()
        for skill in standardize_skills(text)
        if str(skill).strip()
    }

    active = [
        criterion
        for criterion, _ in EVALUATION_CRITERIA
    ]

    # ========================================================
    # 2. XỬ LÝ CÂU TRẢ LỜI TRỐNG HOẶC QUÁ NGẮN
    # ========================================================
    if not lower or word_count < 3:
        criteria = {
            criterion: 0
            for criterion in active
        }

        return {
            "overall": 0,
            "criteria": criteria,
            "evidence": {},
            "focus": focus,
            "active_criteria": active,
            "relevance": 0,
            "question_hits": [],
            "target_hits": [],
            "strengths": [],
            "improvements": active[:3],
            "explanation": (
                "Câu trả lời quá ngắn để đánh giá năng lực. "
                "Hãy trả lời trực tiếp câu hỏi và giải thích "
                "cách bạn thực hiện."
            ),
            "action": (
                "Nêu ý chính, mô tả hành động cụ thể "
                "và đưa ra ví dụ phù hợp với câu hỏi."
            ),
            "word_count": word_count,
            "cleaned": text,
        }

    # ========================================================
    # 3. NHẬN DIỆN CẤU TRÚC CÂU TRẢ LỜI
    # ========================================================
    has_steps = any(
        phrase in lower
        for phrase in (
            "đầu tiên",
            "sau đó",
            "tiếp theo",
            "cuối cùng",
            "bước 1",
            "bước 2",
        )
    )

    has_action = any(
        phrase in lower
        for phrase in (
            "tôi đã",
            "em đã",
            "mình đã",
            "tôi thực hiện",
            "em thực hiện",
            "tôi sử dụng",
            "em sử dụng",
            "tôi kiểm tra",
            "em kiểm tra",
            "tôi phân tích",
            "em phân tích",
            "tôi xử lý",
            "em xử lý",
            "chủ động trao đổi",
            "phân tích nguyên nhân",
            "thống nhất",
            "phối hợp xử lý",
        )
    )

    has_example = any(
        phrase in lower
        for phrase in (
            "ví dụ",
            "trong dự án",
            "trong công việc",
            "thực tế",
            "trường hợp",
            "khi gặp",
        )
    )

    has_result = any(
        phrase in lower
        for phrase in (
            "kết quả",
            "đạt được",
            "hoàn thành",
            "cải thiện",
            "giảm",
            "tăng",
            "khắc phục thành công",
            "giải quyết được",
        )
    )

    evidence_signals = sum((
        has_steps,
        has_action,
        has_example,
        has_result,
    ))

    # ========================================================
    # 4. TÍNH ĐIỂM TỪNG TIÊU CHÍ
    # ========================================================
    scores = {}
    evidence = {}

    for criterion, weight in EVALUATION_CRITERIA:
        signals = SIGNALS.get(criterion, [])

        criterion_config = CRITERION_EVIDENCE.get(
            criterion,
            {
                "keywords": [],
                "actions": [],
            }
        )

        # ----------------------------------------------------
        # 4.1. Lấy từ khóa và hành động của tiêu chí
        # ----------------------------------------------------
        keywords = list(dict.fromkeys(
            signals
            + criterion_config.get("keywords", [])
        ))

        actions = criterion_config.get("actions", [])

        keyword_hits = [
            term
            for term in keywords
            if isinstance(term, str)
            and term.strip()
            and term.lower() in lower
        ]

        action_hits = [
            action
            for action in actions
            if isinstance(action, str)
            and action.strip()
            and action.lower() in lower
        ]

        # ----------------------------------------------------
        # 4.2. Lấy kỹ năng có trong câu trả lời
        # ----------------------------------------------------
        profile_skills = (
            profile.get("hard", [])
            + profile.get("soft", [])
        )

        if not isinstance(profile_skills, list):
            profile_skills = []

        skill_hits = [
            skill.strip()
            for skill in profile_skills
            if isinstance(skill, str)
            and skill.strip()
            and skill.strip().lower() in lower
        ]

        # Chỉ tính kỹ năng có liên quan đến tiêu chí.
        # Tránh cộng toàn bộ kỹ năng CV vào mọi tiêu chí.
        criterion_text = " ".join(
            str(item)
            for item in keywords + actions
            if isinstance(item, str)
        ).lower()

        relevant_skill_hits = [
            skill
            for skill in skill_hits
            if skill.lower() in criterion_text
        ]

        # ----------------------------------------------------
        # 4.3. Xác định tín hiệu cấu trúc
        # ----------------------------------------------------
        # Dùng chung các tín hiệu về ví dụ, kết quả và
        # trình tự, nhưng không coi chúng là bằng chứng
        # chuyên môn riêng của từng tiêu chí.
        example_points = 15 if has_example else 0
        result_points = 15 if has_result else 0
        structure_points = 5 if has_steps else 0

        keyword_points = min(
            25,
            len(keyword_hits) * 5,
        )

        action_points = min(
            30,
            len(action_hits) * 15,
        )

        skill_points = min(
            10,
            len(relevant_skill_hits) * 5,
        )

        focus_points = 10 if criterion in focus else 0

        raw_score = (
            keyword_points
            + action_points
            + skill_points
            + example_points
            + result_points
            + structure_points
            + focus_points
        )

        score_value = min(100, raw_score)

        # ----------------------------------------------------
        # 4.4. Điều chỉnh theo độ liên quan
        # ----------------------------------------------------
        # Không áp dụng mức trần cho điểm từng tiêu chí
        # quá mạnh chỉ vì relevance hơi thấp.
        #
        # Tuy nhiên, câu trả lời rất ít liên quan vẫn
        # cần bị giới hạn để tránh điểm cao không hợp lý.
        if relevance < 15:
            score_value = min(score_value, 15)

        elif relevance < 25:
            score_value = min(score_value, 30)

        elif relevance < 35:
            score_value = min(score_value, 50)

        # Chỉ có từ khóa mà không có hành động, ví dụ
        # hoặc kết quả thì giới hạn điểm.
        if (
            keyword_hits
            and not action_hits
            and not has_example
            and not has_result
        ):
            score_value = min(score_value, 35)

        scores[criterion] = round(
            max(0, min(100, score_value)),
            1,
        )

        # ----------------------------------------------------
        # 4.5. Lưu Evidence theo từng tiêu chí
        # ----------------------------------------------------
        evidence[criterion] = {
            "keywords": keyword_hits[:8],
            "actions": action_hits[:6],
            "skills": relevant_skill_hits[:5],
            "has_example": has_example and bool(keyword_hits or action_hits),
            "has_result": has_result and bool(action_hits),
            "has_steps": has_steps and bool(action_hits),
        }   

    # ========================================================
    # 5. TÍNH ĐIỂM TỔNG CÓ TRỌNG SỐ
    # ========================================================
    weight_total = sum(
        weight
        for _, weight in EVALUATION_CRITERIA
    )

    if weight_total > 0:
        total = sum(
            scores.get(criterion, 0) * weight
            for criterion, weight in EVALUATION_CRITERIA
        ) / weight_total
    else:
        total = 0

    # Không áp dụng mức trần 45 điểm chỉ vì relevance < 50.
    # Điểm tổng phản ánh điểm các tiêu chí.
    overall = round(
        max(0, min(100, total)),
        1,
    )

    # ========================================================
    # 6. XÁC ĐỊNH ĐIỂM MẠNH VÀ ĐIỂM CẦN CẢI THIỆN
    # ========================================================
    strengths = [
        criterion
        for criterion, value in scores.items()
        if value >= 65
    ][:3]

    improvements = [
        criterion
        for criterion, value in sorted(
            scores.items(),
            key=lambda item: item[1],
        )
        if value < 60
    ][:3]

    # ========================================================
    # 7. TẠO PHẢN HỒI
    # ========================================================
    if relevance < 20:
        explanation = (
            f"Câu trả lời có mức liên quan thấp "
            f"({round(relevance)}/100) so với câu hỏi. "
            "Cần kiểm tra lại nội dung câu trả lời "
            "và bổ sung bằng chứng trực tiếp."
        )

        action = (
            "Trả lời trực tiếp câu hỏi, mô tả hành động "
            "của bản thân và nêu kết quả cụ thể."
        )

    elif evidence_signals == 0 and not answer_skills:
        explanation = (
            f"Mức liên quan của câu trả lời: "
            f"{round(relevance)}/100. "
            "Câu trả lời chưa thể hiện rõ hành động, "
            "ví dụ thực tế hoặc kết quả."
        )

        action = (
            "Bổ sung ví dụ thực tế, hành động cụ thể "
            "và kết quả đạt được."
        )

    else:
        explanation = (
            f"Mức liên quan của câu trả lời: "
            f"{round(relevance)}/100. "
            "Điểm được ước tính dựa trên từ khóa liên quan, "
            "hành động được mô tả, kỹ năng, ví dụ, "
            "cấu trúc và kết quả được đề cập."
        )

        if improvements:
            targets = ", ".join(improvements[:2])
        elif focus:
            targets = ", ".join(focus[:2])
        else:
            targets = (
                "kiến thức chuyên môn và kinh nghiệm thực tế"
            )

        action = (
            "Tiếp tục bổ sung bằng chứng cụ thể và cải thiện: "
            f"{targets}."
        )

    # ========================================================
    # 8. TRẢ KẾT QUẢ CHO FRONTEND
    # ========================================================
    return {
        "overall": overall,
        "criteria": scores,
        "evidence": evidence,
        "focus": focus,
        "active_criteria": active,
        "relevance": relevance,
        "question_hits": q_hits,
        "target_hits": target_hits,
        "strengths": strengths,
        "improvements": improvements,
        "explanation": explanation,
        "action": action,
        "word_count": word_count,
        "cleaned": text,
    }

# ============================================================
# 18. INDEX
# ============================================================

@bp.route("/")
def index():

    if session.get("user_id"):
        return redirect(
            url_for("main.dashboard")
        )

    return render_template(
        "landing.html"
    )


# ============================================================
# 19. SIGNUP
# ============================================================

@bp.route(
    "/signup",
    methods=["GET", "POST"],
)
def signup():

    if session.get("user_id"):

        return redirect(
            url_for("main.dashboard")
        )

    if request.method == "POST":

        username = (
            request.form
            .get(
                "username",
                "",
            )
            .strip()
        )

        password = request.form.get(
            "password",
            "",
        )

        confirm_password = (
            request.form
            .get(
                "confirm_password",
                "",
            )
        )

        if (
            len(username) < 3
            or len(password) < 4
        ):

            return render_template(
                "signup.html",
                error=(
                    "Tên đăng nhập cần ít nhất "
                    "3 ký tự và mật khẩu ít nhất "
                    "4 ký tự."
                ),
            )

        if password != confirm_password:

            return render_template(
                "signup.html",
                error=(
                    "Mật khẩu xác nhận không khớp."
                ),
            )

        password_hash = (
            generate_password_hash(
                password
            )
        )

        try:

            with db() as conn:

                cur = conn.cursor()

                cur.execute(
                    """
                    INSERT INTO users(
                        username,
                        password_hash,
                        role
                    )
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (
                        username,
                        password_hash,
                        "guest",
                    ),
                )

                user_id = cur.fetchone()["id"]

            session.update(
                user_id=user_id,
                username=username,
                role="guest",
            )

            return redirect(
                url_for("main.profile")
            )

        except Exception as exc:

            current_app.logger.exception(
                exc
            )

            return render_template(
                "signup.html",
                error=(
                    "Tên đăng nhập đã tồn tại "
                    "hoặc không thể tạo tài khoản."
                ),
            )

    return render_template(
        "signup.html"
    )


# ============================================================
# 20. LOGIN
# ============================================================

@bp.route(
    "/login",
    methods=["GET", "POST"],
)
def login():

    if request.method == "POST":

        username = (
            request.form
            .get(
                "username",
                "",
            )
            .strip()
        )

        password = request.form.get(
            "password",
            "",
        )

        with db() as conn:

            cur = conn.cursor()

            cur.execute(
                """
                SELECT
                    id,
                    username,
                    password_hash,
                    role
                FROM users
                WHERE username = %s
                LIMIT 1
                """,
                (username,),
            )

            user = cur.fetchone()

        valid = False

        if user:

            stored_hash = (
                user["password_hash"]
                or ""
            )

            try:

                valid = check_password_hash(
                    stored_hash,
                    password,
                )

            except (
                ValueError,
                TypeError,
            ):

                # Hỗ trợ dữ liệu cũ nếu
                # password_hash đang chứa plaintext.
                valid = (
                    stored_hash
                    == password
                )

                if valid:

                    new_hash = (
                        generate_password_hash(
                            password
                        )
                    )

                    with db() as conn:

                        cur = conn.cursor()

                        cur.execute(
                            """
                            UPDATE users
                            SET password_hash = %s
                            WHERE id = %s
                            """,
                            (
                                new_hash,
                                user["id"],
                            ),
                        )

        if valid:

            session.update(
                user_id=user["id"],
                username=user["username"],
                role=user["role"],
            )

            return redirect(
                url_for("main.dashboard")
            )

        return render_template(
            "login.html",
            error=(
                "Tên đăng nhập hoặc mật khẩu "
                "không đúng."
            ),
        )

    return render_template(
        "login.html"
    )


# ============================================================
# 21. LOGOUT
# ============================================================

@bp.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("main.login")
    )

# ============================================================
# DASHBOARD
# ============================================================

@bp.route("/dashboard")
@login_required()
def dashboard():

    # Chuyển admin sang trang quản trị
    if session["role"] == "admin":
        return redirect(url_for("main.admin"))

    user_id = session["user_id"]

    # ========================================================
    # 1. LẤY PROFILE VÀ DANH SÁCH PHIÊN PHỎNG VẤN
    # ========================================================

    with db() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM candidates
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )

        profile = cur.fetchone()

        cur.execute(
            """
            SELECT
                s.*,
                c.full_name,

                COUNT(DISTINCT a.id) AS answer_count,

                COALESCE(
                    AVG(sc.total_score),
                    0
                ) AS score

            FROM interview_sessions s

            JOIN candidates c
                ON c.id = s.candidate_id

            LEFT JOIN answers a
                ON a.session_id = s.id

            LEFT JOIN scores sc
                ON sc.answer_id = a.id

            WHERE c.user_id = %s

            GROUP BY
                s.id,
                c.full_name

            ORDER BY s.id DESC

            LIMIT 5
            """,
            (user_id,),
        )

        attempts = cur.fetchall()

    # ========================================================
    # 2. ĐIỂM KỸ NĂNG MẶC ĐỊNH
    # ========================================================

    skill_preview = [
        ("Knowledge / Technical Knowledge", 0.0),
        ("Problem Solving", 0.0),
        ("JD Fit", 0.0),
        ("Communication", 0.0),
        ("Cultural Fit", 0.0),
    ]

    # ========================================================
    # 3. LẤY ĐIỂM KỸ NĂNG CỦA PHIÊN GẦN NHẤT
    # ========================================================

    if attempts:

        latest = attempts[0]

        with db() as conn:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT
                    AVG(sc.knowledge_score)
                        AS knowledge,

                    AVG(sc.problem_solving_score)
                        AS problem_solving,

                    AVG(sc.jd_fit_score)
                        AS jd_fit,

                    AVG(sc.communication_score)
                        AS communication,

                    AVG(sc.cultural_fit_score)
                        AS cultural_fit

                FROM answers a

                JOIN scores sc
                    ON sc.answer_id = a.id

                WHERE a.session_id = %s
                """,
                (latest["id"],),
            )

            score_row = cur.fetchone()

        if score_row:

            def safe_score(value):
                try:
                    if value is None:
                        return 0.0

                    return round(float(value), 1)

                except (TypeError, ValueError):
                    return 0.0

            skill_preview = [
                (
                    "Knowledge / Technical Knowledge",
                    safe_score(score_row["knowledge"]),
                ),
                (
                    "Problem Solving",
                    safe_score(score_row["problem_solving"]),
                ),
                (
                    "JD Fit",
                    safe_score(score_row["jd_fit"]),
                ),
                (
                    "Communication",
                    safe_score(score_row["communication"]),
                ),
                (
                    "Cultural Fit",
                    safe_score(score_row["cultural_fit"]),
                ),
            ]

    # ========================================================
    # 4. RENDER DASHBOARD
    # ========================================================

    return render_template(
        "dashboard.html",
        profile=profile,
        attempts=attempts,
        roles=ROLES,
        skill_preview=skill_preview,
    )

# ============================================================
# 23. PROFILE
# ============================================================

@bp.route("/profile", methods=["GET", "POST"])
@login_required("guest")
def profile():
    user_id = session["user_id"]

    # 1. Lấy thông tin tài khoản
    with db() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, username
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        user = cur.fetchone()

        if not user:
            return redirect(url_for("main.dashboard"))

        # 2. Lấy hồ sơ ứng viên
        cur.execute(
            """
            SELECT id, user_id, full_name, email
            FROM candidates
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        candidate = cur.fetchone()

        # 3. Tạo hồ sơ nếu người dùng chưa có
        if not candidate:
            cur.execute(
                """
                INSERT INTO candidates (user_id, full_name)
                VALUES (%s, %s)
                RETURNING id, user_id, full_name, email
                """,
                (user_id, user["username"]),
            )
            candidate = cur.fetchone()

        candidate_id = candidate["id"]

        # 4. Xử lý khi người dùng lưu hồ sơ
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip()
            cv = request.files.get("cv")

            # Cập nhật thông tin cá nhân
            cur.execute(
                """
                UPDATE candidates
                SET full_name = %s,
                    email = %s
                WHERE id = %s
                """,
                (
                    full_name or None,
                    email or None,
                    candidate_id,
                ),
            )

            # 5. Nếu có CV mới thì lưu và trích xuất nội dung
            if cv and cv.filename:
                original_name = cv.filename
                extension = original_name.rsplit(".", 1)[-1].lower()

                if extension not in ("pdf", "docx"):
                    return render_template(
                        "profile.html",
                        username=user["username"],
                        candidate=candidate,
                        cv_doc=None,
                        skills=[],
                        error="Chỉ chấp nhận file CV định dạng PDF hoặc DOCX.",
                    )

                safe_name = re.sub(
                    r"[^\w.\- ]",
                    "_",
                    original_name,
                    flags=re.UNICODE,
                )

                upload_folder = current_app.config["UPLOAD_FOLDER"]
                upload_folder.mkdir(parents=True, exist_ok=True)

                # Tên file riêng để tránh ghi đè CV của người khác
                import uuid

                stored_name = f"{uuid.uuid4().hex}_{safe_name}"
                file_path = upload_folder / stored_name

                cv.save(file_path)

                try:
                    raw_text = extract_document(file_path)
                    cleaned_text = clean_text(raw_text or "")

                    cur.execute(
                        """
                        INSERT INTO documents (
                            candidate_id,
                            document_type,
                            file_name,
                            raw_text,
                            cleaned_text
                        )
                        VALUES (%s, 'CV', %s, %s, %s)
                        """,
                        (
                            candidate_id,
                            original_name,
                            raw_text or "",
                            cleaned_text or "",
                        ),
                    )

                except Exception:
                    current_app.logger.exception(
                        "Không thể đọc nội dung CV: %s",
                        original_name,
                    )

                    return render_template(
                        "profile.html",
                        username=user["username"],
                        candidate=candidate,
                        cv_doc=None,
                        skills=[],
                        error=(
                            "Không đọc được nội dung CV. "
                            "Hãy kiểm tra file PDF/DOCX rồi thử lại."
                        ),
                    )

            return redirect(url_for("main.profile"))

        # 6. Lấy CV gần nhất đã lưu
        cur.execute(
            """
            SELECT id, file_name, cleaned_text, created_at
            FROM documents
            WHERE candidate_id = %s
              AND document_type = 'CV'
            ORDER BY id DESC
            LIMIT 1
            """,
            (candidate_id,),
        )
        cv_doc = cur.fetchone()

    # 7. Trích xuất danh sách kỹ năng từ CV
    cv_text = ""
    if cv_doc:
        cv_text = cv_doc["cleaned_text"] or ""

    skills = standardize_skills(cv_text)

    # 8. Hiển thị trang hồ sơ cá nhân
    return render_template(
        "profile.html",
        candidate=candidate,
        cv_doc=cv_doc,
        skills=skills,
        username=user["username"],
    )

# ============================================================
# 23. INTERVIEW_SETUP
# ============================================================

@bp.route("/interview/setup", methods=["GET", "POST"])
@login_required("guest")
def interview_setup():

    # ========================================================
    # POST
    # ========================================================

    if request.method == "POST":
        print(
            "DEBUG: PROFILE POST CALLED",
            flush=True,
        )

        cv = request.files.get("cv")

        jd = (
            request.form
            .get(
                "jd",
                "",
            )
            .strip()
        )

        position = (
            request.form
            .get(
                "position",
                "",
            )
            .strip()
        )

        level = (
            request.form
            .get(
                "level",
                "Junior",
            )
            .strip()
        )

        cv_text = (
            request.form
            .get(
                "cv_text",
                "",
            )
            .strip()
        )

        cv_name = ""

        # ====================================================
        # 1. SAVE CV
        # ====================================================

        if cv and cv.filename:

            safe = re.sub(
                r"[^\w.\- ]",
                "_",
                cv.filename,
                flags=re.UNICODE,
            )

            upload_folder = (
                current_app.config[
                    "UPLOAD_FOLDER"
                ]
            )

            upload_folder.mkdir(
                parents=True,
                exist_ok=True,
            )

            path = (
                upload_folder
                / safe
            )

            cv.save(path)

            cv_name = safe

            if not cv_text:

                cv_text = (
                    extract_document(
                        path
                    )
                )

        # ====================================================
        # 2. CLEAN DATA
        # ====================================================

        cv_text = clean_text(
            cv_text
        )

        jd = clean_text(
            jd
        )

        if not jd:

            return render_template(
                "interview_setup.html",
                error="Vui lòng nhập Job Description.",
                roles=ROLES,
                profile=None,
            )

        # ====================================================
        # 3. BUILD PROFILE
        # ====================================================

        profile_data = (
            build_custom_profile(
                jd,
                position or None,
                level,
            )
        )

        # ====================================================
        # 4. SKILLS
        # ====================================================

        candidate_skills = (
            standardize_skills(
                cv_text
            )
        )

        jd_skills = (
            standardize_skills(
                jd
            )
        )

        # ====================================================
        # 5. CV ↔ JD MATCHING
        # ====================================================

        matching_result = (
            match_cv_jd(
                cv_text,
                jd,
            )
        )

        matching_score = (
            matching_result[
                "matching_score"
            ]
        )

        # ====================================================
        # 6. SKILL MATCHING
        # ====================================================

        skill_result = (
            calculate_skill_matching(
                candidate_skills,
                jd_skills,
            )
        )

        matched_skills = (
            skill_result[
                "matched_skills"
            ]
        )

        skill_gaps = (
            skill_result[
                "skill_gaps"
            ]
        )

        # ====================================================
        # 7. FALLBACK SKILLS
        # ====================================================

        if not jd_skills:

            jd_skills = profile_data.get(
                "hard",
                [],
            )

            skill_result = (
                calculate_skill_matching(
                    candidate_skills,
                    jd_skills,
                )
            )

            matched_skills = (
                skill_result[
                    "matched_skills"
                ]
            )

            skill_gaps = (
                skill_result[
                    "skill_gaps"
                ]
            )

        # ====================================================
        # 8. PROFILE DATA
        # ====================================================

        profile_data[
            "cv_text"
        ] = cv_text

        profile_data[
            "jd_text"
        ] = jd

        profile_data[
            "candidate_skills"
        ] = candidate_skills

        profile_data[
            "jd_skills"
        ] = jd_skills

        profile_data[
            "matched_skills"
        ] = matched_skills

        profile_data[
            "skill_gaps"
        ] = skill_gaps

        profile_data[
            "matching_score"
        ] = matching_score

        # ====================================================
        # 9. LLM QUESTIONS
        # ====================================================

        llm_questions = generate_llm_questions(
            profile_data,
            cv_text,
            jd,
        )

        if llm_questions:
            profile_data["questions"] = llm_questions
            profile_data["question_source"] = "LLM"

        else:
            profile_data["questions"] = build_interview_questions(
                profile_data,
                cv_text,
                jd,
            )
            profile_data["question_source"] = "Rule-based fallback"

        # Chuẩn hóa danh sách câu hỏi:
        # Mỗi phiên sử dụng toàn bộ câu hỏi thực tế trong danh sách.
        questions = profile_data.get("questions") or []

        # Loại bỏ câu hỏi rỗng, đồng thời giữ nguyên thứ tự.
        questions = [
            q.strip()
            for q in questions
            if isinstance(q, str) and q.strip()
        ]

        profile_data["questions"] = questions
        profile_data["question_count"] = len(questions)

        # Không tạo phiên phỏng vấn nếu không có câu hỏi.
        if not questions:
            return render_template(
                "interview_setup.html",
                error="Không tạo được câu hỏi phỏng vấn. Vui lòng thử lại.",
                roles=ROLES,
                profile=None,
            )
        # ====================================================
        # 10. DATABASE
        # ====================================================

        with db() as conn:

            cur = conn.cursor()

            # ------------------------------------------------
            # Candidate
            # ------------------------------------------------

            cur.execute(
                """
                SELECT id
                FROM candidates
                WHERE user_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    session["user_id"],
                ),
            )

            candidate = cur.fetchone()

            if candidate:

                candidate_id = (
                    candidate["id"]
                )

                cur.execute(
                    """
                    UPDATE candidates
                    SET full_name = %s
                    WHERE id = %s
                    """,
                    (
                        session.get(
                            "username",
                            "",
                        ),
                        candidate_id,
                    ),
                )

            else:

                cur.execute(
                    """
                    INSERT INTO candidates(
                        user_id,
                        full_name
                    )
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (
                        session["user_id"],
                        session.get(
                            "username",
                            "",
                        ),
                    ),
                )

                candidate_id = (
                    cur.fetchone()["id"]
                )

            # ------------------------------------------------
            # CV
            # ------------------------------------------------

            cur.execute(
                """
                INSERT INTO documents(
                    candidate_id,
                    document_type,
                    file_name,
                    raw_text,
                    cleaned_text
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    candidate_id,
                    "CV",
                    cv_name,
                    cv_text,
                    cv_text,
                ),
            )

            cv_document_id = (
                cur.fetchone()["id"]
            )
            # ------------------------------------------------
            # JD
            # ------------------------------------------------

            cur.execute(
                """
                INSERT INTO documents (
                    candidate_id,
                    document_type,
                    file_name,
                    raw_text,
                    cleaned_text
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    candidate_id,
                    "JD",
                    "job_description",
                    jd,
                    jd,
                ),
            )

            jd_document_id = cur.fetchone()["id"]
            # ------------------------------------------------
            # Interview Session
            # ------------------------------------------------

            cur.execute(
                """
                INSERT INTO interview_sessions (
                    candidate_id,
                    jd_id,
                    matching_score,
                    question_source,
                    position,
                    level,
                    profile_data
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    candidate_id,
                    jd_document_id,
                    matching_score,
                    profile_data["question_source"],
                    profile_data["position"],
                    profile_data["level"],
                    json.dumps(profile_data, ensure_ascii=False),
                ),
            )

            interview_session_id = cur.fetchone()["id"]

            print(
                f"[DEBUG] Đã tạo phiên mới: "
                f"id={interview_session_id}, "
                f"candidate_id={candidate_id}, "
                f"user_id={session.get('user_id')}",
                flush=True,
            )
            print(
                f"[DEBUG] PROFILE tạo phiên mới: ID={interview_session_id}",
                flush=True,
            )
            session["interview_session_id"] = interview_session_id
            session["interview_run_id"] = uuid.uuid4().hex
            session.modified = True
            
            # ------------------------------------------------
            # Questions
            # ------------------------------------------------

            for index, question in enumerate(
                questions,
                start=1,
            ):

                focus = question_focus(
                    question,
                    profile_data,
                )

                criterion = (
                    focus[0]
                    if focus
                    and focus[0] in {
                        c for c, _ in EVALUATION_CRITERIA
                    }
                    else "JD Fit"
                )

                cur.execute(
                    """
                    INSERT INTO questions(
                        session_id,
                        question_text,
                        criterion,
                        question_order
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        interview_session_id,
                        question,
                        criterion,
                        index,
                    ),
                )

        # ====================================================
        # SESSION
        # ====================================================

        session[
            "interview_session_id"
        ] = interview_session_id

        session[
            "interview_run_id"
        ] = uuid.uuid4().hex

        return redirect(
            url_for(
                "main.interview"
            )
        )

    # ========================================================
    # GET
    # ========================================================

    with db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM candidates
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                session["user_id"],
            ),
        )

        p = cur.fetchone()

    return render_template(
        "interview_setup.html",
        profile=p,
        roles=ROLES,
    )


# ============================================================
# 24. INTERVIEW
# ============================================================

@bp.route("/interview")
@login_required("guest")
def interview():

    interview_session_id = (
        session.get(
            "interview_session_id"
        )
    )

    if not interview_session_id:

        return redirect(
            url_for("main.profile")
        )

    with db() as conn:

        cur = conn.cursor()

        # ----------------------------------------------------
        # Session
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT *
            FROM interview_sessions
            WHERE id = %s
            LIMIT 1
            """,
            (
                interview_session_id,
            ),
        )

        interview_session = (
            cur.fetchone()
        )

        if not interview_session:

            return redirect(
                url_for("main.profile")
            )

        # ----------------------------------------------------
        # JD
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT *
            FROM documents
            WHERE id = %s
            LIMIT 1
            """,
            (
                interview_session[
                    "jd_id"
                ],
            ),
        )

        jd_document = (
            cur.fetchone()
        )

        # ----------------------------------------------------
        # CV
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT *
            FROM documents
            WHERE candidate_id = %s
              AND document_type = 'CV'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                interview_session[
                    "candidate_id"
                ],
            ),
        )

        cv_document = (
            cur.fetchone()
        )

        # ----------------------------------------------------
        # Questions
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT *
            FROM questions
            WHERE session_id = %s
            ORDER BY question_order
            """,
            (
                interview_session_id,
            ),
        )

        questions = (
            cur.fetchall()
        )

    if (
        not jd_document
        or not cv_document
    ):

        return redirect(
            url_for("main.profile")
        )

    cv_text = (
        cv_document[
            "cleaned_text"
        ]
        or ""
    )

    jd_text = (
        jd_document[
            "cleaned_text"
        ]
        or ""
    )

    # --------------------------------------------------------
    # Lấy profile_data đã lưu
    # --------------------------------------------------------

    profile_data = json_load(
        interview_session[
            "profile_data"
        ],
        {},
    )

    # Fallback nếu dữ liệu cũ không có
    if not profile_data:

        profile_data = (
            build_custom_profile(
                jd_text,
                interview_session[
                    "position"
                ],
                interview_session[
                    "level"
                ]
                or "Junior",
            )
        )

        candidate_skills = (
            standardize_skills(
                cv_text
            )
        )

        jd_skills = (
            standardize_skills(
                jd_text
            )
        )

        skill_result = (
            calculate_skill_matching(
                candidate_skills,
                jd_skills,
            )
        )

        profile_data[
            "cv_text"
        ] = cv_text

        profile_data[
            "jd_text"
        ] = jd_text

        profile_data[
            "candidate_skills"
        ] = candidate_skills

        profile_data[
            "jd_skills"
        ] = jd_skills

        profile_data[
            "matched_skills"
        ] = skill_result[
            "matched_skills"
        ]

        profile_data[
            "skill_gaps"
        ] = skill_result[
            "skill_gaps"
        ]

    # --------------------------------------------------------
    # Đảm bảo có dữ liệu
    # --------------------------------------------------------

    profile_data[
        "position"
    ] = interview_session[
        "position"
    ] or profile_data.get(
        "position",
        "Custom Position",
    )

    profile_data[
        "level"
    ] = interview_session[
        "level"
    ] or profile_data.get(
        "level",
        "Junior",
    )

    profile_data[
        "matching_score"
    ] = float(
        interview_session[
            "matching_score"
        ]
        or 0
    )

    profile_data[
        "questions"
    ] = [
        q["question_text"]
        for q in questions
    ]

    profile_data[
        "question_source"
    ] = interview_session[
        "question_source"
    ]

    # --------------------------------------------------------
    # Job object frontend
    # --------------------------------------------------------

    job = profile_data

    # Đảm bảo criteria chuẩn
    job[
        "criteria"
    ] = list(
        EVALUATION_CRITERIA
    )

    return render_template(
        "interview.html",
        profile=cv_document,
        job=job,
    )


# ============================================================
# 25. API ANSWER
# ============================================================

@bp.route(
    "/api/answer",
    methods=["POST"],
)
@login_required("guest")
def answer():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    answer_text = (
        data.get(
            "answer",
            "",
        )
        or ""
    )

    question_text = (
        data.get(
            "question",
            "",
        )
        or ""
    )

    duration = int(
        data.get(
            "duration",
            0,
        )
        or 0
    )

    interview_session_id = (
        session.get(
            "interview_session_id"
        )
    )

    if not interview_session_id:

        return jsonify(
            {
                "error": (
                    "Không tìm thấy phiên "
                    "phỏng vấn."
                )
            }
        ), 400

    if not question_text.strip():

        return jsonify(
            {
                "error": (
                    "Không có câu hỏi."
                )
            }
        ), 400

    # --------------------------------------------------------
    # Get session
    # --------------------------------------------------------

    with db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM interview_sessions
            WHERE id = %s
              AND candidate_id IN (
                  SELECT id
                  FROM candidates
                  WHERE user_id = %s
              )
            LIMIT 1
            """,
            (
                interview_session_id,
                session["user_id"],
            ),
        )

        interview_session = (
            cur.fetchone()
        )

    if not interview_session:

        return jsonify(
            {
                "error": (
                    "Phiên phỏng vấn không hợp lệ."
                )
            }
        ), 403

    # --------------------------------------------------------
    # Profile
    # --------------------------------------------------------

    job = json_load(
        interview_session[
            "profile_data"
        ],
        {},
    )

    if not job:

        with db() as conn:

            cur = conn.cursor()

            cur.execute(
                """
                SELECT cleaned_text
                FROM documents
                WHERE candidate_id = %s
                  AND document_type = 'CV'
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    interview_session[
                        "candidate_id"
                    ],
                ),
            )

            cv_row = cur.fetchone()

            cur.execute(
                """
                SELECT cleaned_text
                FROM documents
                WHERE id = %s
                """,
                (
                    interview_session[
                        "jd_id"
                    ],
                ),
            )

            jd_row = cur.fetchone()

        cv_text = (
            cv_row[
                "cleaned_text"
            ]
            if cv_row
            else ""
        )

        jd_text = (
            jd_row[
                "cleaned_text"
            ]
            if jd_row
            else ""
        )

        job = build_custom_profile(
            jd_text,
            interview_session[
                "position"
            ],
            interview_session[
                "level"
            ] or "Junior",
        )

        job[
            "cv_text"
        ] = cv_text

        job[
            "jd_text"
        ] = jd_text

    job[
        "criteria"
    ] = list(
        EVALUATION_CRITERIA
    )

    # --------------------------------------------------------
    # Analyze
    # --------------------------------------------------------

    result = analyze_answer(
        answer_text,
        question_text,
        job,
    )

    # --------------------------------------------------------
    # Find question
    # --------------------------------------------------------

    with db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT id
            FROM questions
            WHERE session_id = %s
              AND question_text = %s
            LIMIT 1
            """,
            (
                interview_session_id,
                question_text,
            ),
        )

        question_row = (
            cur.fetchone()
        )

        if not question_row:

            return jsonify(
                {
                    "error": (
                        "Không tìm thấy câu hỏi "
                        "trong phiên phỏng vấn."
                    )
                }
            ), 404

        question_id = (
            question_row["id"]
        )

        # ----------------------------------------------------
        # Insert Answer
        # ----------------------------------------------------

        cur.execute(
            """
            INSERT INTO answers(
                session_id,
                question_id,
                answer_text,
                transcript
            )
            VALUES (
                %s,
                %s,
                %s,
                %s
            )
            RETURNING id
            """,
            (
                interview_session_id,
                question_id,
                answer_text,
                result["cleaned"],
            ),
        )

        answer_id = (
            cur.fetchone()["id"]
        )

        # ----------------------------------------------------
        # Scores
        # ----------------------------------------------------

        criteria = result.get(
            "criteria",
            {},
        )

        cur.execute(
            """
            INSERT INTO scores(
                answer_id,
                knowledge_score,
                problem_solving_score,
                jd_fit_score,
                communication_score,
                cultural_fit_score,
                total_score
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING id
            """,
            (
                answer_id,

                criteria.get(
                    "Knowledge / Technical Knowledge",
                    0,
                ),

                criteria.get(
                    "Problem Solving",
                    0,
                ),

                criteria.get(
                    "JD Fit",
                    0,
                ),

                criteria.get(
                    "Communication",
                    0,
                ),

                criteria.get(
                    "Cultural Fit",
                    0,
                ),

                result.get(
                    "overall",
                    0,
                ),
            ),
        )

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        progress_map = {
            "Knowledge / Technical Knowledge":
                criteria.get(
                    "Knowledge / Technical Knowledge",
                    0,
                ),

            "Problem Solving":
                criteria.get(
                    "Problem Solving",
                    0,
                ),

            "JD Fit":
                criteria.get(
                    "JD Fit",
                    0,
                ),

            "Communication":
                criteria.get(
                    "Communication",
                    0,
                ),

            "Cultural Fit":
                criteria.get(
                    "Cultural Fit",
                    0,
                ),
        }

        for criterion, score in progress_map.items():

            cur.execute(
                """
                INSERT INTO progress(
                    candidate_id,
                    session_id,
                    criterion,
                    score
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    interview_session[
                        "candidate_id"
                    ],
                    interview_session_id,
                    criterion,
                    score,
                ),
            )


    result[
        "answer_id"
    ] = answer_id

    result[
        "question_id"
    ] = question_id

    result[
        "duration"
    ] = duration

    return jsonify(
        result
    )


# ============================================================
# 26. API AUDIO
# ============================================================

@bp.route(
    "/api/audio",
    methods=["POST"],
)
@login_required("guest")
def audio():

    audio_file = request.files.get(
        "audio"
    )

    if not audio_file:

        return jsonify(
            {
                "error": (
                    "Không nhận được file âm thanh."
                )
            }
        ), 400

    upload_folder = (
        current_app.config[
            "UPLOAD_FOLDER"
        ]
    )

    upload_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    name = (
        f"session_"
        f"{session['user_id']}_"
        f"{int(__import__('time').time())}"
        f".webm"
    )

    audio_file.save(
        upload_folder / name
    )

    return jsonify(
        {
            "saved": True,
            "name": name,
        }
    )

# ============================================================
# 27. REPORT
# ============================================================
@bp.route("/report")
@login_required("guest")
def report():

    interview_session_id = session.get(
        "interview_session_id"
    )

    print(
        "DEBUG user_id:",
        session.get("user_id"),
        flush=True,
    )

    print(
        "DEBUG interview_session_id:",
        interview_session_id,
        flush=True,
    )

    if not interview_session_id:
        return render_template(
            "report.html",
            latest=None,
            result=None,
            rows=[],
        )

    # ========================================================
    # 1. LOAD CURRENT SESSION
    # ========================================================

    with db() as conn:

        cur = conn.cursor()

        # Kiểm tra phiên có thuộc người dùng hiện tại không.
        cur.execute(
            """
            SELECT *
            FROM interview_sessions
            WHERE id = %s
              AND candidate_id IN (
                  SELECT id
                  FROM candidates
                  WHERE user_id = %s
              )
            LIMIT 1
            """,
            (
                interview_session_id,
                session["user_id"],
            ),
        )

        interview_session = cur.fetchone()

        if not interview_session:
            return render_template(
                "report.html",
                latest=None,
                result=None,
                rows=[],
            )

        # ====================================================
        # 2. LOAD QUESTIONS AND LATEST ANSWER PER QUESTION
        # ====================================================

        cur.execute(
            """
            SELECT
                a.id AS answer_id,
                a.session_id,
                a.question_id,
                a.answer_text,
                a.transcript,
                a.created_at AS answer_created_at,

                q.question_text,
                q.question_order,
                q.criterion,

                sc.knowledge_score,
                sc.problem_solving_score,
                sc.jd_fit_score,
                sc.communication_score,
                sc.cultural_fit_score,
                sc.total_score,

                s.position,
                s.level,
                s.matching_score,
                s.question_source,
                s.started_at,
                s.completed_at

            FROM questions q

            JOIN interview_sessions s
                ON s.id = q.session_id

            JOIN candidates c
                ON c.id = s.candidate_id

            LEFT JOIN LATERAL (
                SELECT a.*
                FROM answers a
                WHERE a.session_id = q.session_id
                  AND a.question_id = q.id
                ORDER BY a.id DESC
                LIMIT 1
            ) a ON TRUE

            LEFT JOIN LATERAL (
                SELECT sc.*
                FROM scores sc
                WHERE sc.answer_id = a.id
                ORDER BY sc.id DESC
                LIMIT 1
            ) sc ON TRUE

            WHERE s.id = %s
              AND c.user_id = %s

            ORDER BY
                q.question_order ASC NULLS LAST,
                q.id ASC
            """,
            (
                interview_session_id,
                session["user_id"],
            ),
        )

        raw_rows = cur.fetchall()

    # ========================================================
    # 3. EMPTY REPORT
    # ========================================================

    if not raw_rows:
        return render_template(
            "report.html",
            latest=None,
            result=None,
            rows=[],
        )

    # ========================================================
    # 4. CONVERT DATABASE ROWS
    # ========================================================

    rows = []

    criterion_names = [
        "Knowledge / Technical Knowledge",
        "Problem Solving",
        "JD Fit",
        "Communication",
        "Cultural Fit",
    ]

    def safe_score(value):

        try:
            if value is None:
                return 0.0

            return float(value)

        except (TypeError, ValueError):
            return 0.0

    for row in raw_rows:

        item = dict(row)

        criteria = {
            "Knowledge / Technical Knowledge":
                safe_score(
                    row["knowledge_score"]
                ),

            "Problem Solving":
                safe_score(
                    row["problem_solving_score"]
                ),

            "JD Fit":
                safe_score(
                    row["jd_fit_score"]
                ),

            "Communication":
                safe_score(
                    row["communication_score"]
                ),

            "Cultural Fit":
                safe_score(
                    row["cultural_fit_score"]
                ),
        }

        # Nếu câu hỏi chưa có câu trả lời hoặc chưa được chấm,
        # không coi câu đó là đã có điểm.
        total_score = (
            safe_score(row["total_score"])
            if row["total_score"] is not None
            else None
        )

        item["question"] = row["question_text"]

        item["answer"] = row["answer_text"] or ""

        item["cleaned"] = row["transcript"] or ""

        item["score"] = total_score

        item["criteria"] = criteria

        item["details"] = json.dumps(
            {
                "overall": total_score,
                "criteria": criteria,
            },
            ensure_ascii=False,
        )

        rows.append(item)

    # ========================================================
    # 5. AGGREGATE SCORES FOR CURRENT SESSION ONLY
    # ========================================================

    scored_rows = [
        row
        for row in rows
        if row["score"] is not None
    ]

    criteria = {}

    for criterion in criterion_names:

        values = [
            row["criteria"][criterion]
            for row in scored_rows
        ]

        criteria[criterion] = (
            round(
                sum(values) / len(values),
                1,
            )
            if values
            else 0.0
        )

    # Chỉ tính điểm tổng trên những câu đã được chấm.
    answer_scores = [
        row["score"]
        for row in scored_rows
    ]

    overall = (
        round(
            sum(answer_scores) / len(answer_scores),
            1,
        )
        if answer_scores
        else 0.0
    )

    # ========================================================
    # 6. STRENGTHS AND IMPROVEMENTS
    # ========================================================

    strengths = [
        criterion
        for criterion, score in criteria.items()
        if score >= 65
    ][:4]

    improvements = [
        criterion
        for criterion, score in sorted(
            criteria.items(),
            key=lambda item: item[1],
        )
        if score < 60
    ][:4]

    # ========================================================
    # 7. LATEST ANSWER
    # ========================================================

    answered_rows = [
        row
        for row in rows
        if row["answer_id"] is not None
    ]

    latest = (
        max(
            answered_rows,
            key=lambda row: (
                row["answer_created_at"] is not None,
                row["answer_created_at"],
                row["answer_id"],
            ),
        )
        if answered_rows
        else rows[0]
    )

    cleaned_text = latest["cleaned"] or ""

    word_count = len(
        re.findall(
            r"\w+",
            cleaned_text,
            re.UNICODE,
        )
    )

    # ========================================================
    # 8. REPORT RESULT
    # ========================================================

    result = {
        "overall": overall,

        "criteria": criteria,

        "strengths": strengths,

        "improvements": improvements,

        "cleaned": cleaned_text,

        "word_count": word_count,

        # Tổng số câu hỏi trong phiên,
        # bao gồm cả câu chưa trả lời.
        "question_count": len(rows),

        # Số câu hỏi đã có bản ghi trả lời.
        "answered_question_count": len(
            answered_rows
        ),

        # Số câu hỏi đã được chấm điểm.
        "scored_question_count": len(
            scored_rows
        ),

        "position": interview_session["position"],

        "level": interview_session["level"],

        "matching_score": safe_score(
            interview_session["matching_score"]
        ),
    }

    # ========================================================
    # 9. RENDER
    # ========================================================

    return render_template(
        "report.html",
        latest=latest,
        result=result,
        rows=rows,
    )
# ============================================================
# 28. PROGRESS
# ============================================================
@bp.route("/progress")
@login_required("guest")
def progress():

    user_id = session["user_id"]

    with db() as conn:
        cur = conn.cursor()

        # =====================================================
        # 1. LẤY LỊCH SỬ PHỎNG VẤN CỦA NGƯỜI DÙNG
        # =====================================================
        cur.execute(
            """
            SELECT
                s.id,
                s.position,
                s.level,
                s.matching_score,
                s.question_source,
                s.started_at,
                s.completed_at,

                -- Tổng số câu hỏi của phiên
                (
                    SELECT COUNT(*)
                    FROM questions q
                    WHERE q.session_id = s.id
                ) AS question_count,

                -- Số câu hỏi đã trả lời
                (
                    SELECT COUNT(DISTINCT a.question_id)
                    FROM answers a
                    WHERE a.session_id = s.id
                ) AS answered_question_count,

                -- Điểm trung bình của câu trả lời mới nhất
                (
                    SELECT AVG(latest_score.total_score)
                    FROM questions q
                    JOIN LATERAL (
                        SELECT a.id
                        FROM answers a
                        WHERE a.session_id = s.id
                          AND a.question_id = q.id
                        ORDER BY a.id DESC
                        LIMIT 1
                    ) latest_answer ON TRUE
                    JOIN LATERAL (
                        SELECT sc.total_score
                        FROM scores sc
                        WHERE sc.answer_id = latest_answer.id
                        ORDER BY sc.id DESC
                        LIMIT 1
                    ) latest_score ON TRUE
                    WHERE q.session_id = s.id
                ) AS overall_score

            FROM interview_sessions s

            JOIN candidates c
                ON c.id = s.candidate_id

            WHERE c.user_id = %s

            ORDER BY s.id DESC
            """,
            (user_id,),
        )

        history_rows = cur.fetchall()

        # =====================================================
        # 2. LẤY ĐIỂM TỪNG TIÊU CHÍ CỦA TỪNG PHIÊN
        #    Chỉ lấy câu trả lời mới nhất của mỗi câu hỏi.
        # =====================================================
        cur.execute(
            """
            WITH latest_answers AS (
                SELECT DISTINCT ON (a.session_id, a.question_id)
                    a.id AS answer_id,
                    a.session_id,
                    a.question_id
                FROM answers a
                JOIN interview_sessions s
                    ON s.id = a.session_id
                JOIN candidates c
                    ON c.id = s.candidate_id
                WHERE c.user_id = %s
                ORDER BY
                    a.session_id,
                    a.question_id,
                    a.id DESC
            )
            SELECT
                la.session_id,
                criteria.criterion,
                AVG(criteria.score) AS score

            FROM latest_answers la

            JOIN scores sc
                ON sc.answer_id = la.answer_id

            CROSS JOIN LATERAL (
                VALUES
                    ('Knowledge', sc.knowledge_score),
                    ('Problem Solving', sc.problem_solving_score),
                    ('JD Fit', sc.jd_fit_score),
                    ('Communication', sc.communication_score),
                    ('Cultural Fit', sc.cultural_fit_score)
            ) AS criteria(criterion, score)

            GROUP BY
                la.session_id,
                criteria.criterion

            ORDER BY
                la.session_id DESC,
                criteria.criterion
            """,
            (user_id,),
        )

        criterion_rows = cur.fetchall()

    # =====================================================
    # 3. CHUYỂN KẾT QUẢ THÀNH DANH SÁCH DICTIONARY
    # =====================================================
    history = []

    for row in history_rows:
        item = dict(row)

        score = item.get("overall_score")

        item["overall_score"] = (
            round(float(score), 1)
            if score is not None
            else 0
        )

        item["question_count"] = int(
            item.get("question_count") or 0
        )

        item["answered_question_count"] = int(
            item.get("answered_question_count") or 0
        )

        history.append(item)

    # =====================================================
    # 4. THỐNG KÊ CÁC PHIÊN ĐÃ HOÀN THÀNH
    # =====================================================
    completed_history = [
        item
        for item in history
        if item.get("completed_at") is not None
    ]

    completed_scores = [
        item["overall_score"]
        for item in completed_history
        if item["overall_score"] > 0
    ]

    total_sessions = len(history)

    average_score = (
        round(
            sum(completed_scores) / len(completed_scores),
            1,
        )
        if completed_scores
        else 0
    )

    highest_score = (
        max(completed_scores)
        if completed_scores
        else 0
    )

    # =====================================================
    # 5. DỮ LIỆU BIỂU ĐỒ THEO THỨ TỰ THỜI GIAN
    # =====================================================
    chart_rows = [
        item
        for item in reversed(completed_history)
        if item["overall_score"] > 0
    ]

    chart_labels = [
        f"Session {index + 1}"
        for index in range(len(chart_rows))
    ]

    chart_scores = [
        item["overall_score"]
        for item in chart_rows
    ]

    # =====================================================
    # 6. TRẢ DỮ LIỆU CHO GIAO DIỆN
    # =====================================================
    return render_template(
        "progress.html",
        rows=history,
        total_sessions=total_sessions,
        completed_sessions=len(completed_history),
        average_score=average_score,
        highest_score=highest_score,
        chart_labels=chart_labels,
        chart_scores=chart_scores,
        criterion_rows=criterion_rows,
    )
# ============================================================
# 29. ADMIN
# ============================================================

@bp.route("/admin")
@login_required("admin")
def admin():

    with db() as conn:

        cur = conn.cursor()

        # ----------------------------------------------------
        # Users
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT
                id,
                username,
                role,
                created_at
            FROM users
            ORDER BY id
            """
        )

        users = cur.fetchall()

        # ----------------------------------------------------
        # Interview sessions
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT
                s.*,
                c.full_name,
                u.username

            FROM interview_sessions s

            JOIN candidates c
                ON c.id = s.candidate_id

            JOIN users u
                ON u.id = c.user_id

            ORDER BY s.id DESC
            """
        )

        rows = cur.fetchall()

    return render_template(
        "admin.html",
        users=users,
        rows=rows,
    )


@bp.route("/api/complete-interview", methods=["POST"])
@login_required("guest")
def complete_interview():
    """Chỉ hoàn thành phiên khi đã trả lời đủ câu hỏi."""

    user_id = session.get("user_id")
    interview_session_id = session.get("interview_session_id")

    if not user_id or not interview_session_id:
        return jsonify({
            "error": "Không tìm thấy phiên phỏng vấn hiện tại."
        }), 400

    with db() as conn:
        cur = conn.cursor()

        # Xác minh phiên thuộc người dùng hiện tại.
        cur.execute(
            """
            SELECT s.id
            FROM interview_sessions s
            JOIN candidates c ON c.id = s.candidate_id
            WHERE s.id = %s
              AND c.user_id = %s
            LIMIT 1
            """,
            (interview_session_id, user_id),
        )

        interview = cur.fetchone()

        if not interview:
            return jsonify({
                "error": "Phiên phỏng vấn không tồn tại hoặc không thuộc tài khoản này."
            }), 404

        # Đếm tổng câu hỏi và số câu đã có câu trả lời.
        cur.execute(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM questions
                    WHERE session_id = %s
                ) AS total_questions,
                (
                    SELECT COUNT(DISTINCT a.question_id)
                    FROM answers a
                    JOIN questions q ON q.id = a.question_id
                    WHERE a.session_id = %s
                      AND q.session_id = %s
                ) AS answered_questions
            """,
            (
                interview_session_id,
                interview_session_id,
                interview_session_id,
            ),
        )

        counts = cur.fetchone()

        total = int(counts["total_questions"] or 0)
        answered = int(counts["answered_questions"] or 0)

        if total == 0 or answered < total:
            return jsonify({
                "error": (
                    f"Bạn mới trả lời {answered}/{total} câu hỏi. "
                    "Hãy hoàn thành tất cả câu hỏi trước khi xem báo cáo."
                ),
                "total_questions": total,
                "answered_questions": answered,
            }), 400

        # Không ghi đè thời điểm kết thúc nếu đã hoàn thành trước đó.
        cur.execute(
            """
            UPDATE interview_sessions
            SET completed_at = COALESCE(
                completed_at,
                CURRENT_TIMESTAMP
            )
            WHERE id = %s
            """,
            (interview_session_id,),
        )

    return jsonify({
        "success": True,
        "message": "Phiên phỏng vấn đã hoàn thành.",
    }), 200
