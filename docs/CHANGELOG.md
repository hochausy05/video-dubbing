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

## 2026-09-15 — UPLOAD-01: Upload video do máy chủ kiểm soát

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Thêm endpoint multipart tạo Project bằng UUID trên server, lưu video dưới đường dẫn cục bộ cố định theo UUID và chỉ lưu tham chiếu tương đối trong PostgreSQL. Xóa file vừa ghi nếu persistence thất bại.
- **Tệp:** `backend/app/main.py`, `backend/app/api/projects.py`, `backend/app/services/uploads.py`, `backend/app/core/config.py`, `backend/requirements.txt`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Upload HTTP thật một MP4 nhỏ và một upload có filename traversal đều nhận HTTP 201; metadata Project được xác nhận lại bằng kết nối Supabase mới, file nằm trong thư mục UUID do server tạo và không có đường dẫn tuyệt đối. Đã xóa hai Project, file upload và fixture kiểm chứng. `compileall`, `pip check`, `git diff --check` thành công; `.env` và runtime storage bị Git bỏ qua.
- **Còn lại:** Không.

## 2026-09-15 — UPLOAD-02: Xác thực video tải lên

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Chuẩn hóa giới hạn MP4, 100 MiB và 1800 giây trong PRD/cấu hình; ghi upload theo khối có giới hạn, dùng `ffprobe` kiểm tra container MP4 thực, video stream và thời lượng trước khi tạo Project; dọn thư mục UUID khi validation thất bại.
- **Tệp:** `.env.example`, `backend/app/api/projects.py`, `backend/app/core/config.py`, `backend/app/services/uploads.py`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/ENVIRONMENT.md`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Qua endpoint FastAPI thật với Supabase: MP4 hợp lệ và filename traversal nhận 201, có đúng một Project và file chỉ ở đường dẫn UUID; AVI nhận 415, file 104857601 byte nhận 413, MP4 giả nhận 422, MP4 1801 giây nhận 422. Mỗi case bị từ chối có 0 Project và không còn thư mục upload; đã xóa Project/fixture kiểm chứng. `compileall`, `pip check`, `git diff --check` thành công; `.env` và runtime storage bị Git bỏ qua.
- **Còn lại:** Không.

## 2026-09-21 — UI-01: API danh sách Project cho persistence giao diện

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm `GET /projects` với schema response ổn định, chỉ trả metadata Project hữu ích cho danh sách và sắp xếp mới nhất trước; thêm proxy Vite `/api` tới FastAPI cục bộ.
- **Tệp:** `backend/app/api/projects.py`, `backend/app/schemas/__init__.py`, `backend/app/schemas/projects.py`, `frontend/vite.config.ts`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Upload multipart MP4 thật qua FastAPI tạo một Project trong Supabase; gọi `GET /projects` và đọc lại cùng bản ghi bằng engine/session mới; xác nhận source reference không tuyệt đối; gọi `/api/projects` qua Vite proxy; `compileall`, `pip check`, frontend build và `git diff --check` thành công.
- **Còn lại:** Chưa triển khai frontend và chưa đánh dấu UI-01 hoàn thành.

## 2026-09-21 — UI-01: Giao diện Project List và Upload

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm giao diện React/TypeScript tối thiểu để tải MP4, hiển thị trạng thái, xử lý lỗi thân thiện và tải lại danh sách Project từ API persistence.
- **Tệp:** `frontend/src/App.tsx`, `frontend/src/index.css`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Frontend chạy qua Vite và hiển thị Project đã persistence sau reload; kiểm tra validation form; upload MP4 thật và upload bị từ chối đã được kiểm chứng qua endpoint backend; `npm run build` và `git diff --check` thành công; không có gọi Supabase trực tiếp trong frontend.
- **Còn lại:** Chưa thể hoàn tất upload thật bằng browser automation vì môi trường trình duyệt từ chối inject file cục bộ vào native file chooser; chưa đánh dấu UI-01 hoàn thành.

## 2026-09-21 — UI-01: Sửa lỗi reset form sau upload

- **Trạng thái:** Một phần
- **Thay đổi:** Xác định `event.currentTarget` trở thành `null` sau `await` và lưu tham chiếu form ổn định trước boundary bất đồng bộ để reset an toàn sau upload thành công.
- **Tệp:** `frontend/src/App.tsx`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Kiểm tra submit flow không còn đọc `event.currentTarget` sau `await`; `npm run build` và `git diff --check` thành công.
- **Còn lại:** Cần manual browser verification cho toàn bộ UI-01; chưa đánh dấu UI-01 hoàn thành.

## 2026-09-22 — UI-01: Hoàn tất kiểm chứng giao diện Project

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Đánh dấu UI-01 hoàn tất sau khi developer xác nhận toàn bộ luồng upload và persistence bằng browser thật.
- **Tệp:** `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Developer chọn MP4 hợp lệ qua native file picker; upload qua React thành công; form reset không lỗi; Project mới xuất hiện ngay không cần refresh thủ công; refresh trình duyệt vẫn tải Project từ backend persistence; lỗi reset cũ không còn. `npm run build` và `git diff --check` thành công.
- **Còn lại:** Không.

## 2026-10-04 — JOB-01: API enqueue và worker tuần tự

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm endpoint tạo Job `queued` trả về ID ngay và worker Python riêng claim tuần tự qua PostgreSQL; không đánh dấu thành công khi chưa có pipeline.
- **Tệp:** `.env.example`, `TASKS.md`, `backend/app/api/projects.py`, `backend/app/core/config.py`, `backend/app/schemas/__init__.py`, `backend/app/schemas/jobs.py`, `backend/app/workers/__init__.py`, `backend/app/workers/job_worker.py`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** `compileall`, `pip check` và import/OpenAPI route thành công. Kết nối SQLAlchemy và truy vấn schema Supabase không thành công: dự án được báo inactive; runtime trả lỗi ENOTFOUND tenant/user và MCP hết thời gian chờ.
- **Còn lại:** Chưa xác minh enqueue/persistence và claim bằng worker riêng trên Supabase thật; JOB-01 chưa hoàn tất.

