# AutoDub — TASKS

> Checklist tiến độ. `[x]` = đã hoàn thành theo bằng chứng trước đây; `[ ]` = chưa hoàn tất/chưa nghiệm thu (kể cả đang làm). Chi tiết kiểm chứng và lỗi ghi ở `docs/CHANGELOG.md`, không ghi dài trong file này.
>
> **Ưu tiên hiện tại:** Hoàn thiện chất lượng **nhận diện lời → dịch → tạo giọng → đồng bộ → render video**. Chỉ hoàn thiện UI sau khi pipeline đạt yêu cầu.

## Task đang thực hiện

- [ ] **PIPE-00 — Chốt bộ video mẫu, tiêu chí đánh giá và trạng thái pipeline hiện tại.**

## Giai đoạn A — Hoàn thiện pipeline (ưu tiên cao nhất)

### A1. Nhận diện lời (ASR)

- [ ] `PIPE-01` — Kiểm tra độ chính xác lời và mốc thời gian; xử lý câu bị thiếu, lặp, im lặng và phân đoạn sai.
- [ ] `PIPE-01-QA` — Kiểm thử ASR với các video mẫu thực tế, lưu lỗi và kết quả đối chiếu.

### A2. Dịch lời thoại

- [ ] `PIPE-02` — Tối ưu dịch theo ngữ cảnh, tự nhiên khi đọc thành tiếng và đủ ý; không làm sai ID/timestamp.
- [ ] `TRANS-04` — So sánh bản dịch, sửa và xác nhận bản dịch an toàn theo revision.
- [ ] `QA-05` — Đối chiếu chất lượng dịch và độ dài câu bằng bộ mẫu có kết quả mong đợi.

### A3. Chuyển văn bản thành giọng nói (TTS)

- [ ] `PIPE-03` — Kiểm thử giọng đọc, phát âm, tốc độ, độ dài audio và các trường hợp TTS lỗi.
- [ ] `PIPE-03-QA` — Đảm bảo không mất chữ, cắt lời hoặc tái sử dụng audio sai revision.

### A4. Đồng bộ tiếng và hình (AV-Sync)

- [ ] `PIPE-04` — Hoàn thiện tối ưu đồng thời độ dài TTS và tốc độ video, giữ đủ nội dung lời.
- [ ] `PIPE-04-QA` — Kiểm tra câu chồng lấn, khoảng im lặng, độ lệch tiếng–hình và giới hạn kéo giãn video.
- [ ] `TIMELINE-02` — Chỉ nâng cấp thuật toán timeline nếu kiểm thử chứng minh còn hạn chế.

### A5. Render video đầu ra

- [ ] `PIPE-05` — Hoàn thiện render MP4, phối âm nền/ducking và xuất phụ đề SRT khi có yêu cầu.
- [ ] `PIPE-05-QA` — Kiểm tra thời lượng, âm lượng, mất tiếng, tiếng rè, đồng bộ, playback/seek và tải file.

### A6. Kiểm thử quy trình hoàn chỉnh

- [ ] `PIPE-06` — Chạy một lượt **ASR → Dịch → TTS → AV-Sync → Render** với video được phép sử dụng.
- [ ] `FLOW-01` — Nghiệm thu đầu ra thực tế sau khi các bước trên đạt chất lượng; không tính một render thô là nghiệm thu cuối.
- [ ] `QA-01` — Bổ sung unit/integration test cho dữ liệu, trạng thái Job và lỗi provider.
- [ ] `QA-02` — Kiểm thử video lỗi, không có lời, quota hết, TTS/FFmpeg thất bại.
- [ ] `QA-03` — Đo thời gian xử lý và tài nguyên trên máy chạy thực tế.
- [ ] `QA-04` — Kiểm tra bảo vệ secret, file tạm và phạm vi dọn dẹp.

## Giai đoạn B — UI/UX và bàn giao (chỉ sau PIPE-06)

