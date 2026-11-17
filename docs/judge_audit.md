# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (κ=0.757 ≥ 0.6, P=0.857 ≥ 0.8, R=0.800 ≥ 0.7) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt (κ=0.375 < 0.6, R=0.300 < 0.7) | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | HL-015: "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." | PASS | FAIL | Người đúng | **Lỗi sai tiền.** Judge bị đánh lừa bởi văn phong trôi chảy, không biết số tiền sai với DB. *Sửa rubric:* Không dùng judge chấm tiền; hoặc rubric phải yêu cầu tra cứu ground-truth DB trước khi chấm. |
| 2 | HL-016: "Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn..." | PASS | FAIL | Người đúng | **Xin lỗi sáo rỗng.** Câu trả lời chỉ xin lỗi nhưng không giải quyết khiếu nại hay đưa ra hướng giải quyết. *Sửa rubric:* Bổ sung quy định "chỉ xin lỗi mà không giải quyết thì tính là FAIL". |
| 3 | HL-020: "Dạ, LogiX đã hoàn 90.000đ cho đơn O-303 ạ." | PASS | FAIL | Người đúng | **Sai số tiền bồi thường.** Judge LLM tưởng câu trả lời rõ ràng là helpful, nhưng thực tế sai nghiệp vụ. *Sửa rubric:* Loại bỏ tiêu chuẩn helpful cho các claim liên quan đến tiền bạc. |
| 4 | HL-028: "Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này..." | PASS | FAIL | Người đúng | **Chưa giải quyết nghiệp vụ.** Tương tự HL-016, bot né tránh giải quyết claim nhưng văn phong lịch sự khiến judge nhầm lẫn. *Sửa rubric:* Phải có kết luận (hoàn tiền, từ chối, hoặc hẹn thời gian xử lý) mới được PASS. |
| 5 | H-008: "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người đúng | **Tone xưng hô suồng sã.** Dùng "em - anh" như chat cá nhân, không đạt chuẩn mực CSKH chuyên nghiệp. *Sửa rubric:* Quy định rõ ràng tone chuẩn mực CSKH doanh nghiệp, cấm ngôn từ suồng sã. |

## Kết luận
- **Tiêu chí bị loại:** `helpful` bị loại vì chỉ số thoả thuận Cohen's $\kappa = 0.375$ (thấp hơn nhiều so với sàn $0.6$) và Recall chỉ đạt $0.300$ (thấp hơn sàn $0.7$). Ma trận nhầm lẫn: `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` cho thấy Judge bỏ sót tới 21 lỗi trong tổng số 30 lỗi thật ($FN=21$), khiến tỷ lệ lỗi quan sát chỉ là $9\%$ trong khi thực tế đã hiệu chỉnh qua Rogan-Gladen là $30\%$. Judge bị đánh lừa bởi câu chữ trôi chảy, lịch thiệp mà không phát hiện được thông tin sai sự thật hoặc né tránh giải quyết.
- **Rủi ro còn lại:** Judge `tone_ok` chỉ được kiểm chuẩn trên tập dữ liệu replay công khai ($n=100$). Cần kiểm chuẩn định kỳ trên dữ liệu hội thoại thực tế của người dùng mới (held-out set). Tuyệt đối tuân thủ nguyên tắc: **Tiền và quyền phê duyệt luôn chấm bằng code cứng, không dùng LLM Judge.**