## 2026-10-04 — JOB-01: Hoàn tất kiểm chứng Supabase

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Xác minh luồng enqueue qua FastAPI và claim bằng tiến trình worker riêng; đánh dấu JOB-01 hoàn tất. Job đã claim giữ trạng thái `running`/`claimed` do pipeline xử lý chưa thuộc phạm vi.
- **Tệp:** `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** SQLAlchemy kết nối Supabase thành công; endpoint thật trả HTTP 202 và Job `queued` trong 2.5 giây; worker riêng claim Job đầu thành `running`/`claimed`, Job thứ hai vẫn `queued`; PID API/worker khác nhau; MCP và engine/session mới xác nhận dữ liệu; đã xóa Project cùng hai Job kiểm chứng. `compileall`, `pip check`, unittest discovery (0 bài test), `git diff --check` và kiểm tra ignore/secret đều đạt.
- **Còn lại:** Không còn việc thuộc JOB-01; Job chạy được giữ `running` tới khi có pipeline thật ở nhiệm vụ sau.

## 2026-10-04 — JOB-02: Trạng thái bền vững và khôi phục Job

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Thêm API đọc trạng thái và retry bằng Job mới; thêm chuyển trạng thái succeeded/failed, làm sạch lỗi an toàn, và đánh dấu Job đang chạy bị bỏ dở là interrupted khi worker khởi động lại. Dùng lại các cột timestamp hiện có, không đổi schema.
- **Tệp:** `backend/app/api/jobs.py`, `backend/app/api/projects.py`, `backend/app/main.py`, `backend/app/schemas/__init__.py`, `backend/app/schemas/jobs.py`, `backend/app/workers/job_worker.py`, `docs/ARCHITECTURE.md`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Trên Supabase thật, API tạo và đọc Job `queued`; worker riêng ghi `running`/`claimed` và `started_at`; sau khi dừng worker, tiến trình mới ghi `interrupted`, stage, lý do an toàn và `completed_at`. Retry tạo ID mới, giữ nguyên Job gốc; retry ở trạng thái queued/running bị từ chối HTTP 409. Helper failure lưu lỗi đã giới hạn và loại đường dẫn; Job tiếp theo chỉ được claim sau khi Job trước chuyển failed. SQLAlchemy session mới và MCP xác nhận dữ liệu; đã xóa Project cùng ba Job kiểm chứng. `compileall`, `pip check`, `git diff --check`, kiểm tra secret/ignore đạt; unittest discovery không tìm thấy test.
- **Còn lại:** Không trong JOB-02; chỉ pipeline thật mới được chuyển Job sang succeeded.

## 2026-10-04 — UI-02: Hiển thị trạng thái Job thật

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Thêm API liệt kê Job theo Project mới nhất trước; React tạo Job, khôi phục trạng thái từ backend sau khi tải lại, hiển thị stage/lỗi an toàn/mốc thời gian và chỉ thăm dò khi Job đang queued hoặc running.
- **Tệp:** `backend/app/api/projects.py`, `frontend/src/App.tsx`, `frontend/src/index.css`, `docs/ARCHITECTURE.md`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Trên Supabase thật, thao tác UI tạo Job `queued` khi worker dừng; refresh khôi phục cùng Job; worker Python riêng cập nhật UI sang `running`/`claimed`; khởi động lại worker cập nhật UI sang `interrupted` với lý do an toàn đã lưu. Đã xóa Project/Jobs kiểm chứng. `npm run build`, `compileall`, `pip check`, `git diff --check`, kiểm tra secret/ignore đạt; không có test phù hợp trong thư mục tests.
- **Còn lại:** Không trong UI-02; Job vẫn không hoàn tất cho tới khi có pipeline xử lý thật.

## 2026-10-04 — UI-02: Xác nhận thủ công trên trình duyệt

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Bổ sung xác nhận nghiệm thu thủ công cho luồng UI-02; giữ nguyên implementation và dữ liệu persistence hiện có.
- **Tệp:** `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Developer xác nhận UI tạo Job thật ở trạng thái `queued`, tải lại trang khôi phục cùng Job từ backend, worker riêng cập nhật UI sang `running`/`claimed`, và khởi động lại worker cập nhật UI sang `interrupted`. Không có phần trăm tiến độ giả. `npm run build` và `git diff --check` thành công.
- **Còn lại:** Không trong UI-02.

## 2026-10-06 — ASR-01: Chép lời Whisper có dấu thời gian

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Tích hợp faster-whisper `small` vào worker tuần tự; xác thực đường dẫn video do máy chủ quản lý và lưu Segment theo thứ tự trong giao dịch. Chạy lại chỉ thay thế transcript chưa chỉnh sửa; Job tổng hợp vẫn `running` cho tới khi có dịch thuật.
- **Tệp:** `.gitignore`, `backend/app/services/asr.py`, `backend/app/workers/job_worker.py`, `backend/requirements.txt`, `tests/unit/test_asr.py`, `docs/ARCHITECTURE.md`, `docs/ENVIRONMENT.md`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Faster-whisper xử lý video lời nói và video im lặng đã tải lên qua FastAPI; SQLAlchemy lưu và session mới xác nhận Segment có ID duy nhất, văn bản nguồn, thứ tự và mốc thời gian hợp lệ, `translated_text` rỗng/null. Chạy lại không nhân đôi dữ liệu; video im lặng cho 0 Segment và stage `no_speech`; transcript có dữ liệu chỉnh sửa bị từ chối ghi đè và Job chuyển `failed` an toàn. CUDA đã được thử nhưng thiếu `cublas64_12.dll`; suy luận thật bằng CPU `int8` thành công. Đã dọn Project, Job, Segment, video và media kiểm thử. `compileall`, `pip check`, 3 unit test, `git diff --check`, kiểm tra secret/ignore và model weights đều đạt.
- **Còn lại:** GPU chưa được xác minh. Supabase MCP báo RLS đang tắt trên các bảng public hiện có; cấu hình này không đổi trong ASR-01 và cần chính sách truy cập riêng trước khi bật RLS.

