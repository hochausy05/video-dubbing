# Quy tắc phát triển AutoDub

## 1. Bối cảnh và phạm vi

AutoDub đang ở giai đoạn bắt đầu một dự án môn học. Phát triển từng nhiệm vụ, từng giai đoạn và ghi nhận trên GitHub theo tuần. Tài liệu định hướng không phải bằng chứng ứng dụng đã hoạt động.

- Đọc README.md, PLAN.md và TASKS.md trước khi thay đổi.
- Chỉ thực hiện nhiệm vụ được yêu cầu; không tự xây cả hệ thống hoặc thêm tính năng ngoài phạm vi.
- Muốn thay đổi công nghệ/phạm vi đáng kể phải nêu lý do và xin ý kiến người phát triển.
- Không copy bí mật hoặc nội dung không có quyền sử dụng vào repository.

## 2. Phân chia trách nhiệm

- `frontend/`: hiển thị và tương tác; không chứa API key, không trực tiếp chạy Python/FFmpeg.
- `backend/app/api/`: nhận và kiểm tra request, gọi nghiệp vụ; không giữ request mở để xử lý cả video.
- `backend/app/services/`: logic nghiệp vụ, nhận dạng, dịch, TTS và render; không phụ thuộc giao diện.
- `backend/app/workers/`: chạy tác vụ nền, cập nhật trạng thái; lúc đầu chỉ một tác vụ video đồng thời.
- `backend/app/models/` và `schemas/`: tách dữ liệu lưu trữ với hợp đồng request/response.
- `storage/`: dữ liệu runtime; đường dẫn do server tạo, không lấy đường dẫn tùy ý từ người dùng.

Không tạo abstraction, microservice hoặc framework bổ sung khi chưa có nhu cầu cụ thể. Các thư mục là điểm bắt đầu; có thể bổ sung khi triển khai task tương ứng.

## 3. Quy trình sử dụng AI

1. Nêu task ID, mục tiêu, tiêu chí hoàn thành và file dự kiến thay đổi.
2. Yêu cầu AI làm một thay đổi nhỏ, có thể đọc và kiểm chứng.
3. Đọc diff, kiểm tra logic và đối chiếu tài liệu chính thức cho API/thư viện liên quan.
4. Chạy kiểm tra phù hợp; không coi “không báo lỗi cú pháp” là pipeline đã đúng.
5. Ghi kết quả thật vào TASKS.md và nhật ký AI; commit/push theo quy trình dự án.

AI không được tự đánh dấu task hoàn thành nếu chưa có bằng chứng. Không bịa kết quả test, số đo hiệu năng, URL triển khai hoặc lịch sử commit. Sau hai lần sửa cùng lỗi không hiệu quả, dừng cách tiếp cận cũ, tóm tắt bằng chứng và đề xuất hướng mới.

## 4. Chất lượng dữ liệu và xử lý lỗi

- Duy trì ID ổn định cho từng đoạn lời thoại; giữ text nguồn riêng với text dịch.
- Kiểm tra thời gian bắt đầu/kết thúc, nội dung rỗng và số đoạn trả về.
- Không âm thầm dùng text chưa dịch hoặc audio im lặng rồi báo hoàn tất.
- Không cắt bỏ văn bản dài để làm TTS thành công; chia đoạn hợp lý hoặc báo lỗi cần xử lý.
- Có retry giới hạn cho lỗi tạm thời; phân biệt quota hết với lỗi dữ liệu và lỗi mạng.
- TTS/render chỉ sử dụng phiên bản bản dịch đã được người dùng xác nhận.
- Sửa bản dịch phải làm kết quả audio/video cũ trở thành chưa cập nhật; không trình bày chúng như kết quả mới.
- Trạng thái job và lỗi phải được lưu bền vững, không chỉ nằm trong biến của trình duyệt.
- Khi thêm khả năng thử lại, không chạy trùng job hoặc tái sử dụng sai artifact của lần trước.

## 5. Tệp, tài nguyên và bảo mật

- Dùng ID do backend tạo và thư mục riêng cho từng project/job.
- Kiểm tra dung lượng, định dạng thực tế và thời lượng video; không chỉ tin phần mở rộng.
- Gọi FFmpeg bằng danh sách đối số, không ghép đầu vào người dùng thành shell command.
- Thiết lập timeout phù hợp; đóng file/tiến trình và giải phóng tài nguyên trong cả đường lỗi.
- Không commit `.env`, khóa API, môi trường ảo, dependency tải về, video hoặc cơ sở dữ liệu runtime.
- Không ghi API key hoặc toàn bộ nội dung nhạy cảm vào log.
- Không xóa thư mục rộng để dọn cache; chỉ dọn đúng job đã xác định, không xóa đầu vào/kết quả còn cần dùng.
- Không mở demo công khai khi chưa có kiểm soát truy cập, quota và giới hạn dung lượng.
- Thông báo cho người dùng khi văn bản được gửi đến dịch vụ AI bên ngoài.

## 6. Định nghĩa hoàn thành một task

Một task chức năng chỉ được đánh dấu hoàn thành khi:

- Đáp ứng tiêu chí đã ghi trong TASKS.md.
- Có kiểm thử hoặc kiểm tra thủ công có bước tái hiện và kết quả thực tế.
- Các lỗi/giới hạn còn tồn tại được ghi rõ.
- Không lộ bí mật, không thêm dữ liệu runtime vào Git.
- Tài liệu liên quan được cập nhật nếu hành vi/cách chạy thay đổi.

Task tài liệu chỉ cần kiểm tra tính nhất quán, đường dẫn và trạng thái; không yêu cầu giả lập kiểm thử ứng dụng chưa tồn tại.

## 7. Git và tài liệu

- Mỗi commit có mục đích rõ ràng; không gộp thay đổi không liên quan.
- Không tự push, force-push, xóa branch hoặc ghi đè lịch sử khi chưa được yêu cầu.
- Không đánh dấu cả tuần hoàn thành chỉ vì một task nhỏ đã xong.
- Báo cáo tuần ghi phân biệt: đã làm, đang làm, chưa làm, kiểm tra và hạn chế.
- Ghi nhận việc dùng AI trung thực; tôn trọng giấy phép và ghi nguồn tài nguyên/mã bên thứ ba khi cần.
