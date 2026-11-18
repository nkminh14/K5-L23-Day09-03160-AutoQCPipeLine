# Báo cáo Day 09 — Nguyễn Khoa Minh, 03160

## 1. Kết luận trước
- **Quyết định của pipeline:** **Hold** (mã thoát `10`).
- **Số lượng ảnh:** Đầu vào có **224 ảnh** (`data/raw`). Ở Bước 1 (`intake`), pipeline loại **22/224 ảnh** vi phạm lỗi bắt buộc về chất lượng/trùng lặp (`2 CORRUPT_IMAGE`, `3 BAD_SIZE`, `8 DUP_IMAGE_EXACT`, `4 DUP_IMAGE_NEAR`, `5 LEAK_TEST`), giữ lại **202/224 ảnh** đưa vào kiểm tra nhãn và xuất ra bản nháp `submission/export/clean_v1/` (**202 ảnh**, tổng cộng **748 box**: `0: car` 101 box, `1: person` 574 box, `2: truck` 41 box, `3: bus` 32 box).
- **Lý do chính:** Sau khi `autofix` tự động sửa 35 lỗi cú pháp và người duyệt (mô phỏng với ngân sách 80 ảnh) xử lý **80/202 ảnh** ưu tiên cao nhất (bao gồm gán nhãn mới cho toàn bộ **6/6 ảnh** `MISSING_LABEL_FILE`), bộ dữ liệu không còn lỗi bắt buộc nào (`n_errors = 0`). Tuy nhiên, do tổng hàng đợi cần người xem là **125/202 ảnh** trong khi ngân sách duyệt giới hạn ở **80 ảnh**, vẫn còn **38/202 ảnh (18,81%)** mang cảnh báo chưa qua mắt người duyệt — vượt ngưỡng chặn `gate.warn_ratio_hold = 10%` (`0.10`). Do đó, cổng kiểm soát kết luận **Hold**: cho phép xuất bản nháp (`decision: Hold` trong `manifest.json`) để phục vụ thử nghiệm huấn luyện nhưng chưa được phát hành chính thức.

---

## 2. Lỗi và phân việc
Bảng dưới đây tổng hợp toàn bộ **18 mã lỗi/cảnh báo** xuất hiện trong danh sách lỗi trước khi sửa (`submission/reports/02_error_list_v1.txt`), kèm số lượng dòng lỗi, số ảnh bị ảnh hưởng (kèm mẫu số), phân công xử lý (**máy** hay **người**) và lý do:

