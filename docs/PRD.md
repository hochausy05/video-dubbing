# PRD — AutoDub

## 1. Tổng quan

AutoDub là webapp hỗ trợ một người dùng chuyển lời thoại của video sang tiếng Việt: tải video lên, nhận dạng lời nói có mốc thời gian, dịch theo từng đoạn, duyệt và sửa bản dịch, tạo giọng đọc tiếng Việt, rồi xuất video lồng tiếng và phụ đề SRT.

Sản phẩm giải quyết nhu cầu tạo bản dịch và lồng tiếng Việt có thể kiểm soát được cho video ngắn. AI chỉ tạo kết quả hỗ trợ; người dùng là người duyệt nội dung trước khi tạo giọng và xuất kết quả.

### Trạng thái hiện tại

Đây là tài liệu yêu cầu cho dự án môn Chuyên đề 4. Repository AutoDub đã được tạo và commit đầu tiên đã được push lên GitHub. Tại thời điểm viết, AutoDub **chưa có chức năng ứng dụng nào được triển khai**; repository hiện chỉ chứa tài liệu định hướng và cấu trúc thư mục. Mọi khả năng mô tả trong phần phạm vi, yêu cầu và user story dưới đây đều là **yêu cầu dự kiến** cho MVP, không phải cam kết rằng hệ thống đã chạy được.

## 2. Mục tiêu

- Cung cấp luồng rõ ràng từ video đầu vào đến video có lồng tiếng Việt và phụ đề SRT.

- Giúp người dùng xem, sửa và xác nhận bản dịch theo từng đoạn trước khi sử dụng bản dịch đó cho TTS/render.

- Tách giao diện, API và xử lý nền để tác vụ nặng không giữ mở request của người dùng.

- Hiển thị trạng thái và lỗi trung thực; không trình bày kết quả AI, audio hoặc video là hoàn tất khi chưa được tạo hợp lệ.

- Phát triển tăng dần theo các task trong `TASKS.md`, lưu bằng chứng tiến độ thực tế trên GitHub theo tuần.

## 3. Người dùng mục tiêu

### Người dùng chính

Người cần dịch và lồng tiếng Việt cho từng video ngắn mà họ sở hữu hoặc được phép sử dụng.

Người dùng chính có kiến thức máy tính cơ bản: chọn tệp, theo dõi trạng thái, đọc/chỉnh sửa văn bản và tải tệp kết quả. Họ không cần biết cách chạy Whisper, TTS hay FFmpeg.

### Bối cảnh sử dụng

- MVP phục vụ một người dùng tại một thời điểm trên máy cục bộ.

- Video đầu vào ưu tiên là MP4, dự kiến không quá 3 phút và 100 MB; các giới hạn này phải được xác minh khi triển khai, không coi là số liệu đã kiểm chứng.

- Ngôn ngữ nguồn ưu tiên là tiếng Anh hoặc tiếng Trung; ngôn ngữ đích là tiếng Việt.

## 4. Phạm vi MVP dự kiến

| Nhóm | Khả năng dự kiến |
| --- | --- |
| Quản lý dự án | Tạo, xem danh sách và xem chi tiết dự án video. |
| Video đầu vào | Upload từ máy tính; backend kiểm tra tệp và lưu theo ID do server tạo. |
| Nhận dạng và dịch | Tạo transcript theo đoạn có ID, text nguồn và mốc thời gian; dịch sang tiếng Việt. |
| Duyệt nội dung | Xem/sửa bản dịch theo từng đoạn, lưu và xác nhận một revision trước TTS. |
| Xử lý nền | Chạy một tác vụ video tại một thời điểm; các tác vụ còn lại chờ; lưu trạng thái và lỗi. |
| Lồng tiếng và xuất | Chọn một trong hai giọng Việt dự kiến, tạo audio, render MP4, tạo SRT, xem trước và tải kết quả. |

## 5. Luồng sử dụng dự kiến