## 2026-10-06 — TRANS-01: Dịch Segment bằng Gemini

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Thêm cấu hình Gemini và dịch theo lô có schema; xác thực đầy đủ ID và nội dung trước khi cập nhật `translated_text` trong một giao dịch. Worker chỉ hoàn tất Job sau khi dịch xong; đầu vào không có lời nói bỏ qua Gemini.
- **Tệp:** `.env.example`, `backend/app/core/config.py`, `backend/app/services/translation.py`, `backend/app/workers/job_worker.py`, `backend/requirements.txt`, `tests/unit/test_translation.py`, `docs/ARCHITECTURE.md`, `docs/ENVIRONMENT.md`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Video lời nói tải lên qua FastAPI được worker riêng xử lý bằng faster-whisper và Gemini thật; bốn Segment dịch trong một lô. FastAPI trả Job `succeeded`/`translation_ready`; SQLAlchemy session mới và Supabase MCP xác nhận bản dịch cùng ID, văn bản nguồn, thứ tự và dấu thời gian được giữ nguyên. Video im lặng hoàn tất `succeeded`/`no_speech`, không có Segment hay lời gọi Gemini. Chín unit test đạt, gồm các phản hồi thiếu/trùng/ID lạ/sai cấu trúc/rỗng, bảo vệ bản dịch hiện có và bảo đảm lô lỗi không ghi một phần. Đã xác minh chuyển lỗi và khôi phục `interrupted`; dọn các Project, Job, Segment và media kiểm thử. `compileall`, `pip check`, `git diff --check`, kiểm tra secret/ignore đạt.
- **Còn lại:** Không trong TRANS-01; chính sách retry/quota vẫn thuộc TRANS-02.

## 2026-10-15 — TRANS-02: Retry Gemini có giới hạn và xử lý quota

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Phân loại lỗi quota, lỗi tạm thời và lỗi cấu hình; chỉ retry lỗi mạng/5xx hoặc phản hồi cấu trúc không hợp lệ tối đa một lần với cùng lô dữ liệu và thời gian chờ ngắn. Lỗi quota dừng ngay; không đổi model, chia lô do quota hay dùng văn bản nguồn thay bản dịch.
- **Tệp:** `backend/app/services/translation.py`, `tests/unit/test_translation.py`, `docs/ARCHITECTURE.md`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** 14 unit test đạt, gồm các lỗi quota/429, timeout, xác thực, phản hồi sai/thiếu và bảo toàn Segment khi dịch thất bại. Backoff được mock để kiểm thử không phải chờ thật. `compileall`, `pip check`, `git diff --check`, kiểm tra secret/runtime/ignore đạt; không gửi yêu cầu Gemini thật.
- **Còn lại:** Không trong TRANS-02.

## 2026-10-25 — EDIT-01: Trình xem video và transcript song ngữ

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm API chỉ đọc cho Segment theo thứ tự và video nguồn theo đường dẫn UUID chuẩn; React hiển thị video, transcript song ngữ, mốc thời gian, seek và tô sáng Segment đang phát. Không thay đổi schema hoặc dữ liệu Project.
- **Tệp:** `backend/app/api/projects.py`, `backend/app/schemas/projects.py`, `backend/app/schemas/__init__.py`, `frontend/src/App.tsx`, `frontend/src/index.css`, `tests/unit/test_project_viewer_api.py`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** 18 unit test đạt; gồm sắp thứ tự Segment, Project không tồn tại, chặn đường dẫn video không chuẩn và HTTP Range. `npm run build`, `compileall`, `pip check`, `git diff --check`, kiểm tra secret/runtime/ignore đều đạt. Kiểm tra SQLAlchemy tới Supabase thất bại do cấu hình local trỏ tới tenant/user không hợp lệ; chưa xác minh video/transcript thật trên trình duyệt.
- **Còn lại:** EDIT-01 vẫn chờ xác minh thủ công với Project thật: mở Project, phát video, seek Segment, kiểm tra tô sáng và tải lại trang để xác nhận dữ liệu được đọc lại từ backend.

## 2026-10-25 — EDIT-01: Đóng nghiệm thu thủ công

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Ghi nhận xác nhận thủ công của nhà phát triển cho video, transcript Hoa–Việt, seek theo Segment, tô sáng theo timeline, khớp timestamp và dữ liệu còn nguyên sau khi tải lại trang. Không thay đổi phần triển khai EDIT-01.
- **Tệp:** `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Nhà phát triển xác nhận sáu hành vi nghiệm thu trên trình duyệt; không ghi nhận kiểm chứng nào khác.
- **Còn lại:** Không trong EDIT-01.

## 2026-10-25 — EDIT-02: Chỉnh sửa bản dịch tiếng Việt

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm PATCH chỉ cập nhật `translated_text` trong giao dịch, kiểm tra Project/Segment và Job hiện hành; thêm giao diện chỉnh sửa có Lưu/Hủy, trạng thái lưu và giữ nội dung nháp nếu lỗi. Không thêm cột hay migration.
- **Tệp:** `backend/app/api/projects.py`, `backend/app/schemas/projects.py`, `backend/app/schemas/__init__.py`, `frontend/src/App.tsx`, `frontend/src/index.css`, `tests/unit/test_project_viewer_api.py`, `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** 22 backend unit test đạt, gồm lưu/đọc lại bản dịch, payload lỗi/rỗng/quá dài, Project/Segment không hợp lệ, Job đang chạy, tính nguyên vẹn Segment và chặn worker khỏi ghi đè bản dịch đã sửa. `npm run build`, `compileall`, `pip check` và `git diff --check` đạt. Chưa kiểm tra thao tác editor thực tế trên trình duyệt.
- **Còn lại:** EDIT-02 chờ kiểm thử trình duyệt với Project thật: Lưu, Hủy, lỗi lưu và tải lại để xác nhận dữ liệu lưu bền. API đang theo quy ước single-user hiện có; ứng dụng chưa có authentication.

## 2026-10-25 — EDIT-02: Hoàn tất nghiệm thu chỉnh sửa bản dịch

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Đóng EDIT-02 sau khi người dùng xác nhận thao tác sửa/lưu bản dịch tiếng Việt, dữ liệu giữ nguyên sau F5, Hủy bỏ thay đổi chưa lưu và từ chối nội dung rỗng/chỉ có khoảng trắng.
- **Tệp:** `TASKS.md`, `docs/CHANGELOG.md`
- **Kiểm chứng:** Người dùng xác nhận trên Project thật rằng video vẫn phát, bấm Segment seek đúng timestamp, timestamp hiển thị chính xác và Segment hiện tại được tô sáng tự động. 22 unit test backend, frontend production build, `compileall`, `pip check` và `git diff --check` đã đạt trong lần kiểm chứng trước. Kịch bản ngắt kết nối backend/lưu thất bại không được kiểm thử thủ công.
- **Còn lại:** Không còn tiêu chí EDIT-02 đang chờ; kịch bản lỗi lưu khi backend mất kết nối chưa được kiểm chứng.

