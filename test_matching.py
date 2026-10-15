from ai.matching import match_cv_jd


cv_text = """
Tôi là lập trình viên Python.
Tôi có kinh nghiệm xây dựng REST API
bằng FastAPI và Flask.
Tôi sử dụng MySQL và PostgreSQL.
Tôi từng phát triển các hệ thống backend
và triển khai ứng dụng web.
"""


jd_text = """
Công ty cần tuyển Backend Developer.
Ứng viên cần có kinh nghiệm Python,
xây dựng REST API bằng FastAPI hoặc Flask,
có kiến thức về cơ sở dữ liệu MySQL hoặc PostgreSQL.
Có kinh nghiệm phát triển hệ thống backend
là một lợi thế.
"""


result = match_cv_jd(
    cv_text,
    jd_text
)


print("CV-JD Matching Result")
print("----------------------")

print(
    "Matching Score:",
    result["matching_score"],
    "%"
)