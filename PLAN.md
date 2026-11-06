# AutoDub — Kế hoạch phát triển tiếp theo

## 1. Mục tiêu hiện tại

Ưu tiên hoàn thiện **chất lượng xử lý video từ đầu vào đến đầu ra** trước khi thiết kế lại giao diện:

**Video → Nhận diện lời (ASR) → Dịch theo ngữ cảnh → Tạo giọng (TTS) → Đồng bộ tiếng–hình (AV-Sync) → Phối âm và render MP4/SRT.**

Backend, Supabase, worker, các API và luồng UI cơ bản đã có. Đây là **nền tảng chức năng**, chưa đồng nghĩa chất lượng lồng tiếng đã đạt yêu cầu. Không mở công việc polish UI khi chưa hoàn thành cổng nghiệm thu pipeline.

`TASKS.md` chỉ chứa checkbox tiến độ; bằng chứng, nguyên nhân lỗi và thay đổi kỹ thuật nằm trong test, tài liệu chuyên đề và `docs/CHANGELOG.md`.

## 2. Thứ tự thực hiện

| Thứ tự | Nhóm task | Mục tiêu / điều kiện chuyển bước |
| --- | --- | --- |
| 0 | `PIPE-00` | Chọn video mẫu được phép sử dụng, lưu đầu ra hiện tại, xác định lỗi ưu tiên và tiêu chí so sánh. |
| 1 | `PIPE-01` | Lời nguồn đủ và đúng, timestamp hợp lý, nhận biết khoảng im lặng và đoạn có lời. |
| 2 | `PIPE-02`, `TRANS-04`, `QA-05` | Dịch đủ ý, tự nhiên, nhất quán theo ngữ cảnh; chỉnh sửa và xác nhận không làm sai revision. |
| 3 | `PIPE-03` | TTS không bỏ chữ/cắt tiếng, giọng và phát âm ổn định, audio có thời lượng đo được. |
| 4 | `PIPE-04`, `TIMELINE-02` (nếu cần) | Tìm phương án đồng bộ bằng số liệu đo; không che lỗi bằng việc cắt lời hoặc tăng tốc quá mức. |
| 5 | `PIPE-05` | Render MP4 có hình/tiếng hợp lệ, nhạc nền không lấn thoại, SRT và tải/seek hoạt động. |
| 6 | `PIPE-06`, `FLOW-01`, `QA-01`–`QA-04` | Kiểm thử trọn pipeline trên media thật; đo kết quả, tái hiện lỗi và ghi giới hạn. |
| 7 | `UI-03`, `TIMELINE-UX-01`, `DOC-01`, `DEMO-01` | Hoàn thiện trải nghiệm, giao diện và tài liệu **sau** khi pipeline đạt chất lượng. |

Không làm lại các bước ASR/Gemini/TTS đã có chỉ để tạo một render mới; trước hết xác định phần nào chưa đạt và kiểm thử lại đúng bước đó. Tái sử dụng Artifact hợp lệ, bảo toàn revision và provenance.

## 3. Nguyên tắc xử lý theo giai đoạn

### ASR — Lời và thời gian

- Đối chiếu transcript với tiếng gốc; theo dõi câu thiếu, câu lặp, ngôn ngữ nhận sai, đoạn im lặng và timestamp lệch.
- Điều chỉnh phân đoạn dựa trên bằng chứng từ video mẫu; không chỉnh thuật toán hàng loạt khi chưa có trường hợp tái hiện.

### Dịch — Chất lượng và độ dài lời

- Giữ cách dịch **Bulk-First có ngữ cảnh**, xác thực đủ Segment ID và bảo toàn source transcript.
- Đánh giá đồng thời tính đúng nghĩa, tự nhiên khi đọc tiếng Việt và thời lượng câu so với cửa sổ thoại.
- Cho phép người dùng sửa và xác nhận; sửa bản dịch phải làm hết hiệu lực audio/render phụ thuộc đúng cách.

