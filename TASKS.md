# Danh sách nhiệm vụ AutoDub

## Quy ước

- `[ ]`: chưa hoàn thành; chỉ chuyển sang `[x]` khi có kiểm chứng.
- Task đang thực hiện: ghi ID tại mục “Hiện tại”, không đánh dấu hoàn thành sớm.
- Lịch tuần là dự kiến theo PLAN.md, có thể điều chỉnh sau khi xác nhận lịch môn học.
- Chưa có chức năng ứng dụng được triển khai trong bộ khung ban đầu.

## Hiện tại

- Giai đoạn: khởi tạo tài liệu và cấu trúc thư mục.
- Task đang thực hiện: chưa bắt đầu nhiệm vụ code.
- Bước tiếp theo: INIT-03 và INIT-04; sau đó mới ENV-01/ENV-02.
- Kết nối GitHub: chưa thực hiện trong bộ khung này.

## Tuần 1 — Định hướng và môi trường

- [x] INIT-01 — Soạn README, kế hoạch, quy tắc, backlog và kiến trúc dự kiến. Kiểm chứng: file tồn tại, link nội bộ hợp lệ, trạng thái chưa triển khai được ghi rõ.
- [x] INIT-02 — Tạo các thư mục giữ chỗ và `.gitignore`. Kiểm chứng: cấu trúc đóng gói đầy đủ, chưa có mã ứng dụng hay dữ liệu runtime.
- [ ] INIT-03 — Xác nhận lịch học, tiêu chí chấm và phạm vi MVP. Hoàn thành khi các quyết định được cập nhật vào tài liệu.
- [ ] INIT-04 — Xác nhận máy phát triển/demo, khả năng CPU/GPU và môi trường worker. Hoàn thành khi có ghi chú môi trường cùng kết quả kiểm tra khả dụng.
- [ ] ENV-01 — Khởi tạo FastAPI tối thiểu. Hoàn thành khi API health chạy cục bộ và có test hoặc bước kiểm tra tái hiện.
- [ ] ENV-02 — Khởi tạo React/TypeScript/Vite. Hoàn thành khi trang chào và lệnh build chạy được.
- [ ] ENV-03 — Khai báo dependencies và cấu hình mẫu không chứa bí mật. Hoàn thành khi README có hướng dẫn cài đặt đã được thử.
- [ ] GIT-01 — Khởi tạo repository, cấu hình remote và push đầu tiên. Hoàn thành khi có commit thực tế trên GitHub; chỉ thực hiện khi được yêu cầu và có remote chính xác.

## Tuần 2 — Dự án, dữ liệu và upload

- [ ] DATA-01 — Tạo cấu trúc Project, Job, Segment và Artifact. Kiểm chứng dữ liệu còn sau khi restart ứng dụng.
- [ ] UPLOAD-01 — Nhận và lưu video theo ID server tạo. Kiểm chứng video hợp lệ; tên file lạ không thay đổi đường dẫn lưu.
- [ ] UPLOAD-02 — Kiểm tra định dạng, dung lượng và thời lượng. Kiểm chứng tệp sai định dạng, quá giới hạn và hỏng bị từ chối rõ ràng.
- [ ] UI-01 — Trang danh sách/tạo dự án kết nối API. Kiểm chứng upload và xem lại dự án sau khi refresh.

## Tuần 3 — Worker, nhận dạng và dịch

- [ ] JOB-01 — Tích hợp worker/hàng đợi đã kiểm chứng môi trường. Kiểm chứng request trả về job ID và xử lý diễn ra ở worker riêng.
- [ ] JOB-02 — Lưu trạng thái, giai đoạn, lỗi và chính sách job bị gián đoạn. Kiểm chứng tải lại trang không làm mất tiến độ; restart không để job mắc kẹt mà không có cách xử lý.
- [ ] ASR-01 — Nhận dạng lời thoại có timestamp bằng video mẫu ngắn. Kiểm chứng văn bản và mốc thời gian hợp lệ; video không có lời thoại được báo đúng.
- [ ] TRANS-01 — Dịch sang tiếng Việt, giữ ID và text nguồn. Kiểm chứng đoạn thiếu/sai cấu trúc không bị coi là bản dịch hoàn chỉnh.
- [ ] TRANS-02 — Xử lý lỗi dịch/quota với retry có giới hạn. Kiểm chứng bằng tình huống mô phỏng có ghi rõ là mock.
- [ ] UI-02 — Hiển thị trạng thái/giai đoạn từ backend. Kiểm chứng không dùng progress giả để biểu diễn tiến độ thật.