| Mã lỗi | Mức độ | Số dòng / Số ảnh | Ai sửa (máy/người) | Vì sao |
|---|---|---:|---|---|
| `CORRUPT_IMAGE` | ERROR | 2 dòng (2/224 ảnh) | **Máy** (`intake` / `autofix` xoá ảnh) | File ảnh hỏng byte (`img_0010`, `img_0136`) không thể giải mã khi `im.load()`, giữ lại sẽ làm sập quá trình huấn luyện. |
| `BAD_SIZE` | ERROR | 3 dòng (3/224 ảnh) | **Máy** (`intake` / `autofix` xoá ảnh) | Ảnh có cạnh ngắn `< 250px` (`img_0107`, `img_0113`, `img_0122`), vi phạm quy tắc độ phân giải tối thiểu của dự án. |
| `DUP_IMAGE_EXACT` | ERROR | 8 dòng (8/224 ảnh) | **Máy** (`intake` / `autofix` xoá ảnh) | Trùng khớp 100% mã băm MD5 với ảnh đứng trước; xoá bản sao giúp tránh lệch phân bố dữ liệu. |
| `DUP_IMAGE_NEAR` | ERROR | 4 dòng (4/224 ảnh) | **Máy** (`intake` / `autofix` xoá ảnh) | Trùng gần đúng (`phash_dist <= 10`: ảnh thu nhỏ/đổi sáng/cắt nhẹ như `img_0076`, `img_0143`, `img_0186`, `img_0223`); máy loại bỏ tự động để tránh rò rỉ nội bộ. |
| `LEAK_TEST` | ERROR | 5 dòng (5/224 ảnh) | **Máy** (`intake` / `autofix` xoá ảnh) | Ảnh trùng với kho `data/test` hoặc `data/gold_val` (`img_0049`, `img_0101`, `img_0167`, `img_0174`, `img_0221`); bắt buộc loại bỏ để không làm mAP test đẹp giả. |
| `BAD_CLASS_NAME` | ERROR | 2 dòng (`data.yaml`) | **Máy** (`autofix`: `rename_classes`) | Tên lớp viết hoa sai quy chuẩn (`'Person'`, `'Bus'`); máy ghi đè lại `names` theo đúng danh sách cố định `['car', 'person', 'truck', 'bus']`. |
| `BAD_FORMAT` | ERROR | 3 dòng (3/202 ảnh) | **Máy** (`autofix`: `drop_line`) | Dòng nhãn thiếu cột hoặc chứa `nan` (`img_0014`, `img_0022`, `img_0179`); vi phạm cú pháp YOLO nên máy xoá dòng hỏng. |
| `BAD_CLASS_ID` | ERROR | 6 dòng (6/202 ảnh) | **Máy** (`autofix`: `drop_line`) | ID lớp nằm ngoài `0..3` (`-1`, `4`, `7`, `93`); máy không thể tự đoán lớp đúng nên xoá dòng lỗi cú pháp và đẩy ảnh vào hàng đợi để người kiểm lại. |
| `BOX_ZERO` | ERROR | 4 dòng (4/202 ảnh) | **Máy** (`autofix`: `drop_line`) | Box có chiều rộng hoặc chiều cao `<= 0` (`img_0050`, `img_0066`, `img_0092`, `img_0185`); không có diện tích hợp lệ nên máy xoá dòng. |
| `DUP_BOX` | ERROR | 7 dòng (7/202 ảnh) | **Máy** (`autofix`: `drop_line`) | Hai box cùng lớp chồng khít lên nhau (`IoU > 0.90`); máy giữ dòng đầu và xoá dòng lặp phía sau. |
| `BOX_OUT_OF_IMAGE` | ERROR | 8 dòng (8/202 ảnh) | **Máy** (`autofix`: `clip_box`) | Mép box tràn khỏi `[0, 1]` vượt mức dung sai `0.002`; máy cắt (`clip`) mép box về biên `[0, 1]` (hoặc xoá dòng nếu phần còn lại không còn diện tích). |
| `MISSING_LABEL_FILE` | ERROR | 6 dòng (6/202 ảnh) | **Người** (`autofix` đánh dấu `needs_label`) | Ảnh hợp lệ nhưng mất file `.txt` (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`); máy không được tạo file rỗng hay bịa nhãn mà phải đẩy lên đầu hàng đợi cho người gán. |
| `EMPTY_LABEL` | WARN | 12 dòng (12/202 ảnh) | **Người** (hàng đợi duyệt) | File `.txt` rỗng: máy không phân biệt được đây là ảnh nền thật sự không có vật thể hay người gán bỏ quên, cần người xem lại. |
| `BOX_TINY` | WARN | 6 dòng (4/202 ảnh) | **Người** (hàng đợi duyệt) | Cạnh ngắn của box `< 12px` (sau khi clip ở vòng 2 tăng lên 7 dòng trên 5/202 ảnh); cần người xác nhận vật thể quá nhỏ có nên giữ theo guideline hay xoá. |
| `BOX_HUGE` | WARN | 3 dòng (3/202 ảnh) | **Người** (hàng đợi duyệt) | Box chiếm `> 95%` diện tích ảnh (`img_0018`, `img_0128`, `img_0196`); có thể là vật thể chụp cận cảnh hợp lệ hoặc box vẽ bao trùm sai. |
| `CLASS_RARE` | WARN | 4 dòng (`<dataset>`) | **Máy** (tự hết sau `autofix`) | Cảnh báo thống kê cấp tập dữ liệu do các ID rác (`-1`, `4`, `7`, `93`) chỉ có 1–2 box; sau khi `autofix` xoá các dòng `BAD_CLASS_ID`, cảnh báo này tự động biến mất ở vòng 2. |
| `POSSIBLE_WRONG_CLASS` | WARN | 18 dòng (18/202 ảnh) | **Người** (hàng đợi duyệt) | Nhãn lệch lớp so với dự đoán tự tin cao của `yolo26l` (`IoU >= 0.50`); model cũng có thể nhầm (vd. `truck` vs `bus`) nên chỉ cảnh báo để người quyết định. |
| `POSSIBLE_MISSING` | WARN | 53 dòng (52/202 ảnh) | **Người** (hàng đợi duyệt) | Model lớn thấy vật thể (`conf >= 0.60`, diện tích `>= 600px²`) nhưng nhãn không có box nào khớp (`IoU < 0.30`); cần người bổ sung nếu thiếu thật. |
| `POSSIBLE_LOOSE_BOX` | WARN | 28 dòng (24/202 ảnh) | **Người** (hàng đợi duyệt) | Cùng lớp với dự đoán của model nhưng `0.30 <= IoU < 0.50`; cần người chỉnh lại khung bao cho sát vật thể. |
| `POSSIBLE_FALSE_POS` | WARN | 25 dòng (24/202 ảnh) | **Người** (hàng đợi duyệt) | Box nhãn không khớp với bất kỳ dự đoán nào của model (`conf >= 0.10`); cần người kiểm tra xem là nhãn thừa hay vật thể khó mà model bỏ sót. |

### Cơ chế xếp hàng đợi (`05_review_queue.csv`) và độ phủ với ngân sách 80 ảnh
- **Vì sao `05_review_queue.csv` xếp các ảnh đầu hàng như vậy?** Hàm `review_queue.build_queue` tính điểm ưu tiên (`priority`) cho từng ảnh bằng tổng trọng số (`cfg["review"]["weights"]`) của mọi cảnh báo `WARN` trên ảnh đó (nhân với `1 + conf` nếu có độ tự tin của model), cộng thêm điểm cho các can thiệp tự động (`FIXED_DROP_LINE = 2`, `FIXED_CLIP_BOX = 1`) và đặc biệt cộng **`NEEDS_LABEL = 10`** cho ảnh thiếu file nhãn. Nhờ vậy:
  - Đứng thứ 1 là `img_0020` (`priority = 11.524`) do hội tụ nhiều dấu hiệu rủi ro cao cùng lúc: vừa bị xoá dòng lỗi (`FIXED_DROP_LINE`: +2), vừa bị nghi gán nhầm lớp (`POSSIBLE_WRONG_CLASS` với `conf = 0.95`: +5.85), vừa bị nghi thiếu nhãn (`POSSIBLE_MISSING` với `conf = 0.84`: +3.68).
  - Đứng vị trí thứ 2 đến thứ 7 là toàn bộ **6/6 ảnh thiếu file nhãn** (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219` với `priority = 10.0`). Việc đẩy nhóm này lên đầu đảm bảo người duyệt luôn gán nhãn cho chúng trước tiên, không để lỗi bắt buộc `MISSING_LABEL_FILE` làm chặn toàn bộ pipeline (Rework).
  - Các vị trí tiếp theo ưu tiên ảnh có nhiều lỗi ngữ nghĩa nặng (`POSSIBLE_WRONG_CLASS` trọng số 3, `POSSIBLE_MISSING` và `POSSIBLE_FALSE_POS` trọng số 2) hoặc vừa bị máy xoá dòng (`FIXED_DROP_LINE`) dẫn đến nguy cơ mất box của vật thể thật.
