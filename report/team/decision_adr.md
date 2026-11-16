# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash: (Người 1 điền lúc nộp bài ở bước #16)
- Run id dẫn chứng: R-workflow-C-002-s55 (pass) so với R-swarm-C-002-s55 (fail)
- Pass rate / pass^5 / seed min-max / variance: 1.0 / 1.0 / 1.0-1.0 / 0.0
- Cost per success (mô phỏng, VND): 28.791428571428572
- Crash safety: 20/20 (src/reports/crash.json)
- Secret leak / approval bypass: 0 / 0 trên bộ public, kiểm chứng qua test_trace_leak_sweep.py và test_shape_approval_paths.py

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Quy trình xử lý bồi thường (claims flow) có bản chất tuần tự chặt chẽ: xác thực claim/order (`lookup_order`), tính toán mức hoàn theo chính sách (`compute_compensation`), rồi mới gọi host ghi nhận (`issue_refund`). Trên 14 claim public × 5 seed (70 trial mỗi shape) trong `src/reports/benchmark.json`, `workflow` đạt tuyệt đối: pass rate 1.0, pass^5 1.0, seed variance 0.0 và chi phí mô phỏng thấp nhất toàn bộ (28.79 VND/success so với single 28.91, orchestrator 47.73, swarm 49.57). Quy trình cố định đảm bảo tính tất định, triệt tiêu nguy cơ hallucination về tiền hoặc vi phạm chính sách của LLM.

## Có đáng đổi lấy multi-agent không

Không đáng đổi trong bài toán này. Benchmark đối chứng cho thấy việc tăng số lượng agent (orchestrator hoặc swarm) không hề làm tăng tỷ lệ thành công (orchestrator đạt 1.0 ngang workflow, còn swarm giảm xuống 0.986 với variance 0.000816 do lỗi tin ticket ở seed 55), nhưng chi phí lại tăng 1.66× đến 1.72× do số lượng tool call và LLM call dư thừa của các investigator. Quyết định chỉ đảo lại sang multi-agent khi bài toán mở rộng sang các nghiệp vụ có khả năng song song hóa độc lập cao (như đối soát đồng thời qua nhiều hãng vận chuyển, kho bãi, ngân hàng thanh toán độc lập), hoặc khi dữ liệu phi cấu trúc phức tạp đòi hỏi các chuyên gia chuyên biệt mà pipeline cố định không thể bao quát.

## Trace và bằng chứng

Trace của nhóm ghi nhận các event chuẩn hóa: `claim_received`, `order_lookup`, `compensation_computed`, `refund_issued`, `final_status` tuân thủ Contract v1. Nhóm CỐ Ý KHÔNG ghi: nội dung ticket thô, `parent_secret`, token `Authorization` / `CANARY_SECRET_`, số điện thoại, địa chỉ nhận hàng, ghi chú nội bộ (`internal_note`), và tên hàng hoá nhạy cảm để tuân thủ nguyên tắc Least Privilege và bảo vệ dữ liệu PII/bảo mật hệ thống. Bằng chứng bảo mật: bộ test `src/tests/test_trace_leak_sweep.py` quét 70 trial public và ticket độc hại chèn canary đều pass (0 leak, không print ra stdout), và `src/tests/test_shape_approval_paths.py` xác nhận 100% các vi phạm approval (mượn, thu hồi, thiếu) đều bị denied và ghi audit `policy_denied`.

## Giới hạn

Môi trường kiểm thử sử dụng `MockLLM` quy chuẩn thay vì model sản xuất; `latency` được ghi nhận là `unavailable`. Chi phí token và tool call là số liệu mô phỏng theo `config/pricing.yaml`, chưa phản ánh đầy đủ độ trễ mạng thực tế và chi phí vận hành hạ tầng phân tán trong môi trường production.