1. Người dùng tạo dự án và tải video từ máy tính lên.

2. Người dùng chọn ngôn ngữ nguồn, sau đó yêu cầu nhận dạng và dịch.

3. Hệ thống tạo job nền; người dùng xem trạng thái, bước đang xử lý và lỗi (nếu có).

4. Khi job dịch hoàn thành, người dùng mở phần duyệt, đối chiếu text nguồn/mốc thời gian với bản dịch và sửa từng đoạn nếu cần.

5. Người dùng lưu và xác nhận revision bản dịch.

6. Người dùng chọn giọng tiếng Việt, yêu cầu tạo giọng và render. Hệ thống chỉ dùng revision đã xác nhận.

7. Người dùng xem trước, tải MP4 và/hoặc SRT của đúng dự án và revision hiện hành.

Nếu một bước lỗi, hệ thống phải báo rõ bước và nguyên nhân có thể hiển thị; không được thay bằng audio im lặng, bản dịch thiếu hoặc artifact cũ rồi báo thành công.

## 6. User stories

### US-001: Tạo và xem dự án

**Mô tả:** Là người dùng, tôi muốn tạo và xem danh sách dự án video để tiếp tục công việc sau khi tải lại trang.

**Tiêu chí nghiệm thu:**

- [ ] Người dùng tạo được một dự án với tên và thông tin cần thiết cho video.

- [ ] Danh sách hiển thị dự án đã tạo cùng trạng thái nghiệp vụ hiện có.

- [ ] Tải lại trang vẫn hiển thị dự án đã lưu.

- [ ] Kiểm chứng giao diện bằng trình duyệt trên môi trường chạy cục bộ.

### US-002: Tải và kiểm tra video

**Mô tả:** Là người dùng, tôi muốn tải video từ máy tính để hệ thống dùng làm đầu vào xử lý.

**Tiêu chí nghiệm thu:**

- [ ] Hệ thống chấp nhận video hợp lệ thuộc định dạng đã hỗ trợ trong MVP.

- [ ] Hệ thống từ chối rõ ràng tệp hỏng, sai định dạng, vượt dung lượng hoặc vượt thời lượng được cấu hình.

- [ ] Tên tệp do người dùng nhập không quyết định đường dẫn lưu trên máy chủ.

- [ ] Video được gắn với đúng project bằng ID do backend tạo.

- [ ] Kiểm chứng giao diện bằng trình duyệt trên môi trường chạy cục bộ.

### US-003: Yêu cầu nhận dạng và dịch

**Mô tả:** Là người dùng, tôi muốn yêu cầu hệ thống nhận dạng và dịch lời thoại để có bản nháp tiếng Việt để duyệt.

**Tiêu chí nghiệm thu:**

- [ ] Request tạo job trả về định danh job; xử lý nặng chạy ngoài request web.

- [ ] Mỗi segment kết quả có ID ổn định, thứ tự, thời gian bắt đầu/kết thúc, text nguồn và text dịch riêng.

- [ ] Video không có lời thoại hoặc kết quả thiếu/sai cấu trúc được báo là cần xử lý, không được coi là bản dịch hoàn chỉnh.

- [ ] Lỗi tạm thời, quota và lỗi dữ liệu được phân biệt khi có thông tin cần thiết.

### US-004: Theo dõi job và xử lý lỗi

**Mô tả:** Là người dùng, tôi muốn biết tác vụ đang ở bước nào hoặc vì sao lỗi để không nhầm lẫn trạng thái xử lý.

**Tiêu chí nghiệm thu:**

- [ ] Job lưu trạng thái `queued`, `running`, `succeeded`, `failed` hoặc `interrupted`, cùng bước xử lý và thông tin lỗi phù hợp.

- [ ] Tải lại trang không làm mất trạng thái đã lưu.

- [ ] Job thành công ở bước dịch không bị hiển thị nhầm là video đã xuất xong.