- **Với ngân sách 80 ảnh, người duyệt xem được bao nhiêu lỗi ngữ nghĩa?**
  Ở vòng 2 (`04_error_list_v2.csv`), toàn bộ 202 ảnh có **123 dòng cảnh báo ngữ nghĩa** (thuộc 4 mã `second_opinion`) nằm trên **103 ảnh** (trong tổng số 125 ảnh của hàng đợi). Với ngân sách duyệt **80 ảnh đầu hàng đợi**, người duyệt đã kiểm tra và xử lý được **94/123 dòng lỗi ngữ nghĩa (76,4%)**, tương ứng **74/103 ảnh (71,8%)** có cảnh báo ngữ nghĩa:
  - `POSSIBLE_WRONG_CLASS`: **18/18 dòng (100%)** — được duyệt toàn bộ.
  - `POSSIBLE_MISSING`: **51/53 dòng (96,2%)** — gần như toàn bộ các ca nghi thiếu box đều được xem.
  - `POSSIBLE_FALSE_POS`: **13/24 dòng (54,2%)**.
  - `POSSIBLE_LOOSE_BOX`: **12/28 dòng (42,9%)** — có trọng số thấp hơn (`1.5`) nên phần còn lại nằm ở cuối hàng đợi.

---

## 3. Calibration (2 ngưỡng)