## 2026-10-25 — EDIT-03: Kiểm tra transcript trước TTS

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm API kiểm tra chỉ đọc theo Project và UI hiển thị readiness, lỗi chặn, cảnh báo thời gian cùng liên kết tới Segment liên quan. Kết quả cũ bị xóa sau khi lưu bản dịch; không tạo audio/video hoặc thay đổi timeline nguồn.
- **Tệp:** `backend/app/core/config.py`, `backend/app/api/projects.py`, `backend/app/schemas/projects.py`, `backend/app/schemas/readiness.py`, `backend/app/schemas/__init__.py`, `backend/app/services/tts_readiness.py`, `frontend/src/App.tsx`, `frontend/src/index.css`, `tests/unit/test_tts_readiness.py`, `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** 33 unit test backend đạt, gồm Project/Job/Segment, lỗi bản dịch và timestamp, warning WPS/overlap, thứ tự issue và xác nhận không ghi dữ liệu. `npm run build`, `compileall`, `pip check` đạt. Chưa thực hiện nghiệm thu thủ công trên trình duyệt.
- **Còn lại:** EDIT-03 chờ xác nhận UI readiness, phân loại lỗi/cảnh báo và điều hướng tới Segment trên trình duyệt thật. Ngưỡng cảnh báo là cửa sổ dưới 250 ms và trên 8 token cách trắng/giây; đây không phải phép đo thời lượng audio. TTS thích ứng và dynamic video stretching chưa được triển khai.

## 2026-10-25 — EDIT-03: Hoàn tất nghiệm thu readiness trên demo2

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Đóng EDIT-03 sau khi người dùng xác nhận readiness cho Project `demo2`, cập nhật kết quả sau khi lưu bản dịch và giữ nguyên video/transcript viewer.
- **Tệp:** `TASKS.md`, `docs/CHANGELOG.md`
- **Kiểm chứng:** Người dùng xác nhận trên trình duyệt thật: `demo2` hiển thị “Ready for future TTS” với 11 Segment, 0 lỗi chặn và 0 cảnh báo; sau khi sửa/lưu bản dịch, kết quả readiness cũ bị vô hiệu hóa và lần kiểm tra tiếp theo hiển thị kết quả mới; video preview và transcript vẫn hoạt động. 33 backend unit test, frontend build, `compileall`, `pip check` là kết quả của lần kiểm chứng tự động trước. Lỗi/cảnh báo và điều hướng Segment không được kiểm thử thủ công trên trình duyệt.
- **Còn lại:** Không còn tiêu chí EDIT-03 đang chờ; TTS đo thời lượng, điều chỉnh tốc độ và dynamic video stretching chưa thuộc EDIT-03.

## 2026-10-25 — TTS-01: Tạo giọng tiếng Việt theo Segment

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm Job `tts` có kiểm tra lại readiness, worker Edge-TTS theo Segment, tốc độ thích ứng theo WPS, lưu Artifact theo Project/Job/Segment, đo duration bằng FFprobe và API phát audio có kiểm tra provenance. Thêm migration PostgreSQL chỉ bổ sung metadata nullable; không đổi timestamp nguồn hay bản dịch.
- **Tệp:** `backend/app/services/tts.py`, `backend/app/api/projects.py`, `backend/app/workers/job_worker.py`, `backend/app/models/entities.py`, `backend/app/core/config.py`, `backend/app/schemas/tts.py`, `backend/app/schemas/__init__.py`, `backend/app/services/tts_readiness.py`, `backend/app/api/jobs.py`, `backend/requirements.txt`, `backend/migrations/20261025_add_tts_artifact_metadata.sql`, `.env.example`, `frontend/src/App.tsx`, `frontend/src/index.css`, `tests/unit/test_tts.py`, `tests/unit/test_tts_pipeline.py`, `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/ENVIRONMENT.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Edge-TTS `7.3.1` tạo mẫu tiếng Việt thật bằng `vi-VN-HoaiMyNeural`; FFprobe đo 3.480 ms. Migration additive đã áp dụng và Supabase MCP cùng kết nối SQLAlchemy xác nhận các cột Artifact mới. 44 backend unit test, frontend production build, `compileall`, `pip check` và `git diff --check` đạt. Chưa chạy worker với Project thật hoặc kiểm tra phát audio trên trình duyệt.
- **Còn lại:** Chờ người dùng kiểm tra readiness, tạo Job TTS trên Project có bản dịch thật, đợi worker tới `succeeded`/`tts_ready`, nghe audio nhiều Segment và xác nhận thời lượng hiển thị sau khi tải lại trang. TTS-01 vẫn chưa hoàn tất. Supabase MCP cũng báo RLS đang tắt trên các bảng public hiện có; cấu hình này không được thay đổi trong task.