- [ ] Phần trăm tiến độ chỉ hiển thị khi có dữ liệu tiến độ thực; nếu không, hiển thị tên bước hoặc số đoạn đã xử lý.

- [ ] Kiểm chứng giao diện bằng trình duyệt trên môi trường chạy cục bộ.

### US-005: Duyệt, sửa và xác nhận bản dịch

**Mô tả:** Là người dùng, tôi muốn sửa bản dịch theo từng đoạn và xác nhận phiên bản cần dùng để nội dung tiếng Việt phù hợp trước khi tạo giọng.

**Tiêu chí nghiệm thu:**

- [ ] Giao diện hiển thị text nguồn, text dịch, thứ tự và mốc thời gian theo cùng segment ID.

- [ ] Người dùng lưu được nội dung đã sửa và thấy lại nội dung đó sau khi tải lại trang.

- [ ] Bản dịch có revision; chỉ revision được người dùng xác nhận mới đủ điều kiện cho TTS/render.

- [ ] Đoạn rỗng hoặc lỗi được đánh dấu để người dùng xử lý trước khi xuất.

- [ ] Việc sửa bản dịch làm artifact audio/video của revision cũ không còn là kết quả hiện hành.

- [ ] Kiểm chứng giao diện bằng trình duyệt trên môi trường chạy cục bộ.

### US-006: Tạo giọng và xuất kết quả

**Mô tả:** Là người dùng, tôi muốn chọn giọng tiếng Việt và xuất video/phụ đề từ bản dịch đã xác nhận để nhận kết quả sử dụng được.

**Tiêu chí nghiệm thu:**

- [ ] Người dùng chỉ chọn được giọng đã được kiểm tra khả dụng trong cấu hình thực tế.

- [ ] TTS/render dùng đúng project và revision đã xác nhận.

- [ ] Mỗi audio đoạn được kiểm tra là hợp lệ; lỗi TTS không bị thay bằng audio im lặng rồi báo thành công.

- [ ] Hệ thống kiểm tra và cảnh báo khi thời lượng giọng đọc dài hơn khoảng thoại; không tự cắt mất câu chỉ để khớp timeline.

- [ ] Khi render thành công, MP4 và SRT gắn với đúng project, job và revision.

- [ ] Kiểm chứng giao diện bằng trình duyệt trên môi trường chạy cục bộ.

## 7. Yêu cầu chức năng

1. **FR-01 — Quản lý project:** Hệ thống phải cho phép tạo, liệt kê và xem chi tiết project; metadata phải còn sau khi khởi động lại ứng dụng.

2. **FR-02 — Upload an toàn:** Hệ thống phải nhận video từ máy tính, kiểm tra định dạng thực tế, dung lượng và thời lượng trước khi xếp xử lý; không chỉ tin phần mở rộng.

3. **FR-03 — Lưu tệp theo server:** Backend phải tạo ID và thư mục riêng cho mỗi project/job; client không gửi hoặc nhận quyền dùng đường dẫn tuyệt đối tùy ý.

4. **FR-04 — Tạo job nền:** Nhận dạng/dịch và TTS/render phải tạo job chạy ở worker riêng; API không giữ request mở để hoàn tất toàn bộ pipeline.

5. **FR-05 — Điều phối MVP:** Hệ thống phải chỉ xử lý một tác vụ video đồng thời; tác vụ tiếp theo chờ theo cơ chế hàng đợi đã được kiểm chứng môi trường.

6. **FR-06 — Transcript và dịch:** Hệ thống phải lưu segment theo ID ổn định với timestamp hợp lệ, text nguồn và text tiếng Việt tách biệt.

7. **FR-07 — Trạng thái bền vững:** Hệ thống phải lưu trạng thái, stage, thời gian và lỗi của job; phân biệt trạng thái job với trạng thái nghiệp vụ project.