- [ ] `UI-03` — Hoàn thiện giao diện workspace dịch/lồng tiếng và responsive.
- [ ] `TIMELINE-UX-01` — Hiển thị timeline cũ khi kết quả hiện tại hết hiệu lực; nghiệm thu trên trình duyệt.
- [ ] `DOC-01` — Cập nhật hướng dẫn, ảnh minh họa, giới hạn và bằng chứng demo.
- [ ] `DEMO-01` — Chuẩn bị và chạy lại kịch bản trình diễn hoàn chỉnh.
- [ ] `GIT-01` — Đối chiếu yêu cầu remote/commit/push; chỉ thực hiện khi được yêu cầu.

## Các task đã hoàn thành trước đây (rút gọn)

### Khởi tạo, backend và dữ liệu

- [x] `INIT-01` — Tài liệu khởi tạo.
- [x] `INIT-02` — Cấu trúc repository.
- [x] `INIT-03` — Chốt MVP và kiến trúc.
- [x] `INIT-04` — Khảo sát môi trường.
- [x] `ENV-00` — Dung lượng ổ dự án.
- [x] `ENV-01` — FastAPI cơ bản.
- [x] `ENV-02` — React/TypeScript/Vite cơ bản.
- [x] `ENV-03` — Dependencies và config mẫu.
- [x] `DATA-01` — Supabase metadata.
- [x] `UPLOAD-01` — Lưu video và Project.
- [x] `UPLOAD-02` — Kiểm tra đầu vào.
- [x] `UI-01` — Giao diện upload/danh sách Project.
- [x] `JOB-01` — Worker xử lý tuần tự.
- [x] `JOB-02` — Job state/recovery.
- [x] `UI-02` — Hiển thị trạng thái Job.

### ASR, dịch và chỉnh sửa

- [x] `ASR-01` — Whisper transcript có timestamp.
- [x] `LEGACY-01` — Đối chiếu mã tool desktop cũ.
- [x] `TRANS-01` — Dịch Segment bằng Gemini.
- [x] `TRANS-02` — Retry và phân loại lỗi dịch.
- [x] `TRANS-03` — Dịch Bulk-First theo ngữ cảnh.
- [x] `GEMINI-FIX` — Xử lý model/provider Gemini.
- [x] `EDIT-01` — Hiển thị transcript và bản dịch.
- [x] `EDIT-02` — Lưu sửa bản dịch.
- [x] `EDIT-03` — Kiểm tra bản dịch trước TTS.

### TTS, timeline và render bản thô

- [x] `TTS-01` — Tạo audio theo Segment.
- [x] `TTS-INCREMENTAL-01` — Tái sử dụng audio còn hợp lệ.
- [x] `TTS-02` — Timeline dựa trên duration đo được.
- [x] `TTS-03` — Thử các mức tốc độ TTS có giới hạn.
- [x] `TTS-04` — Chuẩn hóa khoảng lặng audio.
- [x] `AV-SYNC-02` — Joint plan và migration đã xác minh.
- [x] `AV-SYNC-03` — Thực thi kế hoạch FFmpeg với kiểm tra đồng bộ.
- [x] `TIMELINE-01` — Xử lý xung đột timeline qua chỉnh bản dịch.
- [x] `RENDER-01` — Render MP4 bản chức năng.
- [x] `AUDIO-01` — Phối tiếng gốc và giọng lồng tiếng.
- [x] `RESULT-01` — API preview/download Artifact đúng revision.

## Công việc định kỳ

- [ ] Cập nhật issue/task khi bắt đầu việc mới.
- [ ] Kiểm tra diff, test và ghi bằng chứng thật trước khi kết luận hoàn thành.
- [ ] Ghi thay đổi vào `docs/CHANGELOG.md` và `docs/AI_USAGE.md` khi phù hợp.
- [ ] Commit/push tiến độ khi người dùng yêu cầu.
- [ ] Lập báo cáo tuần từ `docs/weekly/TEMPLATE.md` khi cần.

## Backlog — Chưa đưa vào MVP

- [ ] Đăng nhập, phân quyền và nhiều người dùng.
- [ ] Thanh toán.
- [ ] Tải video qua link mạng xã hội và tự đăng bài.
- [ ] Voice cloning, lip-sync, OCR phụ đề và tách nhạc/giọng nâng cao.
- [ ] Xử lý hàng loạt/đồng thời, timeline editor nâng cao và public deployment.