## 2026-10-25 — TTS-01: Hoàn tất nghiệm thu giọng tiếng Việt

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Đóng TTS-01 sau khi người dùng xác nhận tạo và phát audio Edge-TTS riêng cho từng Segment trên Project `demo2`. TTS-01 chỉ hoàn tất phát sinh giọng nói theo Segment; đồng bộ audio/video, Dynamic Video Time-Stretching và render vẫn thuộc các task sau.
- **Tệp:** `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Người dùng xác nhận Job đạt `succeeded`/`tts_ready`; readiness có 11 Segment, 0 lỗi và 0 cảnh báo; audio tiếng Việt phát được, không bị cắt, hiển thị tốc độ thích ứng `+20%` và thời lượng đo thực tế; audio/thời lượng còn sau F5; timestamp nguồn và bản dịch được giữ nguyên. 44 backend unit test, frontend production build, `compileall`, `pip check` và `git diff --check` là kết quả tự động trước đó do người dùng cung cấp; không chạy lại trong lần đóng task này.
- **Còn lại:** Không còn tiêu chí TTS-01 đang chờ. Đồng bộ audio/video, Dynamic Video Time-Stretching và render MP4/SRT chưa thuộc TTS-01.

## 2026-10-25 — TTS-02: Phân tích thời lượng và lập kế hoạch timeline

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm API chỉ đọc để kiểm tra Artifact TTS hiện hành và lập timeline đầu ra theo duration đo được, khoảng lặng nguồn, các lần kéo giãn video tối đa 1,4×, dịch chuyển tích lũy và xung đột cần xử lý. Viewer hiển thị kế hoạch và liên kết tới Segment liên quan; không thay đổi timestamp hoặc tạo video.
- **Tệp:** `backend/app/api/projects.py`, `backend/app/schemas/timeline.py`, `backend/app/schemas/__init__.py`, `backend/app/services/tts_timeline.py`, `frontend/src/App.tsx`, `frontend/src/index.css`, `tests/unit/test_tts_timeline.py`, `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/ENVIRONMENT.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** 57 backend unit test, frontend production build, `compileall`, `pip check` và `git diff --check` đạt. Gọi endpoint thực với Project `demo2` và dữ liệu Supabase hiện có trả 11 Segment, video nguồn 21.339 ms, timeline dự kiến 25.211 ms, tăng 3.872 ms với 9 thao tác kéo giãn; có 8 lỗi chặn do giới hạn 1,4× nên kế hoạch chưa thể render. API chỉ đọc, không ghi dữ liệu.
- **Còn lại:** Chưa nghiệm thu thủ công trên trình duyệt. Cần mở Project `demo2`, chạy phân tích timeline sau khi TTS hoàn tất, kiểm tra thời lượng nguồn/kế hoạch, thao tác và lỗi chặn cùng điều hướng Segment; tải lại trang và chạy phân tích lại. TTS-02 chưa hoàn tất. Chưa triển khai FFmpeg/render, kéo giãn audio, trộn audio hoặc tạo SRT.

## 2026-10-25 — TTS-02: Hoàn tất nghiệm thu timeline trên demo2

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Đóng TTS-02 sau khi người dùng xác nhận phân tích timeline, hiển thị thao tác kéo giãn và điều hướng tới Segment có xung đột trên trình duyệt thật.
- **Tệp:** `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Người dùng xác nhận trên Project `demo2`: thời lượng video nguồn 21.339 ms, timeline dự kiến 25.211 ms, tăng 3.872 ms; 9/11 Segment cần kéo giãn và 8 xung đột vượt giới hạn 1,4× được hiển thị. Chọn xung đột điều hướng tới Segment liên quan; tải lại và phân tích lại cho kết quả nhất quán. Video, transcript, bản dịch và audio TTS hiện có vẫn hoạt động. 57 backend unit test, frontend build, `compileall`, `pip check` và `git diff --check` là kết quả tự động trước đó; không chạy lại trong lần đóng task này.
- **Còn lại:** TTS-02 hoàn tất. Tám xung đột trên `demo2` là kết quả phân tích hợp lệ, nhưng kế hoạch hiện không thể render cho tới khi được giải quyết. Thực thi kéo giãn video, trộn audio, đồng bộ phụ đề và render video vẫn thuộc công việc sau; không đánh dấu Project sẵn sàng render.

## 2026-10-25 — TTS-03: Tối ưu thời lượng TTS theo timeline

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm Job `tts_optimize` chạy tuần tự trong worker riêng, thử lại tổng hợp Edge-TTS với các mức tốc độ hữu hạn tới +35%, đo thời lượng thực tế và phân tích lại các xung đột sau từng vòng. Chỉ Artifact được xác minh mới được thay thế nguyên tử; bản dịch, Segment và timestamp nguồn được giữ nguyên. API trả Job và kết quả tối ưu có thời lượng/rate đo được cùng xung đột còn lại; chưa giải quyết được xung đột thì Project vẫn chưa sẵn sàng render. Thêm migration PostgreSQL chỉ mở rộng allow-list rate cần thiết; không đổi các hàng Artifact hiện có.
- **Tệp:** `.env.example`, `TASKS.md`, `backend/app/api/jobs.py`, `backend/app/api/projects.py`, `backend/app/core/config.py`, `backend/app/models/entities.py`, `backend/app/schemas/__init__.py`, `backend/app/schemas/tts_optimization.py`, `backend/app/services/tts.py`, `backend/app/services/tts_optimization.py`, `backend/app/services/tts_timeline.py`, `backend/app/workers/job_worker.py`, `frontend/src/App.tsx`, `frontend/src/index.css`, `supabase/migrations/20261024193822_add_tts_optimization_rate_tiers.sql`, `tests/unit/test_tts_optimization.py`, `docs/ARCHITECTURE.md`, `docs/ENVIRONMENT.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** 13 kiểm thử tối ưu hóa tập trung và toàn bộ 70 backend unit test đạt; frontend production build, `compileall`, `pip check` và `git diff --check` đạt. Migration áp dụng thành công lên Supabase và định nghĩa constraint được xác minh qua Supabase MCP cùng SQLAlchemy. Kiểm tra trạng thái secret/ignore xác nhận `.env`, virtualenv, runtime media và frontend build được ignore; migration và mã nguồn không chứa bí mật.
- **Còn lại:** Chưa chạy luồng tối ưu với Edge-TTS thật trên Project thật và chưa nghiệm thu trình duyệt; TTS-03 vẫn một phần. Cần dùng Project có các xung đột TTS hiện hành, enqueue tối ưu hóa, xác nhận worker chạy riêng và Job/result được khôi phục sau refresh; kiểm tra thời lượng/rate mới, Artifact cũ trong khi Job chạy, các xung đột còn lại và thông báo khi không renderable. Không triển khai kéo giãn video, trộn audio, phụ đề hay render. Supabase MCP tiếp tục báo RLS đang tắt trên các bảng public hiện có; không thay đổi cấu hình này trong task.

