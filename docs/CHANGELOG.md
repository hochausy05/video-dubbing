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

## 2026-09-14 — ENV-02: Khởi tạo React, TypeScript và Vite tối thiểu

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Khởi tạo ứng dụng React/TypeScript/Vite tối thiểu với trang chào AutoDub.
- **Tệp:** `frontend/package.json`, `frontend/package-lock.json`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig*.json`, `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/index.css`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** `npm run build` hoàn tất thành công; chạy `npm run dev -- --host 127.0.0.1 --port 5173`, rồi `Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing` nhận HTTP 200 và xác nhận nội dung có `AutoDub`.
- **Còn lại:** Không.

## 2026-09-15 — ENV-03: Phụ thuộc và cấu hình mẫu an toàn

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Thêm phụ thuộc backend trực tiếp đã kiểm chứng, tệp cấu hình mẫu không chứa bí mật và hướng dẫn PowerShell để cài đặt/chạy backend lẫn frontend.
- **Tệp:** `backend/requirements.txt`, `.env.example`, `README.md`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Chạy `py -3.11 -m venv backend\.venv` và `pip install -r backend\requirements.txt`; FastAPI trả HTTP 200 với `{"status":"ok"}`. `npm ci` và `npm run build` hoàn tất; Vite trả HTTP 200 với nội dung `AutoDub`. Đã xác nhận `.env` bị bỏ qua còn `.env.example` không bị bỏ qua.
- **Còn lại:** Không.

## 2026-09-15 — DATA-01: Chuyển định hướng lưu trữ sang Supabase PostgreSQL

- **Trạng thái:** Một phần
- **Thay đổi:** Cập nhật tài liệu để Supabase-hosted PostgreSQL thay SQLite cho metadata; quy định FastAPI là lớp truy cập duy nhất, SQLAlchemy với PostgreSQL driver, `DATABASE_URL` chỉ từ môi trường, UUID và timestamp có múi giờ. Nội dung tệp media vẫn ở storage do máy chủ quản lý; Auth, Storage, Realtime và RLS của Supabase chưa thuộc phạm vi hiện tại.
- **Tệp:** `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/PRD.md`, `docs/ENVIRONMENT.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Đối chiếu các tài liệu liên quan với quyết định lưu trữ mới; không triển khai mã, schema hoặc kết nối cơ sở dữ liệu.
- **Còn lại:** Cài đặt driver, cấu hình `DATABASE_URL`, tạo schema và kiểm chứng persistence trong phần triển khai DATA-01.

## 2026-09-15 — DATA-01: Bổ sung nhất quán tài liệu kế hoạch

- **Trạng thái:** Một phần
- **Thay đổi:** Bổ sung `README.md` và `PLAN.md` để Phase 3 và bảng công nghệ cùng chỉ Supabase-hosted PostgreSQL cho metadata, còn tệp media do backend-managed local storage quản lý.
- **Tệp:** `README.md`, `PLAN.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Tìm kiếm toàn bộ tài liệu hoạt động cho thấy không còn chỉ dẫn SQLite đang hiệu lực ngoài các bản ghi lịch sử/audit được giữ nguyên.
- **Còn lại:** Cài đặt driver, cấu hình `DATABASE_URL`, tạo schema và kiểm chứng persistence trong phần triển khai DATA-01.

## 2026-09-15 — DATA-01: Nền tảng persistence PostgreSQL

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm model SQLAlchemy cho Project, Job, Segment và Artifact cùng quan hệ khóa ngoại, UUID, timestamp có múi giờ, ràng buộc trạng thái/thứ tự/thời lượng và cơ chế khởi tạo bảng idempotent không xóa dữ liệu. Thêm cấu hình `DATABASE_URL` từ `.env` cục bộ và các dependency PostgreSQL cần thiết.
- **Tệp:** `.env.example`, `backend/requirements.txt`, `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/models/__init__.py`, `backend/app/models/base.py`, `backend/app/models/entities.py`, `docs/ARCHITECTURE.md`, `docs/ENVIRONMENT.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** `pip install -r backend\\requirements.txt` cài SQLAlchemy 2.0.52, psycopg 3.3.5 và python-dotenv 1.2.3; `compileall` và kiểm tra metadata model thành công. `.env` bị Git bỏ qua, `.env.example` không bị bỏ qua. Khởi tạo thật dừng trước khi kết nối vì `DATABASE_URL` chưa được cấu hình.
- **Còn lại:** Cần `DATABASE_URL` Supabase thật để tạo bảng, ghi/đọc lại bộ dữ liệu qua kết nối mới và dọn chỉ các bản ghi kiểm chứng trước khi có thể hoàn thành DATA-01.

## 2026-09-15 — DATA-01: Kiểm chứng Supabase PostgreSQL

- **Trạng thái:** Bị chặn
- **Thay đổi:** Không thay đổi schema hoặc dữ liệu từ lần kiểm chứng này.
- **Tệp:** `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Kết nối SQLAlchemy/psycopg đã tới Supabase nhưng bị từ chối xác thực mật khẩu trước khi khởi tạo bảng. Kiểm tra bổ sung qua Supabase cho thấy dự án đang hoạt động và chưa có bảng trong schema `public`.
- **Còn lại:** Cập nhật `DATABASE_URL` cục bộ với thông tin xác thực hợp lệ, sau đó chạy lại khởi tạo, kiểm chứng ghi/đọc sau kết nối mới và dọn dữ liệu kiểm chứng.

## 2026-09-15 — DATA-01: Hoàn tất kiểm chứng persistence Supabase

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Hoàn tất khởi tạo idempotent các bảng metadata và kiểm chứng persistence qua kết nối SQLAlchemy/psycopg thực tới Supabase PostgreSQL.
- **Tệp:** `TASKS.md`, `docs/ENVIRONMENT.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Tạo và commit một Project, Job, Segment, Artifact liên kết; đóng engine/session rồi đọc lại bằng engine/session mới; xác nhận UUID, timestamp có múi giờ, khóa ngoại, quan hệ và constraint trạng thái/thời lượng. Xóa Project kiểm chứng cùng toàn bộ bản ghi con do cascade; không drop bảng. `compileall`, `pip check`, `git diff --check` thành công; `.env` bị Git bỏ qua và bí mật không xuất hiện trong diff.
- **Còn lại:** Không.
