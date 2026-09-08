# AutoDub

Webapp hỗ trợ tự động dịch và lồng tiếng video bằng AI.

> Dự án môn Chuyên đề 4 — giai đoạn khởi tạo. Repository hiện chỉ có tài liệu định hướng và cấu trúc thư mục; chưa có ứng dụng chạy được.

## 1. Giới thiệu

AutoDub hướng đến việc hỗ trợ người dùng chuyển lời thoại trong video sang tiếng Việt: tải video lên, nhận dạng lời nói, dịch nội dung, duyệt và chỉnh sửa bản dịch, tạo giọng đọc và xuất video có lồng tiếng.

AI hỗ trợ xử lý nội dung, còn người dùng có thể kiểm tra và điều chỉnh kết quả trước khi xuất. Chất lượng nhận dạng, dịch và đồng bộ âm thanh cần được đánh giá trong quá trình phát triển, không mặc định là chính xác hoàn toàn.

## 2. Mục tiêu

- Xây dựng một webapp có quy trình sử dụng rõ ràng, từ tải video đến nhận kết quả.
- Tích hợp các thành phần nhận dạng lời nói, dịch thuật, tạo giọng và xử lý video.
- Tách giao diện, API và tác vụ xử lý nền để thuận tiện phát triển và kiểm thử.
- Sử dụng AI hỗ trợ lập trình có kiểm soát; lưu tiến độ thực tế trên GitHub theo tuần/giai đoạn.

## 3. Phạm vi phiên bản tối thiểu dự kiến

Các mục dưới đây là yêu cầu dự kiến, chưa phải tính năng đã triển khai.

| Nhóm | Phạm vi ban đầu |
| --- | --- |
| Video đầu vào | Upload từ máy tính; ưu tiên MP4, tối đa 3 phút và 100 MB; giới hạn sẽ kiểm chứng bằng thử nghiệm |
| Ngôn ngữ | Ưu tiên tiếng Anh hoặc tiếng Trung sang tiếng Việt |
| Nhận dạng | Trích xuất lời thoại có mốc thời gian |
| Dịch | Dịch theo từng đoạn, giữ liên kết với lời thoại và thời gian nguồn |
| Biên tập | Xem và sửa bản dịch trước khi tạo giọng |
| Lồng tiếng | Chọn một trong hai giọng tiếng Việt dự kiến; kiểm tra khả dụng khi tích hợp |
| Xử lý nền | Một tác vụ video chạy tại một thời điểm; các tác vụ còn lại chờ |
| Kết quả | Xem trước và tải MP4, tải phụ đề SRT |
| Quản lý | Danh sách dự án, trạng thái xử lý và thông báo lỗi |

Chưa thuộc phạm vi tối thiểu: đăng nhập nhiều người dùng, thanh toán, tải video từ liên kết mạng xã hội, đăng video tự động, nhân bản giọng nói, đồng bộ khẩu hình, OCR phụ đề, tách giọng khỏi nhạc nền, xử lý hàng loạt và hệ thống chỉnh sửa timeline nâng cao.

Bản đầu hướng đến môi trường demo cục bộ một người dùng. Nếu cần công khai trên Internet, phải bổ sung kiểm soát truy cập và giới hạn tài nguyên trước khi triển khai.

## 4. Quy trình sử dụng dự kiến

1. Tạo dự án và tải video lên.
2. Chọn ngôn ngữ nguồn và yêu cầu nhận dạng, dịch.
3. Theo dõi tiến độ xử lý.
4. Duyệt và sửa bản dịch theo từng đoạn.
5. Chọn giọng đọc, xác nhận tạo giọng và xuất video.
6. Xem trước, tải video và phụ đề.

## 5. Công nghệ định hướng

| Thành phần | Lựa chọn dự kiến |
| --- | --- |
| Giao diện | React + TypeScript + Vite |
| API | Python + FastAPI |
| Xử lý nền | Python worker; Redis + RQ là phương án khảo sát ban đầu |
| Dữ liệu | SQLite cho demo cục bộ |
| Nhận dạng lời nói | faster-whisper |
| Dịch | Gemini API thông qua Google Gen AI SDK |
| Tạo giọng | Edge-TTS, cần thử nghiệm độ ổn định và kiểm tra điều kiện sử dụng |
| Xử lý video | FFmpeg / ffprobe |
| Lưu tệp | Thư mục cục bộ do backend quản lý |

Chưa chốt phiên bản thư viện và chưa tạo file dependencies. Khả năng chạy trên môi trường phát triển, đặc biệt worker trên Windows/WSL, sẽ được xác minh trước khi cài đặt. Tác vụ nền vẫn thực hiện Whisper và render; không loại bỏ hai bước này.

## 6. Cấu trúc ban đầu

| Đường dẫn | Trách nhiệm dự kiến |
| --- | --- |
| `frontend/src/pages/` | Các trang giao diện |
| `frontend/src/components/` | Thành phần giao diện dùng lại |
| `frontend/src/services/` | Gọi API từ trình duyệt |
| `backend/app/api/` | Tiếp nhận request và trả response |
| `backend/app/core/` | Cấu hình, logging và thành phần dùng chung |
| `backend/app/models/` | Mô hình dữ liệu lưu trữ |
| `backend/app/schemas/` | Cấu trúc dữ liệu và kiểm tra đầu vào/đầu ra |
| `backend/app/services/` | Logic nghiệp vụ và xử lý AI/video |
| `backend/app/workers/` | Điều phối tác vụ chạy nền |
| `tests/` | Kiểm thử unit, integration và end-to-end |
| `storage/` | Giữ chỗ cho dữ liệu runtime; không đưa video lên Git |
| `docs/` | Kiến trúc dự kiến, nhật ký AI và báo cáo tuần |

Các thư mục chưa có mã nguồn chứa `.gitkeep` để Git lưu được cấu trúc. Chúng không phải module đã triển khai.

## 7. Tài liệu và cách bắt đầu

- [PLAN.md](PLAN.md): các giai đoạn và sản phẩm bàn giao theo tuần.
- [TASKS.md](TASKS.md): danh sách việc cần làm và trạng thái thực tế.
- [RULES.md](RULES.md): quy tắc phát triển, kiểm thử và sử dụng AI.
- [AGENTS.md](AGENTS.md): hướng dẫn đầu vào cho trợ lý lập trình.
- [Kiến trúc dự kiến](docs/ARCHITECTURE.md): phân chia thành phần và dữ liệu.
- [Nhật ký sử dụng AI](docs/AI_USAGE.md): mẫu ghi nhận quá trình AI hỗ trợ.
- [Mẫu báo cáo tuần](docs/weekly/TEMPLATE.md): bằng chứng tiến độ từng giai đoạn.

Chưa có lệnh khởi chạy ứng dụng. Bước tiếp theo là xác nhận phạm vi và lịch học, sau đó khởi tạo môi trường backend/frontend theo TASKS.md. Không cần cài đặt toàn bộ công nghệ ngay ở giai đoạn tài liệu này.

## 8. Dữ liệu và sử dụng có trách nhiệm

Chỉ dùng video do người dùng sở hữu hoặc được phép sử dụng. Không đưa API key, video cá nhân hoặc nội dung nhạy cảm lên GitHub. Khi tích hợp dịch/TTS, cần thông báo rõ phần văn bản nào được gửi đến dịch vụ bên ngoài.

Nếu sử dụng mã nguồn hoặc tài nguyên bên thứ ba, phải tuân thủ giấy phép và ghi nguồn phù hợp. Việc ứng dụng AI trong lập trình cần được mô tả trung thực cùng với phần kiểm tra do người phát triển thực hiện.
