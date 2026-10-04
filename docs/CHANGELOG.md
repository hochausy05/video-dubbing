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