8. **FR-08 — Duyệt bản dịch:** Hệ thống phải cho phép người dùng đọc, sửa, lưu và xác nhận bản dịch từng segment trước khi tạo giọng.

9. **FR-09 — Revision và artifact:** Khi bản dịch thay đổi, artifact cũ phải bị đánh dấu không còn hiện hành; retry phải có định danh lần chạy để không ghi đè/tái sử dụng nhầm artifact.

10. **FR-10 — TTS có kiểm soát:** Hệ thống phải tạo audio theo segment bằng giọng Việt đã kiểm chứng, phát hiện lỗi hoặc audio không hợp lệ và báo lỗi rõ ràng.

11. **FR-11 — Render và phụ đề:** Hệ thống phải tạo MP4 lồng tiếng và SRT từ revision đã xác nhận, đồng thời cho phép xem trước/tải artifact đúng project.

12. **FR-12 — Thông báo dịch vụ ngoài:** Trước hoặc tại thời điểm dùng dịch vụ AI bên ngoài, hệ thống phải thông báo rằng text được gửi đến dịch vụ đó.

## 8. Yêu cầu phi chức năng

1. **NFR-01 — Phạm vi vận hành:** MVP chỉ hỗ trợ demo cục bộ cho một người dùng; không có yêu cầu triển khai công khai hoặc đa người dùng.

2. **NFR-02 — Tính trung thực kết quả:** Không được báo hoàn tất nếu transcript, bản dịch, audio hoặc render bị thiếu, không hợp lệ hoặc thuộc revision cũ.

3. **NFR-03 — Độ tin cậy:** Lỗi tạm thời chỉ được retry có giới hạn; hệ thống phải tránh chạy trùng job khi thử lại.

4. **NFR-04 — Bảo mật dữ liệu:** Không đưa API key, `.env`, video, cơ sở dữ liệu runtime hoặc log chứa nội dung nhạy cảm vào Git; frontend không chứa API key.

5. **NFR-05 — An toàn xử lý tệp:** Lệnh FFmpeg phải dùng danh sách đối số, không ghép dữ liệu người dùng thành shell command; tiến trình/tệp phải được đóng hoặc giải phóng trên cả nhánh lỗi.

6. **NFR-06 — Khả năng kiểm chứng:** Mỗi task chức năng chỉ hoàn thành sau khi có test hoặc bước kiểm tra thủ công tái hiện được cùng kết quả thực tế; mock phải được ghi rõ là mock.

7. **NFR-07 — Hiệu năng và tài nguyên:** Không cam kết thời gian xử lý trước khi đo trên máy demo. CPU là đường chạy cần thử; GPU chỉ là tăng tốc tùy khả năng tương thích.

8. **NFR-08 — Khả năng bảo trì:** Tách frontend, API, services và worker theo ranh giới trong `docs/ARCHITECTURE.md`; không thêm microservice/abstraction không cần thiết.

## 9. Ngoài phạm vi MVP

- Đăng nhập, phân quyền hoặc hỗ trợ nhiều người dùng.

- Thanh toán.

- Triển khai demo công khai trên Internet.

- Tải video bằng liên kết mạng xã hội hoặc đăng video tự động.

- Nhân bản giọng nói, đồng bộ khẩu hình, OCR phụ đề, tách giọng khỏi nhạc nền.

- Xử lý hàng loạt nhiều video, chỉnh sửa timeline nâng cao hoặc thêm nhiều nhà cung cấp/ngôn ngữ ngoài ưu tiên MVP.

- Cam kết chất lượng dịch, giọng hoặc thời gian xử lý khi chưa có phép đo và kiểm thử thực tế.

## 10. Lưu ý thiết kế và kỹ thuật

- UI cần ưu tiên thông tin trạng thái/bước lỗi dễ hiểu, danh sách project, trình phát video và bảng segment gồm text nguồn, bản dịch, timestamp.

