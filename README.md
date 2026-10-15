# PV_AI_DEMO v3

Demo Flask cho nền tảng AI Interview Platform đa ngành, thiết kế theo hướng career platform: đơn giản, hiện đại, AI hỗ trợ phía sau.

## Chạy

```powershell
& "C:\Users\DELL\AppData\Local\Programs\Python\Python314\python.exe" -m pip install -r requirements.txt
& "C:\Users\DELL\AppData\Local\Programs\Python\Python314\python.exe" run.py
```

Mở `http://127.0.0.1:5000`.

## Tài khoản demo
- Candidate: `guest / guest123`
- Admin: `admin / admin123`

## Luồng candidate
Landing → Đăng ký/Đăng nhập → CV + JD → Job Profile → Interview → STT/Transcript → Criteria Scoring → Report → Progress.

## Nhiều ngành và JD mới
Có role mẫu cho Sales, Software Developer, Data Analyst, Marketing, HR, Customer Service, UI/UX, Finance. Nếu không chọn role, dán JD bất kỳ để hệ thống tạo Custom Position + criteria.

## Audio / Speech-to-Text
- Browser `MediaRecorder` ghi audio và gửi `.webm` về server.
- Web Speech API `vi-VN` tạo transcript.
- Recognition tự restart sau các lần Chrome/Edge kết thúc nhận diện khi người dùng vẫn đang ghi, nên khoảng ngắt tự nhiên không làm mất phiên transcript.
- Nếu trình duyệt không hỗ trợ Web Speech API, người dùng vẫn có thể nhập text trực tiếp.

## Phạm vi demo
Scoring hiện là rule-based, minh bạch và có thể kiểm tra evidence; chưa giả lập một LLM/Whisper production. PDF/DOCX được text extraction; JPG/PNG được upload và hiển thị tên file, chưa OCR server-side.