## 2026-10-25 — TTS-03: Hoàn tất nghiệm thu tối ưu thời lượng TTS

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Đóng TTS-03 sau khi người dùng nghiệm thu luồng tối ưu bằng Edge-TTS thật trên Project `demo2`. Bảy Segment có audio được cải thiện; 2/8 xung đột thời lượng được giải quyết. Kế hoạch giảm từ 25.211 ms (tăng 3.872 ms) xuống 25.011 ms (tăng 3.672 ms).
- **Tệp:** `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Người dùng xác nhận đã nghe và chấp nhận audio tiếng Việt tối ưu; sau khi tải lại, kết quả tối ưu, metadata audio và Job vẫn còn. Bản dịch và timestamp nguồn không đổi; video preview, click-to-seek và chỉnh sửa hiện có vẫn hoạt động. Người dùng cung cấp kết quả tự động trước đó: 13 kiểm thử tối ưu hóa, 70 backend unit test, frontend build, `compileall`, `pip check`, `git diff --check` đều đạt; không chạy lại các kiểm tra này trong lần đóng task.
- **Còn lại:** Sáu xung đột còn lại có phần vượt lần lượt 64, 536, 216, 232, 232 và 920 ms; `demo2` chưa renderable. Giải quyết xung đột timeline và render video vẫn là công việc tương lai, không thuộc nghiệm thu TTS-03.

## 2026-10-25 — TIMELINE-01: Hướng dẫn xử lý xung đột thời lượng

- **Trạng thái:** Một phần
- **Thay đổi:** Mở rộng viewer để liệt kê xung đột theo Segment ID ổn định, bản dịch hiện tại, thời lượng nguồn, duration TTS đã đo, speaking rate và phần vượt còn lại; nút dẫn tới editor EDIT-02. Hướng dẫn rút gọn bản dịch do người dùng quyết định. Sau khi lưu, timeline/optimization kết quả cũ bị xóa khỏi UI, endpoint nhận diện kết quả optimization stale sau refresh, và audio cũ được đánh dấu stale theo fingerprint. Tạo lại TTS dùng Job toàn Project hiện có; audio cũ giữ nguyên tới khi bộ audio mới được kiểm chứng và publish transactionally. UI thông báo rate tối ưu TTS-03 sẽ bị thay bằng adaptive rate mặc định. Tình trạng timeline-ready tiếp tục dựa trên planner TTS-02; không có video nào được render.
- **Tệp:** `TASKS.md`, `docs/ARCHITECTURE.md`, `frontend/src/App.tsx`, `frontend/src/index.css`, `tests/unit/test_tts_pipeline.py`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** 72 backend unit test đạt, gồm kiểm tra translation mới làm Artifact cũ stale và toàn bộ TTS regeneration publish an toàn sau khi audio mới được tạo; `npm run build`, `compileall`, `pip check`, `git diff --check` và kiểm tra secret/ignore đạt. Chưa thực hiện nghiệm thu trình duyệt hoặc gọi Edge-TTS thật trong task này.
- **Còn lại:** TIMELINE-01 vẫn một phần, chờ người dùng nghiệm thu thủ công trên `demo2`: xem chi tiết sáu conflict, mở Segment và sửa bản dịch, lưu, xác nhận audio cũ stale, chạy full TTS Job và kiểm tra audio mới/rate adaptive; xác nhận rate TTS-03 cần tối ưu lại nếu muốn, chạy lại phân tích timeline, kiểm tra xung đột mới và chỉ thấy timeline-ready khi planner trả về 0 blockers. Sáu conflict hiện tại vẫn ngăn render cho tới khi được giải quyết. Không triển khai render, mixing hoặc rewrite tự động.

## 2026-10-25 — TIMELINE-01: Điều tra duration TTS của Segment 10

- **Trạng thái:** Một phần
- **Thay đổi:** Điều tra luồng save translation → TTS Job → Edge-TTS/FFprobe → Artifact → timeline API. Không tìm thấy lỗi production; thêm kiểm thử hồi quy nối PATCH translation, từ chối Artifact cũ, enqueue/chạy full TTS regeneration, chọn Artifact mới và tính lại timeline.
- **Tệp:** `tests/unit/test_tts_pipeline.py`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Trên `demo2`, SQLAlchemy và Supabase MCP cùng xác nhận Segment 10 hiện có bản dịch `Đâu đến nỗi` và Artifact mới nhất đúng `tts` Job, `succeeded`/`tts_ready`, `is_current=true`, rate 20%, duration 1.872 ms. Fingerprint của Artifact hiện hành khớp bản dịch đã lưu; fingerprint của Artifact cũ khớp bản dịch ban đầu. File MP3 hiện tại và file cũ có hash khác nhau; FFprobe đo cả hai là 1.872 ms, 78 frame, 24 kHz/48 kbps. Endpoint `/tts-audio` trả Artifact hiện hành; timeline API chọn duration 1.872 ms, 920 ms excess và sáu blocker. Pacing heuristic cho cả bản cũ (5 token/0,68 s) và mới (3 token/0,68 s) vẫn chọn +20%. `silencedetect` ở ngưỡng -50 dB ghi nhận khoảng 1,001 s vùng im lặng cuối ở file mới và 0,822 s ở file cũ; đây là quan sát mức tín hiệu, không phải sửa duration. 73 backend unit test, frontend build, `compileall`, `pip check` và `git diff --check` đạt.
- **Còn lại:** Chưa có lỗi cache, metadata cũ, Artifact chọn sai hay duration bị làm tròn cố định được xác nhận; duration 1.872 ms phản ánh media MP3 mới. Chưa nghiệm thu lại trong trình duyệt. Cần quyết định riêng liệu khoảng lặng từ Edge-TTS có nên được trim/đo riêng ở tác vụ sau; lần điều tra này không thay đổi media hoặc dữ liệu `demo2`. TIMELINE-01 vẫn một phần.

## 2026-10-25 — UI-03: Thiết kế lại Project Viewer đáp ứng màn hình

- **Trạng thái:** Một phần
- **Thay đổi:** Mở rộng viewer theo ba vùng video, transcript/chỉnh sửa và TTS/timeline trên màn hình rộng; chuyển sang hai cột ở laptop và bố cục xếp chồng trên màn hình nhỏ. Panel video và timeline sticky trên desktop rộng; danh sách Segment tự cuộn, điều hướng conflict cuộn trong danh sách và làm nổi bật Segment đích. Các mục Planning issues và stretch operations có thể thu gọn.
- **Tệp:** `TASKS.md`, `frontend/src/App.tsx`, `frontend/src/index.css`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** `npm run build` và `git diff --check` đạt. Chưa chạy nghiệm thu trình duyệt ở các kích thước desktop, laptop và mobile.
- **Còn lại:** UI-03 vẫn một phần cho tới khi kiểm tra thủ công video, transcript, chỉnh sửa/lưu, phát audio, conflict navigation, timeline controls và trạng thái sau khi tải lại ở các kích thước yêu cầu. TIMELINE-01 vẫn chờ nghiệm thu riêng.

## 2026-10-25 — TTS-04: Chuẩn hóa audio TTS theo khoảng lặng

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm dịch vụ FFmpeg phân tích tín hiệu audio đã giải mã và chỉ cắt khoảng lặng dư ở cuối file khi phát hiện đủ tin cậy; giữ 120 ms đệm biên, ngưỡng -60 dB, thời lượng im lặng tối thiểu 500 ms, không cắt khoảng dừng nội bộ. Giữ MP3 Edge-TTS gốc và sidecar provenance có phiên bản. TTS-01 và candidate TTS-03 dùng cùng chính sách; thêm Job `tts_normalize` để tái xử lý Artifact hiện có không gọi Edge-TTS, giữ nguyên voice/rate và publish Artifact generation nguyên tử. Timeline tiếp tục dùng duration FFprobe của media đã publish và là nguồn quyết định duy nhất về khả năng render.
- **Tệp:** `backend/app/services/audio_normalization.py`, `backend/app/services/tts.py`, `backend/app/services/tts_normalization.py`, `backend/app/api/projects.py`, `backend/app/api/jobs.py`, `backend/app/schemas/tts_normalization.py`, `backend/app/services/tts_optimization.py`, `backend/app/services/tts_timeline.py`, `backend/app/workers/job_worker.py`, `frontend/src/App.tsx`, `frontend/src/index.css`, `tests/unit/test_audio_normalization.py`, `tests/unit/test_tts.py`, `tests/unit/test_tts_optimization.py`, `tests/unit/test_tts_normalization.py`, `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** 87 backend unit test đạt, gồm kiểm thử FFmpeg/FFprobe trên audio tổng hợp và kiểm thử API/worker lưu trữ cục bộ có Edge-TTS bị mock; `npm run build`, `compileall`, `pip check` và `git diff --check` đạt. Không thay đổi schema hoặc dependency; không kết nối/ghi dữ liệu Supabase và không chạy normalize trên Project thật.
- **Còn lại:** TTS-04 vẫn một phần. Chưa thực hiện browser acceptance, phát/nghe audio đã normalize hoặc xác nhận kết quả timeline trên `demo2`; không tuyên bố thời lượng/conflict thực tế đã thay đổi. TIMELINE-01 giữ nguyên trạng thái.

