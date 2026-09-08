# Hướng dẫn cho trợ lý lập trình

## Đọc trước khi làm việc

1. `README.md`: mục tiêu và phạm vi.
2. `PLAN.md`: hướng phát triển theo giai đoạn.
3. `RULES.md`: quy tắc bắt buộc trong dự án.
4. `TASKS.md`: trạng thái và việc cần làm.
5. `docs/ARCHITECTURE.md`: ranh giới trách nhiệm dự kiến.

## Cách làm việc

- AutoDub đang bắt đầu bằng tài liệu và thư mục giữ chỗ. Không giả định backend/frontend đã tồn tại hoặc chạy được.
- Chỉ làm task người phát triển yêu cầu; không tự triển khai các tuần sau.
- Trước khi sửa, nêu ngắn gọn mục tiêu và phạm vi file.
- Thực hiện thay đổi nhỏ, giữ các thay đổi không liên quan của người phát triển.
- Khi tích hợp thư viện, kiểm tra tài liệu chính thức và môi trường trước; không đoán tên API/model hoặc bịa dependencies.
- Không đưa khóa API, video hoặc dữ liệu runtime vào Git.
- Không tự commit/push hoặc thao tác phá hủy lịch sử khi chưa được yêu cầu.
- Sau thay đổi, báo rõ file đã sửa, kiểm tra đã chạy, kết quả và phần chưa kiểm chứng.
- Chỉ cập nhật task sang hoàn thành khi đạt tiêu chí; ghi công việc AI vào `docs/AI_USAGE.md` khi phù hợp.
- Nếu được yêu cầu chỉ lập kế hoạch/đánh giá, không triển khai chức năng.

Các quy tắc chi tiết nằm tại RULES.md; không duy trì bản sao nội dung dài dễ lệch nhau trong file này.