## Tuần 4 — Duyệt và chỉnh sửa

- [ ] EDIT-01 — Trang video và bảng text nguồn/bản dịch theo đoạn. Kiểm chứng dữ liệu khớp segment ID.
- [ ] EDIT-02 — Sửa, lưu và xác nhận bản dịch. Kiểm chứng refresh vẫn giữ nội dung; bản dịch được quản lý revision.
- [ ] EDIT-03 — Kiểm tra dữ liệu trước khi tạo giọng. Kiểm chứng đoạn rỗng/lỗi được đánh dấu; thay đổi bản dịch làm audio/video cũ hết hiệu lực.

## Tuần 5 — TTS và xuất kết quả

- [ ] TTS-01 — Chọn giọng và tạo audio theo đoạn. Kiểm chứng giọng khả dụng và mỗi đoạn có audio hợp lệ, không bị mất nội dung.
- [ ] TTS-02 — Báo lỗi và cho thử lại bước tạo giọng có kiểm soát. Kiểm chứng lỗi TTS không bị thay bằng im lặng rồi báo thành công.
- [ ] RENDER-01 — Đồng bộ audio và xuất MP4/SRT. Kiểm chứng nghe/xem thực tế, kiểm tra thời lượng và các đoạn tiếng dài hơn khoảng thoại.
- [ ] RESULT-01 — Xem trước và tải kết quả. Kiểm chứng đúng project, đúng revision và đúng loại file.
- [ ] FLOW-01 — Chạy trọn luồng bằng video được phép sử dụng. Lưu kết quả kiểm tra thực tế, không dùng toàn bộ mock làm bằng chứng tích hợp.

## Tuần 6 — Kiểm thử và bàn giao

- [ ] QA-01 — Bổ sung unit/integration cho validation, trạng thái, segment và lỗi nhà cung cấp.
- [ ] QA-02 — Kiểm tra video không có audio, không có lời thoại, file hỏng, quota hết, TTS lỗi và FFmpeg lỗi.
- [ ] QA-03 — Đo thời gian từng bước trên máy demo và video thử xác định; ghi cấu hình và hạn chế, không suy diễn tốc độ chưa đo.
- [ ] QA-04 — Kiểm tra dữ liệu runtime/bí mật không được theo dõi bởi Git; kiểm tra phạm vi xóa tệp.
- [ ] DOC-01 — Cập nhật cách chạy, ảnh demo, giới hạn và báo cáo; các hướng dẫn phải khớp ứng dụng thật.
- [ ] DEMO-01 — Chuẩn bị kịch bản trình bày và chạy lại trên môi trường đã chọn.

## Công việc lặp lại mỗi tuần

- [ ] Tạo/cập nhật issue theo task ID.
- [ ] Kiểm tra diff và chạy kiểm tra phù hợp trước commit.
- [ ] Ghi nhật ký sử dụng AI và kết quả tự kiểm tra.
- [ ] Push thay đổi thực tế theo tiến độ của tuần.
- [ ] Tạo báo cáo từ `docs/weekly/TEMPLATE.md`, không sửa mẫu thành báo cáo của riêng một tuần.

Checklist lặp lại không có nghĩa là đã hoàn thành cho toàn bộ học kỳ; bằng chứng nằm trong từng báo cáo tuần.

## Backlog ngoài MVP — chưa lên lịch

- [ ] Đăng nhập và phân quyền nhiều người dùng.
- [ ] Triển khai online sau khi có bảo mật, giới hạn tài nguyên và dự toán vận hành.
- [ ] Hủy tác vụ đang chạy an toàn, dừng tiến trình con và dọn tài nguyên.
- [ ] Xử lý nhiều video, OCR phụ đề, nhiều ngôn ngữ/nhà cung cấp.
- [ ] Biên tập timeline nâng cao hoặc tách giọng/nhạc nền.

Không triển khai backlog ngoài MVP nếu chưa được đồng ý.
