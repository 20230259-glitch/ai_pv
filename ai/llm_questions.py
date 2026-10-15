import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_TIMEOUT = 45


def _get_config():
    api_url = os.getenv("LLM_API_URL", DEFAULT_API_URL).strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    timeout_raw = os.getenv("LLM_TIMEOUT", str(DEFAULT_TIMEOUT)).strip()

    try:
        timeout = max(5, int(timeout_raw))
    except ValueError:
        timeout = DEFAULT_TIMEOUT

    return api_url, api_key, model, timeout


def _is_local_url(url):
    value = (url or "").lower()

    return any(
        host in value
        for host in (
            "localhost",
            "127.0.0.1",
            "0.0.0.0"
        )
    )


def _extract_content(data):
    """
    Đọc content từ response của các API
    tương thích OpenAI Chat Completions.
    """

    choices = data.get("choices") or []

    if not choices:
        return ""

    first = choices[0] or {}

    message = first.get("message") or {}

    content = message.get("content", "")

    if isinstance(content, str):
        return content.strip()

    # Một số provider trả content dạng list
    if isinstance(content, list):

        parts = []

        for item in content:

            if (
                isinstance(item, dict)
                and isinstance(item.get("text"), str)
            ):
                parts.append(item["text"])

        return "\n".join(parts).strip()

    return ""


def _parse_questions(content):
    """
    Parse JSON từ câu trả lời của LLM.

    Cho phép LLM trả:
    {
        "questions": [
            "...",
            "...",
            ...
        ]
    }

    hoặc JSON nằm trong markdown code block.
    """

    text = (content or "").strip()

    if not text:
        return []

    fenced = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    if fenced:
        text = fenced.group(1).strip()

    candidates = [text]

    # Tìm JSON object
    obj_start = text.find("{")
    obj_end = text.rfind("}")

    if obj_start >= 0 and obj_end > obj_start:

        candidates.append(
            text[obj_start:obj_end + 1]
        )

    # Tìm JSON array
    arr_start = text.find("[")
    arr_end = text.rfind("]")

    if arr_start >= 0 and arr_end > arr_start:

        candidates.append(
            text[arr_start:arr_end + 1]
        )

    for candidate in candidates:

        try:
            data = json.loads(candidate)

        except json.JSONDecodeError:
            continue

        if isinstance(data, dict):

            data = data.get(
                "questions",
                []
            )

        if not isinstance(data, list):
            continue

        questions = []

        seen = set()

        for item in data:

            if not isinstance(item, str):
                continue

            q = re.sub(
                r"^\s*\d+[.)-]\s*",
                "",
                item.strip()
            )

            q = re.sub(
                r"\s+",
                " ",
                q
            ).strip()

            if not q:
                continue

            key = q.casefold()

            if key in seen:
                continue

            seen.add(key)

            questions.append(q)

        if len(questions) == 10:
            return questions

    return []