- Một job dịch kết thúc trước khi người dùng duyệt; worker không chờ trong thời gian người dùng sửa text. TTS/render là job mới sau xác nhận.

- Dữ liệu tối thiểu dự kiến gồm `Project`, `Job`, `Segment` và `Artifact`; tên trường/hợp đồng API chỉ được chốt trong task triển khai tương ứng.

- Công nghệ đang là định hướng, chưa được cài hoặc xác minh: React + TypeScript + Vite, FastAPI, Python worker, SQLite, Redis + RQ (đang khảo sát), faster-whisper, Gemini API qua Google Gen AI SDK, Edge-TTS và FFmpeg/ffprobe.

## 11. Tiêu chí nghiệm thu MVP

MVP được coi là đạt khi có bằng chứng thực tế cho toàn bộ luồng sau trên môi trường demo đã chọn và bằng video được phép sử dụng:

1. Tạo project và upload một video hợp lệ; đầu vào sai bị từ chối với thông báo rõ ràng.

2. Job nhận dạng/dịch chạy ở worker, tạo segment có timestamp và text nguồn/bản dịch; trạng thái/lỗi còn sau khi tải lại giao diện.

3. Người dùng sửa, lưu và xác nhận bản dịch; revision được duy trì và artifact cũ không bị coi là kết quả mới.

4. Người dùng chọn giọng khả dụng, tạo audio và render MP4/SRT từ đúng revision đã xác nhận.

5. Người thực hiện nghe/xem MP4, kiểm tra SRT, thời lượng và các đoạn tiếng đọc dài hơn khoảng thoại; các hạn chế/lỗi còn lại được ghi rõ.

6. Không có bí mật hoặc dữ liệu runtime bị theo dõi bởi Git, và tài liệu/các bước kiểm tra phản ánh đúng trạng thái thực tế.

## 12. Chỉ số thành công dự kiến

Các chỉ số dưới đây là tiêu chí đánh giá MVP, chưa phải số liệu đã đạt:

- Hoàn thành được luồng từ upload đến MP4/SRT với ít nhất một video kiểm thử hợp lệ được phép sử dụng.

- 100% segment trong kết quả dịch có ID, text nguồn, text dịch và timestamp hợp lệ, hoặc được đánh dấu rõ lỗi/cần duyệt.

- 100% lần xuất kết quả dùng revision đã được người dùng xác nhận.

- Không có trường hợp biết được mà hệ thống báo thành công bằng audio im lặng, artifact sai revision hoặc kết quả thiếu.

- Có hướng dẫn tái hiện, kết quả kiểm tra thật và báo cáo giới hạn cho môi trường demo.

## 13. Câu hỏi mở trước hoặc trong triển khai

1. Lịch học, hạn nộp và tiêu chí đánh giá chính thức của môn là gì?

2. Dự án làm cá nhân hay theo nhóm; nếu theo nhóm thì phân công trách nhiệm thế nào?

3. Máy phát triển/demo dùng hệ điều hành nào, cấu hình CPU/GPU/RAM ra sao và worker có cần WSL/Linux không?

4. Video kiểm thử nào được phép dùng, và quyền truy cập/quota cho dịch vụ dịch/TTS có sẵn đến đâu?

5. Môn học có yêu cầu demo online không? Nếu có, cần lập yêu cầu riêng về kiểm soát truy cập, quota và giới hạn tài nguyên trước khi mở phạm vi.

## 14. Theo dõi thực hiện

- PRD này không thay thế `TASKS.md` và không đánh dấu bất kỳ task chức năng nào hoàn thành.

- Triển khai phải bám theo thứ tự task hiện có, bắt đầu sau khi các quyết định INIT-03 và INIT-04 được xác nhận.

- Khi công nghệ, giới hạn hay hành vi thực tế khác với tài liệu này, cập nhật PRD và các tài liệu liên quan cùng bằng chứng kiểm tra; không suy diễn tính năng đã hoàn tất từ kế hoạch.