Bảng kết quả trên tập `data/calib` (39 ảnh có đáp án trong `MANIFEST.csv`) trước và sau khi chọn ngưỡng:

| Tham số | Khởi đầu | Đã chọn | Precision / Recall / F1 (trước → sau) | Lý do (đánh đổi Precision – Recall) |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | `2` | **`10`** | `DUP_IMAGE_EXACT`: `1.00 / 1.00 / 1.00` → `1.00 / 1.00 / 1.00`<br>`DUP_IMAGE_NEAR`: `1.00 / 0.50 / 0.67` → **`1.00 / 0.67 / 0.80`** | Đây là bước máy tự động loại bỏ ảnh nên **Precision = 1.00 là ưu tiên tuyệt đối** (cờ sai = xóa mất ảnh huấn luyện tốt). Tăng từ `2` lên `10` giúp Recall trên `calib` tăng từ `0.50` (3/6) lên `0.67` (4/6) mà không sinh báo động giả nào; đồng thời trên `raw` bắt thêm đúng các cặp trùng biến đổi vừa (`dist = 6` và `dist = 10`). |
| `second_opinion.conf` | `0.25` | **`0.60`** | `WRONG_CLASS`: `0.56 / 0.83 / 0.67` → **`0.62 / 0.83 / 0.71`**<br>`MISSING`: `0.50 / 1.00 / 0.67` → **`0.57 / 1.00 / 0.73`**<br>`LOOSE_BOX`: `0.29 / 0.40 / 0.33` → `0.20 / 0.20 / 0.20`<br>`FALSE_POS`: `0.36 / 1.00 / 0.53` → `0.36 / 1.00 / 0.53` | Cảnh báo ngữ nghĩa đẩy ảnh vào hàng đợi có ngân sách hữu hạn (80 ảnh). Nâng `conf` từ `0.25` lên `0.60` giúp lọc bỏ các dự đoán nhiễu của model, nâng Precision của `WRONG_CLASS` (`0.56 → 0.62`) và `MISSING` (`0.50 → 0.57`), rút gọn hàng đợi trên `raw` từ 143 xuống 125 ảnh mà **không làm giảm Recall** của hai lỗi quan trọng nhất là `MISSING` (`1.00`) và `WRONG_CLASS` (`0.83`). Nếu tăng tiếp lên `0.70` hoặc `0.80`, Recall của `MISSING` bị tụt xuống `0.88` và `0.75` (bỏ sót 25% vật thể thiếu nhãn). |

