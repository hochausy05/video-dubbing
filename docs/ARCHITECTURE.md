# Kiến trúc dự kiến

> Bản thiết kế ban đầu, chưa phải mô tả hệ thống đã triển khai. Không cần tạo toàn bộ thành phần trong một lần.

## 1. Thành phần và trách nhiệm

| Thành phần | Trách nhiệm | Không đảm nhiệm |
| --- | --- | --- |
| Frontend | Upload, danh sách, tiến độ, sửa bản dịch, xem/tải kết quả | Giữ bí mật API hoặc trực tiếp chạy Whisper/FFmpeg |
| FastAPI | Kiểm tra request, lưu dữ liệu, tạo job, cung cấp trạng thái/kết quả | Chạy toàn bộ pipeline nặng trong request |
| Queue | Chuyển job ID đến worker | Là nguồn dữ liệu duy nhất cho lịch sử dự án |
| Python worker | Gọi các bước nhận dạng/dịch/TTS/render, lưu kết quả và trạng thái | Phụ thuộc một tab trình duyệt luôn mở |
| SQLite | Lưu metadata, segment, revision, job và artifact | Chứa trực tiếp video dung lượng lớn |
| Storage cục bộ | Video nguồn, tệp trung gian và kết quả theo project/job | Nhận đường dẫn tùy ý từ client |

Worker có thể chạy cùng máy với API nhưng là tiến trình riêng. Giữ một tác vụ video chạy đồng thời trong MVP. Nạp mô hình vào worker theo vòng đời phù hợp; không nạp lại chỉ vì frontend gọi lấy tiến độ.

Whisper và FFmpeg vẫn chạy đầy đủ trong worker. Tách worker không tự làm tác vụ nhanh hơn hay chậm hơn nhiều lần; tốc độ thực tế phải đo trên môi trường triển khai và còn phụ thuộc thời gian chờ hàng đợi.

## 2. Hai tác vụ chính dự kiến

| Tác vụ | Các bước | Đầu ra |
| --- | --- | --- |
| Phân tích và dịch | Kiểm tra video, trích audio, nhận dạng, dịch | Transcript có ID/timestamp và bản dịch để người dùng duyệt |
| Tạo giọng và xuất | Đọc revision đã xác nhận, TTS, kiểm tra thời lượng, render | Audio theo đoạn, MP4 và SRT của revision đó |

Không để worker chờ trong lúc người dùng sửa bản dịch. Sau tác vụ đầu, lưu dữ liệu và kết thúc job; chỉ tạo job tiếp theo khi người dùng xác nhận.

Trạng thái job dự kiến: `queued`, `running`, `succeeded`, `failed`, `interrupted`. Trường `stage` biểu thị bước chi tiết. Trạng thái nghiệp vụ của project như `awaiting_review` hoặc `ready` được lưu riêng, không trộn với tình trạng worker.

Job thành công ở bước dịch không có nghĩa cả dự án đã xuất video. Tỷ lệ phần trăm chỉ hiển thị khi có dữ liệu tiến độ phù hợp; nếu chưa có thì hiển thị tên bước và số đoạn đã xử lý.

## 3. Dữ liệu tối thiểu dự kiến

| Thực thể | Dữ liệu chính |
| --- | --- |
| Project | ID, tên, video nguồn, ngôn ngữ, giọng, trạng thái nghiệp vụ, revision hiện tại, thời gian tạo |
| Job | ID, project ID, loại tác vụ, revision đầu vào, trạng thái, stage, lỗi, thời gian bắt đầu/kết thúc |
| Segment | ID ổn định, project ID, thứ tự, start/end, text nguồn, text dịch, revision và cảnh báo |
| Artifact | ID, project/job ID, revision, loại tệp và đường dẫn nội bộ |

Các tên trường/schema chỉ được chốt khi triển khai DATA-01. Không dùng tên file do người dùng nhập làm project ID. Client nhận ID/URL được kiểm soát thay vì đường dẫn tuyệt đối trên máy chủ.

Khi bản dịch đổi, audio/video từ revision cũ không được dùng như kết quả hiện hành. Khi thử lại, dùng định danh lần chạy để tránh ghi chồng file hoặc tính phí gọi dịch vụ hai lần không cần thiết.

## 4. Nhóm API dự kiến

- Tạo và liệt kê dự án; đọc chi tiết dự án.
- Upload video và xem video nguồn.
- Tạo job nhận dạng/dịch; đọc trạng thái job.
- Đọc/sửa các đoạn dịch và xác nhận revision.
- Tạo job lồng tiếng/render.
- Xem/tải artifact thuộc đúng dự án.

Chưa khóa URL, request hoặc response. Chốt hợp đồng API theo từng task trước khi nối frontend, không viết toàn bộ endpoint ngay trong giai đoạn tài liệu.

## 5. Môi trường và giới hạn

- Demo đầu tiên: cục bộ một người dùng; CPU là đường chạy cần thử, GPU là tăng tốc nếu tương thích.
- Redis + RQ là lựa chọn khảo sát, phải kiểm tra tương thích hệ điều hành trước khi dùng; cân nhắc WSL/Linux nếu cần.
- API key nằm ở backend/worker, cấu hình mẫu chỉ chứa placeholder.
- Model, phiên bản thư viện và lệnh cài đặt phải được kiểm chứng ở bước tạo môi trường.
- Storage, DB và log không đưa lên Git. Phải xác định chính sách giữ/xóa tệp trước khi thêm chức năng dọn dẹp.
- Không có deploy online, tài khoản hoặc cam kết chất lượng/thời gian xử lý trong bộ khung này.
