# Nhật ký thay đổi AutoDub

## 2026-09-08 — INIT-01: Khởi tạo tài liệu dự án

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Tạo tài liệu tổng quan, kế hoạch, quy tắc, danh sách nhiệm vụ và kiến trúc dự kiến ban đầu.
- **Tệp:** `README.md`, `PLAN.md`, `RULES.md`, `TASKS.md`, `docs/ARCHITECTURE.md`
- **Kiểm chứng:** Đã kiểm tra sự tồn tại của tệp, liên kết nội bộ và trạng thái chưa triển khai ứng dụng.
- **Còn lại:** Các quyết định chi tiết về phạm vi, công nghệ và môi trường được chuyển sang task sau.

## 2026-09-08 — INIT-02: Khởi tạo cấu trúc repository

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Tạo các thư mục giữ chỗ và quy tắc loại trừ dữ liệu không được đưa lên Git.
- **Tệp:** `.gitignore`, `frontend/`, `backend/`, `tests/`, `storage/`, `docs/`
- **Kiểm chứng:** Đã kiểm tra cấu trúc dự kiến; chưa ghi nhận mã ứng dụng hoặc dữ liệu runtime.
- **Còn lại:** Không.

## 2026-09-10 — INIT-03: Chốt hướng phát triển và phạm vi MVP

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Chốt luồng MVP chạy cục bộ cho một người dùng, một video tại một thời điểm; thống nhất stack, ranh giới kiến trúc, phần ngoài phạm vi và thứ tự phát triển.
- **Tệp:** `README.md`, `PLAN.md`, `TASKS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Đã đối chiếu tính nhất quán tài liệu, kiểm tra liên kết Markdown và `git diff --check` theo bản ghi hiện có.
- **Còn lại:** Các tích hợp Whisper, Gemini, Edge-TTS, FFmpeg và giới hạn video chưa được kiểm chứng.

## 2026-09-10 — INIT-04: Chốt môi trường phát triển

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Ghi nhận cấu hình máy; chọn Python 3.11, worker Windows, Whisper `small`, ưu tiên `h264_nvenc` và giữ đường chạy CPU dự phòng.
- **Tệp:** `docs/ENVIRONMENT.md`, `README.md`, `TASKS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Đã đối chiếu kết quả kiểm tra môi trường do người phát triển cung cấp.
- **Còn lại:** Chưa kiểm chứng Whisper chạy GPU và hiệu năng pipeline thực tế.

## 2026-09-10 — ENV-00: Xác nhận dung lượng ổ đĩa

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Chuyển dự án sang ổ D và xác nhận còn khoảng 27 GB trống, đủ để bắt đầu MVP.
- **Tệp:** `TASKS.md`, `docs/ENVIRONMENT.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Đã đối chiếu dung lượng ổ D do người phát triển cung cấp.
- **Còn lại:** Tiếp tục theo dõi và duy trì khoảng 10 GB trống khi tải model, tạo tệp trung gian và render.

## 2026-09-14 — ENV-01: Khởi tạo FastAPI tối thiểu

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Thêm ứng dụng FastAPI tối thiểu với endpoint `GET /health` trả về trạng thái JSON.
- **Tệp:** `backend/app/main.py`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Chạy `& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`, sau đó `Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing`; nhận HTTP 200 và nội dung `{"status":"ok"}`.
- **Còn lại:** Không.