### Điểm đánh lừa của Calibration và bằng chứng thực nghiệm trên dữ liệu
1. **Bẫy tối ưu F1 của `phash_dist = 16` trên tập `calib` nhỏ làm xóa nhầm hàng loạt ảnh tốt trên `raw`:**
   - Nếu chỉ nhìn bảng sweep trong `submission/calibration/calibration_report.md`, tại `duplicates.phash_dist = 16`, chỉ số `DUP_IMAGE_NEAR` đạt đỉnh với `Precision = 1.00, Recall = 0.83, F1 = 0.91` (bắt thêm được `calib_037` có `dist = 16`).
   - Tuy nhiên, có **hai chỗ đánh lừa** ở đây:
     - Thứ nhất, `calibrate.py` chỉ chấm mã `DUP_IMAGE_EXACT` và `DUP_IMAGE_NEAR` mà không đưa `LEAK_TEST` vào bảng sweep. Ngay trên tập `calib`, khi đặt `phash_dist = 16`, ảnh `calib_027` đã bị bắt nhầm là `LEAK_TEST` với `test/test_027.jpg` (do trùng ngẫu nhiên khoảng cách Hamming 16 bit), làm giảm số ảnh sạch mà bảng Precision của `DUP_IMAGE_NEAR` không hề phản ánh.
     - Thứ hai, tập `calib` chỉ có 39 ảnh (số cặp so sánh nhỏ), trong khi tập `raw` có **224 ảnh** so chéo với nhau và so với **140 ảnh** trong `data/test` + `data/gold_val` (~55.000 cặp so sánh). Khi thử đặt `phash_dist = 16` trên `raw`, số ảnh bị báo trùng/rò rỉ vọt từ **17 ảnh** (ở `phash_dist = 10`) lên **26 ảnh** (tăng thêm **9 ảnh bị loại oan**).
   - **Bằng chứng mở xem ảnh thực tế trên `raw`:**
     - Ở `phash_dist = 10`, cả 4 cặp `DUP_IMAGE_NEAR` bị loại đều là ảnh trùng thật: `img_0076` vs `img_0042` (`dist = 0`), `img_0143` vs `img_0037` (`dist = 0`), `img_0223` (375×309) vs `img_0077` (500×412, `dist = 6`), và `img_0186` (640×425) vs `img_0061` (544×361, `dist = 10` — cùng bức ảnh người phụ nữ ngồi trên ghế gỗ ngoài công viên nhìn từ phía sau, chỉ khác độ sáng và tỉ lệ cắt). Năm ảnh `LEAK_TEST` (`img_0049`, `img_0101`, `img_0167`, `img_0174`, `img_0221`) cũng trùng khớp thật với tập `test`.
     - Ngược lại, các cặp phát sinh thêm ở `phash_dist = 16` hoàn toàn là **hai bức ảnh khác nhau**: ví dụ `img_0008.jpg` (hai người trượt tuyết trên sườn núi tuyết trắng) bị coi là trùng với `img_0011.jpg` (vận động viên quần vợt mặc đồ hồng trên sân xanh, `phash = 16`); và `img_0013.jpg` (bàn làm việc có 3 chiếc laptop) bị coi là rò rỉ `LEAK_TEST` với `test/test_087.jpg` (trận đấu bóng chày trên sân cỏ, `phash = 16`). Vì vậy, dừng ở `phash_dist = 10` là lựa chọn đúng đắn.
2. **Bẫy chọn `second_opinion.conf = 0.80` để đạt "Release giả":**
   - Nếu chọn `conf = 0.80`, số ảnh còn cảnh báo chưa duyệt sau 80 ảnh trên `raw` giảm xuống `16/202 (7,92% < 10%)`, giúp pipeline báo **Release**. Nhưng đó là **Release giả** vì ngưỡng quá cao làm bộ kiểm bị "mù" trước các vật thể bị bỏ sót mà model dự đoán với độ tự tin `0.60–0.79` (khiến Recall của `POSSIBLE_MISSING` trên `calib` sụt từ `1.00` xuống `0.75`).

---

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