## 2026-10-25 — TTS-04: Điều tra Job normalize thất bại trên demo2

- **Trạng thái:** Một phần
- **Thay đổi:** Xác nhận thông báo stale là lỗi so sánh thứ tự: worker snapshot Artifact theo thứ tự Segment nhưng truy vấn publish đọc theo UUID. Chuẩn hóa so sánh theo Artifact ID và thêm regression test với UUID đảo thứ tự; UI nói rõ timeline sau khi phân tích vẫn dựa trên generation đang publish nếu Job normalize thất bại.
- **Tệp:** `backend/app/services/tts_normalization.py`, `tests/unit/test_tts_normalization.py`, `frontend/src/App.tsx`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** SQLAlchemy và Supabase MCP xác nhận Job lỗi `87c450d9-2ee0-4984-8775-992bdd1d28c2` có 0 Artifact; generation hiện hành là Job TTS thành công `fad4ffec-6d88-4a2f-8385-f594e3bc0fd3` với đủ 11 Artifact hiện hành, rate +20%. Segment 10 hiện 1.045 ms từ file thực, sidecar ghi 1.872 ms nguồn và 827 ms đã bỏ; API timeline trả 23.730 ms với hai blocker: Segment 3 còn 246 ms và Segment 10 còn 93 ms. Chưa thay đổi dữ liệu hoặc media demo2. Kiểm thử regression về thứ tự UUID và kiểm thử normalization tập trung đạt.
- **Còn lại:** TTS-04 vẫn một phần; cần nghiệm thu browser và nghe audio sau thao tác người dùng. Job lỗi không phải generation hiện tại; generation hiện tại đến từ TTS Job thành công. TIMELINE-01 không đổi trạng thái.