### TTS — Giọng đọc và độ dài thực tế

- Dùng duration **đo từ audio được tạo**, không suy đoán bằng số ký tự.
- Thử tốc độ có giới hạn; cắt khoảng lặng thừa thận trọng, không cắt mất âm cuối hoặc nội dung.
- Tái tạo từng audio sai/hết hiệu lực; không gọi provider lại khi Artifact còn dùng được.

### AV-Sync — Kế hoạch tối ưu chung

- Dựa trên candidate TTS và tốc độ video cho phép để giải quyết xung đột, ưu tiên giữ nguyên nội dung lời nói.
- Kiểm tra overlap, gap, sai lệch audio–video và tốc độ kéo giãn; nếu không có phương án hợp lệ thì báo xung đột rõ ràng.
- `TIMELINE-02` chỉ triển khai khi benchmark chứng minh planner hiện tại cần thay đổi.

### Render — File giao được

- Phối thoại TTS với âm gốc/nhạc nền bằng ducking và giới hạn âm lượng; tránh tiếng rè, méo hoặc clipping.
- Xuất MP4 (và SRT nếu hỗ trợ ở luồng yêu cầu); xác nhận duration, âm thanh, hình ảnh, seek và download thực tế.
- Gắn Artifact với đúng Project, Job, revision, plan và source; không công bố output lỗi như bản thành công.

## 4. Tiêu chí nghiệm thu pipeline

Hoàn tất `PIPE-06` và `FLOW-01` chỉ khi có **bằng chứng trên video thực được phép dùng**, gồm:

1. Transcript và bản dịch được đối chiếu thủ công ở các đoạn đại diện; không mất câu hoặc sai ý nghiêm trọng.
2. Từng câu lồng tiếng nghe trọn vẹn, phát âm chấp nhận được; không bị cắt ngang, mất âm hoặc chồng lên câu kế tiếp ngoài ý muốn.
3. Đồng bộ trên các đoạn đầu, giữa, cuối video; phương án kéo giãn/video speed nằm trong giới hạn hiện hành hoặc có cảnh báo xung đột.
4. MP4 xem và tua được; âm gốc/giọng mới phối hợp hợp lý; tải về và phát lại file đã tải thành công.
5. Kiểm tra đường lỗi/quota/interruption và xác nhận không xuất Artifact sai revision; ghi rõ thời gian chạy và giới hạn môi trường.

Một Job `render_complete`, unit test đạt hay Artifact MP4 đã lưu **chỉ chứng minh chức năng tương ứng chạy được**, không thay thế nghiệm thu chất lượng video.

## 5. Phạm vi chưa ưu tiên

- Cho phép UI tối thiểu để quan sát và kiểm tra các bước xử lý; **hoãn redesign/polish UI** cho tới sau cổng nghiệm thu pipeline.
- Không triển khai trong giai đoạn này: authentication đa người dùng, thanh toán, voice cloning, lip-sync, tách giọng/nhạc nâng cao, batch processing và public deployment.
- Không tự ý chạy lại provider tốn quota, sửa dữ liệu production, reset database hay commit/push; các thao tác này được quyết định riêng theo phạm vi công việc.

## 6. Cách làm việc với Codex

1. Mỗi lượt chọn một checkbox ưu tiên trong `TASKS.md`; đọc mã liên quan và các bài học của tool desktop cũ.
2. Nêu cách tái hiện vấn đề, triển khai phần nhỏ, chạy test phù hợp, kiểm tra tác động tới Artifact/revision.
3. Ghi ngắn gọn kết quả và phần chưa xác nhận vào changelog; chỉ đánh dấu `[x]` khi có bằng chứng phù hợp.
4. Khi `PIPE-06` và `FLOW-01` hoàn tất mới chuyển sang Giai đoạn B — UI/UX và bàn giao.