### (a) Chứng minh cửa chặn (`gate`) thực sự chặn khi còn lỗi bắt buộc
Chạy thử nghiệm tắt ngân sách người duyệt để giữ nguyên các lỗi bắt buộc mà máy không tự sửa được (`MISSING_LABEL_FILE`):
```bash
python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb
```
- **Kết quả thực tế:**
  - Ở vòng 1 và vòng 2, pipeline phát hiện **6/202 ảnh** không có file nhãn (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`). `autofix` chỉ ghi nhận `action = needs_label` chứ không tự tạo file `.txt` rỗng.
  - Khi `--budget 0`, không có người duyệt nào gán nhãn cho 6 ảnh này. Do đó ở vòng 3 (`work/rep_nb/07_error_list_v3.txt`), danh sách lỗi vẫn còn nguyên **6 lỗi mức `ERROR` (`MISSING_LABEL_FILE`)**.
  - Cửa chặn (`gate.decide`) lập tức trả về kết luận **`Rework`** (`n_errors = 6`, lý do: `"còn 6 lỗi bắt buộc chưa được xử lý"`), chương trình kết thúc với **mã thoát `20`**, in rõ `"Bước 5/5 KHÔNG xuất: còn lỗi bắt buộc (Rework) — trả về bước 3"`, và thư mục `work/exp_nb/clean_v1` **hoàn toàn không tồn tại** (`exported: null` trong `work/rep_nb/08_summary.json`).

### (b) Các điểm mù mà pipeline KHÔNG bắt được (kèm bằng chứng)
1. **Ảnh trùng gần đúng nhưng bị cắt cúp hoặc biến đổi hình học mạnh (`phash_dist > 10`):**
   - *Bằng chứng:* Trong tập `data/raw`, cặp ảnh `img_0074.jpg` (352×470) và `img_0084.jpg` (480×640) chụp cùng một người phụ nữ đội ô trắng giữa đám đông nhưng khác khung cắt và tỷ lệ khung hình, làm khoảng cách băm cảm nhận vọt lên `phash_dist = 16`. Tương tự trên tập `data/calib`, ảnh `calib_037` (biến đổi mức 3 của `calib_015`) có `phash_dist = 16` và `calib_038` (biến đổi mức 4 của `calib_024`) có `phash_dist = 18`. Do không thể nâng `phash_dist` lên `16–18` (sẽ gây xoá nhầm các ảnh khác nhau như `img_0008` vs `img_0011`), các cặp trùng biến đổi mạnh này lọt qua bước `duplicates`.
2. **Lỗi ngữ nghĩa / box lỏng ở những vật thể mà chính model lớn (`yolo26l`) dự đoán sai hoặc có độ tự tin thấp:**
   - *Bằng chứng:* Trong `data/calib/MANIFEST.csv` có 5 lỗi `LOOSE_BOX` chèn sẵn, nhưng `second_opinion` chỉ bắt được 1/5 ca (`calib_023` dòng 2, `IoU = 0.425, conf = 0.926`). Bốn ca còn lại lọt lưới vì:
     - Ở `calib_006` (dòng 1, `scale = 1.48`), model `yolo26l` hoàn toàn không phát hiện được chiếc xe đó trong cache dự đoán.
     - Ở `calib_012` (dòng 1, `IoU = 0.465`) và `calib_024` (dòng 1, `IoU = 0.336`), dự đoán của `yolo26l` chỉ đạt độ tự tin thấp (`conf = 0.1545` và `conf = 0.3664`), thấp hơn ngưỡng `conf = 0.60` nên bị bỏ qua.
     - Ở `calib_002` (dòng 3, nhãn gốc là `3: bus` bị phình `scale = 1.54`), model `yolo26l` lại dự đoán vật thể đó là `2: truck` (`conf = 0.2875, IoU = 0.421`). Vì khác lớp và `IoU = 0.421` nằm trong vùng mơ hồ `[iou_missing=0.30, iou_match=0.50)`, thuật toán giữ im lặng nên cả lỗi lệch lớp lẫn lỗi box lỏng đều không bị cờ.
3. **Box lỏng mức vừa phải (`0.50 <= IoU < 0.75`) và vật thể ở xa có diện tích nhỏ (`< 600 px²`):**
   - *Bằng chứng:* Quy tắc cấu hình cố định `second_opinion.iou_loose = 0.50` và `min_area_px = 600`. Khi quan sát các ảnh vẽ nhãn trong `work/viz/` (như `img_0001.png`, `img_0025.png`), những box bao quanh người/xe hơi bị dư viền nhưng vẫn đạt `IoU` khoảng `0.55–0.65` với dự đoán của `yolo26l` đều được coi là "khớp tốt" và không báo cảnh báo. Đồng thời, các người đi bộ hoặc xe ở xa có diện tích `< 600 px²` (ví dụ `20×25 px = 500 px²`) bị lọc bỏ trước khi so sánh nên nếu người gán bỏ sót thì pipeline cũng không phát hiện được.

---

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
- **Trạng thái:** **Chưa chạy** (`--no-train`).
- **Lý do:** Máy thực hiện bài Lab hiện chỉ có CPU (`torch.cuda.is_available() == False`), chưa kết nối phiên GPU T4 trên Google Colab để chạy `scripts/train_compare.py` cho 2 biến thể × 2 seed × 20 epoch. Bản xuất nháp `submission/export/clean_v1/` (kèm `manifest.json` và `data.yaml`) đã được tạo đầy đủ và sẵn sàng để chạy huấn luyện đối chứng trên Colab.

---

## 6. Quyết định và ghi chú AI

### (a) Quyết định cuối và điều kiện để chuyển sang Release
- **Quyết định cuối cùng:** **Hold** — giữ bộ dữ liệu ở trạng thái bản nháp (`submission/export/clean_v1/`), **chưa phát hành chính thức** cho sản xuất.
- **Cần làm gì để thành Release?**
  - Hiện tại `n_errors = 0` (toàn bộ lỗi cú pháp và 6 ảnh mất nhãn đã được giải quyết triệt để), nhưng còn **38/202 ảnh (18,81%)** có cảnh báo chưa được người duyệt (nằm ở vị trí 81–125 của `05_review_queue.csv`, cộng với các ảnh cảnh báo nhẹ).
  - Để tỉ lệ ảnh còn cảnh báo chưa duyệt giảm xuống **dưới ngưỡng `10%`** (`< 20,2` ảnh, tức tối đa **19/202 ảnh = 9,41%**), dự án cần **cấp thêm ngân sách duyệt cho ít nhất 19 ảnh nữa** trong hàng đợi `05_review_queue.csv` (nâng tổng số ảnh người duyệt từ `80` lên tối thiểu **`99 ảnh`**, hoặc duyệt hết toàn bộ **`45 ảnh`** còn lại trong hàng đợi 125 ảnh để đạt `0%` cảnh báo tồn đọng). Sau khi người duyệt sửa xong các ảnh này và chạy lại `--resume-after-review`, cổng `gate` sẽ chính thức đạt **Release** (mã thoát `0`).

### (b) Ghi chú sử dụng AI
1. **Prompt chính đã dùng (đủ 4 ý theo quy tắc):**
   > *"Viết hàm `run(ds, cfg)` cho `pipeline/checks/label_format.py` và `pipeline/checks/second_opinion.py` đọc dữ liệu từ đối tượng `Dataset` (1 - định dạng vào: mỗi dòng nhãn YOLO gồm 5 cột `id cx cy w h` chuẩn hoá 0–1 lấy qua `ds.read_label_lines(stem)`, dự đoán model dạng `[cls, conf, cx, cy, w, h]`). Kiểm tra các quy tắc cú pháp (`BAD_FORMAT`, `BAD_CLASS_ID`, `BOX_ZERO`, `BOX_OUT_OF_IMAGE`, `DUP_BOX`, `BOX_TINY`, `BOX_HUGE`) và đối chiếu IoU với model lớn theo ngưỡng trong `cfg` (2 - quy tắc kiểm). Trả về `list[Issue]` với đúng `severity`, `code`, `image`, `line` đếm từ 1 và `extra` (3 - kiểu đầu ra). Tuyệt đối chỉ đọc từ `ds` và `cfg`, không sửa/xoá file gốc, không viết cứng ngưỡng (4 - giới hạn an toàn)."*
2. **Cách kiểm tra code:**
   - Đọc rà soát từng dòng đảm bảo không có lệnh ghi/xoá trên `data/raw` và mọi ngưỡng đều đọc từ `cfg`.
   - Chạy toàn bộ 79 unit test + e2e test (`python -m pytest -q`), tự viết thêm kịch bản kiểm thử 3 ca biên (1 dòng nhãn dính đồng thời 2 lỗi `BOX_OUT_OF_IMAGE` + `DUP_BOX`; file nhãn có nhiều dòng trống xen kẽ dòng lỗi ở đầu/giữa/cuối; 1 ảnh có đồng thời 4 loại dự đoán tương ứng `LOOSE_BOX`, `WRONG_CLASS`, `MISSING`, `FALSE_POS`), và kiểm tra chéo độ chính xác trên tập `data/calib` qua `pipeline.calibrate`.
3. **Một lần phát hiện lỗi logic và cách sửa:**
   - Khi kiểm tra `second_opinion.py` trên tập `data/calib`, ở bước lọc các dòng nhãn hợp lệ (`valid_labels`) để tìm `POSSIBLE_FALSE_POS`, nếu chỉ kiểm tra `parse_yolo_line` và `0 <= cls_id < len(ds.classes)` (giống `ds.valid_boxes`) mà quên kiểm tra `w > 0 and h > 0`, thì 2 dòng lỗi `BOX_ZERO` trong `calib_011.txt` (dòng 2, `w = 0`) và `calib_012.txt` (dòng 2, `h = 0`) sẽ có `IoU = 0.0 < iou_missing` với mọi dự đoán và bị báo nhầm thêm lỗi `POSSIBLE_FALSE_POS` (làm giảm Precision trên tập `calib`). Tôi đã phát hiện qua bảng `calibrate` và sửa lại bằng cách chỉ đưa các dòng có `w > 0 and h > 0` vào `valid_labels` trong `second_opinion.py`, đồng thời ở `autofix.py` bổ sung kiểm tra nếu sau khi `clip_box` mà `nw <= 1e-6` hoặc `nh <= 1e-6` thì chuyển thành `drop_line` để không tạo ra `BOX_ZERO` ở vòng QC kế tiếp.

---

### *(Phần thưởng tùy chọn +2)* Đối chiếu bộ lọc CVAT (`width < 20`) với `BOX_TINY` và thuộc tính `can_review`
- **Kết quả lọc `width < 20` px so với `BOX_TINY` (`cạnh ngắn < 12` px) của pipeline:**
  - Trên bộ dữ liệu làm việc `work/run/ds` (202 ảnh sau bước nhận và sửa tự động), khi áp dụng quy tắc lọc `width < 20` px của CVAT, có tất cả **51 box trên 26 ảnh** khớp bộ lọc (nếu tính trong 20 ảnh đầu hàng đợi `05_review_queue.csv` thì có **2 ảnh khớp** với tổng cộng **6 box**: `img_0020` có 4 box ở các dòng 4, 5, 6, 7 với chiều rộng `19.5px, 16.8px, 15.0px, 16.4px`; và `img_0030` có 2 box ở dòng 5, 9 với chiều rộng `19.5px, 9.8px`). Nếu lọc cả hai chiều `min(width, height) < 20` px thì có **60 box trên 28 ảnh**.
  - Trong khi đó, cảnh báo `BOX_TINY` của pipeline (dùng ngưỡng dự án `min_box_px = 12` px tính trên cạnh ngắn `min(w*W, h*H) < 12`) chỉ gắn cờ **7 box trên 5 ảnh** ở vòng 2 (`img_0026` dòng 6: `11.4×29.8px`; `img_0030` dòng 9: `9.8×84.3px`; `img_0051` dòng 5: `8.9×44.1px`; `img_0069` dòng 2: `11.2×31.6px`; và `img_0161` dòng 2, 3, 4: `10.3×32.3px`, `11.4×43.8px`, `11.9×43.6px`). Cả 5 ảnh `BOX_TINY` này đều là tập con nằm trọn trong kết quả lọc `< 20px` của CVAT, vì ngưỡng `12px` của pipeline chặt hơn ngưỡng `20px` minh hoạ trong slide (nhằm tránh làm ngập hàng đợi duyệt bằng các vật thể ở xa có kích thước `12–20px` vẫn nhận diện được).
- **Ý nghĩa của thuộc tính `can_review` trong `cvat/labels.json`:**
  - Người gán nhãn (annotator) bật thuộc tính checkbox `can_review = true` trên CVAT khi gặp những vật thể khó, bị che khuất, mờ nhoè hoặc phân vân giữa hai lớp (ví dụ `truck` và `bus`) để đánh dấu nhờ người duyệt (reviewer) kiểm tra lại bằng bộ lọc `attr["can_review"]==true`; trong pipeline tự động của chúng ta, vai trò tương đương được thực hiện bởi module `second_opinion` và `review_queue` khi dùng độ bất đồng giữa nhãn với model lớn (`POSSIBLE_WRONG_CLASS`, `POSSIBLE_MISSING`, `POSSIBLE_LOOSE_BOX`, `POSSIBLE_FALSE_POS`) kèm độ tự tin `conf` để tự động gắn cờ và xếp thứ tự ưu tiên vào `05_review_queue.csv` cho người duyệt.