## 2026-10-25 — TTS-04: Hoàn tất nghiệm thu chuẩn hóa audio

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Đóng TTS-04 sau khi người dùng nghiệm thu trên `demo2`. Job `tts_normalize` đạt `tts_normalization_complete`, xử lý 11 file; không file nào cần rút ngắn thêm và không có duration bổ sung được thu hồi vì audio hiện hành đã chuẩn hóa. Chạy lại giữ nguyên duration. Segment 10 duy trì 1.045 ms so với 1.872 ms ban đầu. Artifact generation hiện hành nhất quán; Job normalize lỗi trước đó không publish Artifact.
- **Tệp:** `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Người dùng xác nhận kết quả trong browser và chấp nhận audio đã chuẩn hóa. Timeline còn 2 blocker: Segment 3 vượt 246 ms, Segment 10 vượt 93 ms; planned output 23.730 ms, do đó không tuyên bố Project renderable. Bộ kiểm thử backend 88 test, frontend production build, `compileall`, `pip check` và `git diff --check` đã đạt trong lần xác minh trước.
- **Còn lại:** Xung đột timeline và render video vẫn là công việc riêng; TIMELINE-01 giữ trạng thái Một phần.

## 2026-10-25 — RENDER-01: Render MP4 theo timeline TTS

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm Job `render` chạy FFmpeg trong worker tuần tự; chỉ nhận timeline được planner hiện hành xác nhận, đồng bộ stretch video/audio, trộn TTS đã publish, kiểm tra H.264/AAC và thời lượng rồi publish Artifact MP4 theo giao dịch có kiểm tra provenance. Thêm API enqueue/metadata/preview/download, hỗ trợ HTTP Range, cùng viewer action và phát/tải output hiện hành. Không thêm schema hoặc dependency; encoding dùng libx264 CPU và gain audio nền mặc định 0,10.
- **Tệp:** `.env.example`, `TASKS.md`, `backend/app/api/jobs.py`, `backend/app/api/projects.py`, `backend/app/core/config.py`, `backend/app/schemas/__init__.py`, `backend/app/schemas/render.py`, `backend/app/services/video_render.py`, `backend/app/workers/job_worker.py`, `docs/ARCHITECTURE.md`, `docs/ENVIRONMENT.md`, `frontend/src/App.tsx`, `frontend/src/index.css`, `tests/unit/test_video_render.py`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** 16 kiểm thử render tổng hợp và toàn bộ 104 backend unit test đạt; kiểm thử dùng FFmpeg/FFprobe thật với media tổng hợp, SQLite, worker service/API, stale-input rollback, Artifact preservation, Range preview/download và reconnect DB. `npm run build`, `compileall`, `pip check`, `git diff --check` và kiểm tra ignore đạt; quét secret không tìm thấy credential thật, chỉ nhận diện giá trị mẫu trong `.env.example`; `.env` bị ignore và không được track. Không render hoặc sửa dữ liệu/media `demo2`.
- **Còn lại:** RENDER-01 vẫn một phần cho tới khi nghiệm thu browser trên Project thật: render, phát/nghe MP4, kiểm tra đồng bộ audio/video và Segment, tải xuống, tải lại trang để xác nhận Artifact. TIMELINE-01 vẫn một phần; không xác nhận demo2 renderable hoặc hoàn tất.

## 2026-10-25 — TIMELINE-01 / RENDER-01: Nghiệm thu timeline và render trên demo2

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Đóng TIMELINE-01 và RENDER-01 sau khi người dùng xác nhận nghiệm thu browser trên `demo2`. Timeline planner hiện hành báo Project sẵn sàng render với 0 blocker. Render Job đạt `render_complete`; MP4 preview và download xuất hiện trong Project Viewer. Planned duration và verified output duration đều 23.681 ms; kế hoạch có 11 TTS Segment và 7 stretch operation.
- **Tệp:** `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Người dùng xác nhận browser acceptance thành công và các kết quả nêu trên. `git diff --check` đạt. Không chạy thêm test, không sửa dữ liệu `demo2`, không tái tạo audio/video. TTS-04 đã hoàn thành từ trước và giữ nguyên trạng thái.
- **Còn lại:** Không cho TIMELINE-01 và RENDER-01. Các kiểm tra thủ công được ghi nhận theo xác nhận của người dùng; không thực hiện thêm kiểm thử trong lần đóng task này.

## 2026-10-25 — AUDIO-01: Trộn audio theo timeline và ducking

- **Trạng thái:** Một phần
- **Thay đổi:** Thêm lựa chọn Fixed/Auto Ducking tại Project Viewer và lưu cấu hình đã kiểm tra vào Render Job. Worker dùng đúng timestamp đầu ra và duration normalized TTS từ timeline planner; ducking mặc định 0,35 nền / 0,08 khi thoại Việt, TTS 1,0, attack 80 ms, release 250 ms và nối khoảng lặng tối đa 350 ms. Envelope WAV mono 1 kHz theo Job được trộn bằng FFmpeg `amultiply`; limiter hiện có giữ trần 0,95. Sidecar và API render ghi/đọc lại đầy đủ cấu hình; generation cũ vẫn hợp lệ trong khi render thay thế chưa publish. Không tách giọng: ducking giảm toàn bộ audio gốc.
- **Tệp:** `.env.example`, `TASKS.md`, `backend/app/api/jobs.py`, `backend/app/api/projects.py`, `backend/app/models/entities.py`, `backend/app/schemas/jobs.py`, `backend/app/schemas/render.py`, `backend/app/services/audio_mixing.py`, `backend/app/services/video_render.py`, `docs/ARCHITECTURE.md`, `docs/ENVIRONMENT.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`, `frontend/src/App.tsx`, `frontend/src/index.css`, `supabase/migrations/20261025073602_audio_01_render_audio_settings.sql`, `tests/unit/test_audio_mixing.py`, `tests/unit/test_video_render.py`
- **Kiểm chứng:** Migration cộng thêm cột nullable `autodub_jobs.audio_settings` đã áp dụng trên Supabase `video-dubbing`; SQLAlchemy kết nối qua `DATABASE_URL` và truy vấn schema mới thành công, không sửa hàng, Project hoặc media. 115 backend unit test đạt, gồm FFmpeg/FFprobe thật trên media tổng hợp, mức RMS nền thấp hơn khi thoại đang chạy, duration đầu ra trong sai số planner, và giữ Artifact cũ sau lỗi render với cấu hình khác; frontend production build, Python `compileall`, `pip check`, `git diff --check` và kiểm tra schema Supabase đạt.
- **Còn lại:** AUDIO-01 vẫn một phần cho đến khi người dùng nghe và nghiệm thu render trên Project thật. Không render hoặc sửa media/dữ liệu `demo2`; không tuyên bố chất lượng nghe thực tế.

## 2026-10-25 — AUDIO-01: Hoàn tất nghiệm thu Auto Ducking trên demo2

- **Trạng thái:** Hoàn thành
- **Thay đổi:** Đóng AUDIO-01 sau khi người dùng xác nhận browser và nghe audio render trên `demo2` đạt yêu cầu với Auto Ducking: gain nền 0,35; gain âm thanh gốc khi thoại Việt 0,08; gain TTS Việt 1,0; attack 80 ms; release 250 ms; nối khoảng thoại ngắn 350 ms.
- **Tệp:** `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`
- **Kiểm chứng:** Người dùng xác nhận kết quả mix thực tế đạt yêu cầu. Các kiểm tra tự động trước đó được báo cáo đạt: 115 backend unit test, frontend production build, Python `compileall`, `pip check`, `git diff --check`; migration cấu hình render trên Supabase đã được áp dụng. Không chạy lại kiểm thử, không thay đổi dữ liệu `demo2` hoặc tạo lại media.
- **Còn lại:** Không cho AUDIO-01. Các task khác giữ nguyên trạng thái.
