# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi nhóm 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID: `E-seeded_regression-20261117-18ed` |
| Triệu chứng | `lab8_pass` FAIL (status resolved != denied); `refund_amount_correct` FAIL (ledger=20000 != label=0); reply báo hoàn 20.000đ trong khi claim này không đủ điều kiện hoàn |
| Bước sai đầu tiên | Bước 3: `model_override {"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Bước 1 (`handoff`) và Bước 2 (`investigator` lookup_order trả về `delay_days=2`) đều đúng với sự thật database. Bước 3 tự ý lấy số ngày 5 từ text trong ticket đè lên dữ liệu 2 ngày của DB, dẫn đến các bước sau (quote, refund) tính toán sai |
| Failure mode | `FM-03` (ticket_trust — tin ticket hơn DB) dẫn tới `FM-02` (ignore_denied) |
| Đối chứng | Cùng claim@seed trên shape `fixed`: Không có bước `model_override`. Bước 3 chuyển thẳng sang `quote` với `amount_vnd: 0, reason: "no_entitlement"`, reply từ chối đúng chuẩn, ledger ghi nhận 0đ |
| Regression test | `test_override_event_breaks_db_fact` (kiểm tra grader `DbFactKept`) và `test_wrong_amount_in_ledger` (`RefundAmountCorrect`); đã xác nhận fail trên `seeded_regression` và pass trên `fixed` |
| Chưa chắc chắn | Chưa biết nếu khách hàng cung cấp hình ảnh/biên bản giao hàng thực tế qua một kênh khác thì quy trình tranh chấp có cho phép ghi đè ngày hay không |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
