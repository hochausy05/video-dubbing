# Kế hoạch phát triển AutoDub

## 1. Nguyên tắc lập kế hoạch

- Trạng thái hiện tại: khởi tạo tài liệu và cấu trúc, chưa triển khai chức năng.
- Phát triển tăng dần; mỗi giai đoạn có đầu ra nhỏ có thể kiểm chứng.
- Kế hoạch 6 tuần dưới đây là bản dự kiến, không phải lịch môn học đã xác nhận.
- Không coi việc tạo đủ thư mục hoặc sinh được code là hoàn thành tính năng.
- Ưu tiên demo cục bộ một người dùng, một worker trước khi mở rộng.

## 2. Các mốc dự kiến

| Mốc | Trọng tâm | Đầu ra dự kiến | Điều kiện kiểm chứng |
| --- | --- | --- | --- |
| Tuần 1 | Xác định đề tài và nền tảng | Tài liệu, cấu trúc; sau khi duyệt phạm vi mới tạo backend/frontend tối thiểu | Phạm vi thống nhất; API health và trang chào chạy cục bộ sau bước khởi tạo môi trường |
| Tuần 2 | Quản lý dự án và upload | Dữ liệu project/job; upload; danh sách dự án | Upload video hợp lệ; từ chối đầu vào sai; tải lại trang vẫn thấy dự án |
| Tuần 3 | Nhận dạng và dịch | Worker, trạng thái tác vụ, transcript và bản dịch | Video thử ngắn tạo được các đoạn có timestamp; lỗi API/quota được báo đúng |
| Tuần 4 | Duyệt và sửa bản dịch | Trang chi tiết, trình phát video và bộ sửa text | Sửa và lưu bản dịch; kết quả vẫn còn sau khi tải lại trang |
| Tuần 5 | Tạo giọng và render | Chọn giọng, TTS, xuất MP4/SRT và tải xuống | Luồng upload → dịch → duyệt → lồng tiếng chạy được; kiểm tra đoạn mất tiếng/lệch thời gian |
| Tuần 6 | Kiểm thử và hoàn thiện | Kiểm thử hồi quy, sửa lỗi, hướng dẫn demo, báo cáo | Có bằng chứng chạy thật, danh sách hạn chế và hướng dẫn tái hiện trên môi trường đã kiểm chứng |

Hiện tại mới hoàn thành phần tài liệu/cấu trúc của tuần 1; không đánh dấu cả tuần 1 hoàn thành.

## 3. Trình tự triển khai

1. Chốt yêu cầu, môi trường và tiêu chí nghiệm thu.
2. Dựng khung chạy tối thiểu cho giao diện và API.
3. Hoàn thiện upload, dữ liệu và trạng thái job trước khi tích hợp AI.
4. Tích hợp từng bước xử lý riêng biệt, bắt đầu bằng video mẫu ngắn.
5. Kết nối giao diện duyệt bản dịch với tạo giọng và render.
6. Kiểm thử đầu-cuối, đo thời gian và ghi rõ hạn chế.

Có thể dùng dữ liệu giả để phát triển giao diện/kiểm thử sớm nhưng phải ghi rõ là mock; không dùng mock làm bằng chứng hệ thống AI đã chạy thật.

## 4. Theo dõi GitHub theo tuần

- Tạo repository và remote khi người phát triển sẵn sàng; bộ khung này chưa kết nối GitHub.
- Tạo issue tương ứng task ID trong TASKS.md.
- Commit theo thay đổi có ý nghĩa, ví dụ `docs: define initial scope` hoặc `feat: add video upload` sau khi thực sự làm xong.
- Push đều trong tuần, không đợi đến cuối kỳ mới đưa toàn bộ code lên.
- Cuối tuần dùng mẫu `docs/weekly/TEMPLATE.md` để ghi kết quả thật; liên kết commit/issue và ảnh demo nếu có.
- Không tạo lịch sử, commit, kết quả test hoặc mốc thời gian giả. Nếu chưa hoàn thành thì giữ trạng thái chưa hoàn thành.

## 5. Rủi ro và cách kiểm soát dự kiến

| Rủi ro | Hướng kiểm soát |
| --- | --- |
| Máy thiếu GPU hoặc không tương thích | Thử CPU với video ngắn; đo hiệu năng trước khi quyết định triển khai |
| Hàng đợi/worker không phù hợp Windows | Kiểm chứng môi trường; cân nhắc WSL/Linux trước khi khóa lựa chọn queue |
| Quota, lỗi mạng hoặc dịch vụ TTS gián đoạn | Retry có giới hạn; thông báo rõ; không báo thành công bằng audio im lặng |
| Dịch thiếu hoặc sai nội dung | Giữ text nguồn, cho sửa bản dịch và chỉ rõ đoạn cần kiểm tra |
| Giọng đọc dài hơn khoảng thoại | Đo thời lượng và cảnh báo; không tự cắt mất câu để vừa timeline |
| Video lớn làm đầy RAM/ổ đĩa | Giới hạn upload/thời lượng, một worker, quản lý tệp theo project/job |
| Phạm vi quá rộng | Hoàn thiện MVP trước; không thêm tài khoản, OCR, clone giọng hoặc batch trong giai đoạn đầu |

## 6. Những điểm cần xác nhận

- [ ] Số tuần, hạn nộp và tiêu chí đánh giá chính thức của môn học.
- [ ] Làm cá nhân hay nhóm; phân công nếu có.
- [ ] Hệ điều hành, Python/Node phù hợp và tài nguyên máy demo.
- [ ] Nguồn video kiểm thử được phép sử dụng và quyền truy cập dịch vụ AI.
- [ ] Có bắt buộc demo online không; nếu có, lập thêm kế hoạch bảo mật và triển khai.

Chưa cần giải quyết các điểm này để đọc bộ khung, nhưng phải xác nhận trước những bước triển khai có liên quan.