def _build_prompt(profile, cv_text, jd_text):

    position = (
        profile.get("display_position")
        or profile.get("position")
        or "vị trí mục tiêu"
    )

    level = profile.get(
        "level",
        "Junior"
    )

    criteria = profile.get(
        "criteria",
        []
    )

    hard = profile.get(
        "hard",
        []
    )

    soft = profile.get(
        "soft",
        []
    )

    matched = profile.get(
        "matched_skills",
        []
    )

    gaps = profile.get(
        "skill_gaps",
        []
    )

    matching_score = profile.get(
        "matching_score",
        0
    )

    criteria_text = ", ".join(
        f"{name} ({weight}%)"
        for name, weight in criteria
    )

    return f"""
Bạn là Question Generation Engine của một nền tảng AI phỏng vấn mô phỏng cá nhân hóa.

Hãy sinh đúng 10 câu hỏi phỏng vấn bằng tiếng Việt cho MỘT vị trí duy nhất.

VỊ TRÍ:
{position}

LEVEL:
{level}

CV-JD SEMANTIC MATCHING:
{matching_score}/100

SKILL MATCH:
{", ".join(matched) or "Không có dữ liệu"}

SKILL GAP:
{", ".join(gaps) or "Không có dữ liệu"}

HARD SKILLS CỦA VỊ TRÍ:
{", ".join(hard) or "Không có dữ liệu"}

SOFT SKILLS CỦA VỊ TRÍ:
{", ".join(soft) or "Không có dữ liệu"}

TIÊU CHÍ ĐÁNH GIÁ:
{criteria_text or "Không có dữ liệu"}

CV ỨNG VIÊN:
{cv_text or "Không có CV text"}

JOB DESCRIPTION:
{jd_text or "Không có JD"}


YÊU CẦU SINH CÂU HỎI:

1. Cá nhân hóa theo bằng chứng thực tế có trong CV.

2. Không được bịa kinh nghiệm hoặc thành tích của ứng viên.

3. Ưu tiên các skill gap trong JD để kiểm chứng phần CV còn thiếu bằng chứng.

4. Điều chỉnh độ khó theo level {level}.

5. Bao phủ chuyên môn, problem solving, communication
   và mức độ phù hợp với JD.

6. Có câu hỏi về dự án hoặc kinh nghiệm cụ thể.

7. Có câu hỏi tình huống.

8. Có câu hỏi đào sâu.

9. Không lặp ý.

10. Không dùng 10 câu hỏi cho 10 vị trí khác nhau.

11. Mỗi câu hỏi phải hoàn chỉnh,
    rõ ràng và có thể trả lời bằng kinh nghiệm
    hoặc cách tiếp cận.

12. Trả về ĐÚNG định dạng JSON.

Không thêm giải thích bên ngoài JSON.

Định dạng:

{{
    "questions": [
        "Câu 1",
        "Câu 2",
        "Câu 3",
        "Câu 4",
        "Câu 5",
        "Câu 6",
        "Câu 7",
        "Câu 8",
        "Câu 9",
        "Câu 10"
    ]
}}
""".strip()


def generate_llm_questions(
    profile,
    cv_text="",
    jd_text=""
):
    """
    Sinh 10 câu hỏi cá nhân hóa bằng LLM.

    Thành công:
        trả về list gồm đúng 10 câu hỏi.

    Không cấu hình LLM,
    API lỗi hoặc dữ liệu không hợp lệ:
        trả về [].

    Khi trả về [] thì routes.py
    sẽ dùng rule-based fallback.
    """

    (
        api_url,
        api_key,
        model,
        timeout
    ) = _get_config()

    # API cloud cần API key.
    # API local như LM Studio/Ollama
    # có thể không cần API key.
    if (
        not api_key
        and not _is_local_url(api_url)
    ):
        return []

    if not model:

        logger.warning(
            "LLM_MODEL is not configured; "
            "using rule-based question fallback."
        )

        return []

    payload = {

        "model": model,

        "messages": [

            {
                "role": "system",
                "content": (
                    "Bạn là AI tạo câu hỏi "
                    "phỏng vấn cá nhân hóa. "
                    "Chỉ trả về JSON hợp lệ "
                    "theo yêu cầu của người dùng."
                )
            },

            {
                "role": "user",
                "content": _build_prompt(
                    profile,
                    cv_text,
                    jd_text
                )
            }

        ],

        "temperature": 0.4
    }

    body = json.dumps(
        payload,
        ensure_ascii=False
    ).encode("utf-8")

    headers = {
        "Content-Type":
            "application/json"
    }

    if api_key:

        headers["Authorization"] = (
            f"Bearer {api_key}"
        )

    request = Request(
        api_url,
        data=body,
        headers=headers,
        method="POST"
    )

    try:

        with urlopen(
            request,
            timeout=timeout
        ) as response:

            raw = response.read().decode(
                "utf-8"
            )

        data = json.loads(raw)

    except HTTPError as exc:

        logger.warning(
            "LLM HTTP error %s: %s",
            exc.code,
            exc.reason
        )

        return []

    except (
        URLError,
        TimeoutError,
        OSError
    ) as exc:

        logger.warning(
            "LLM connection error: %s",
            exc
        )

        return []

    except json.JSONDecodeError:

        logger.warning(
            "LLM returned invalid JSON envelope."
        )

        return []

    content = _extract_content(
        data
    )

    questions = _parse_questions(
        content
    )

    if len(questions) != 10:

        logger.warning(
            "LLM returned %s valid questions "
            "instead of exactly 10.",
            len(questions)
        )

        return []

    return questions