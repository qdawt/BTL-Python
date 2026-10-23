# PHẦN 2 – PHÂN TÍCH DỮ LIỆU CẦU THỦ NBA

## 1. Giới thiệu

Phần 2 của bài tập lớn Python thực hiện phân tích thống kê dữ liệu cầu thủ NBA dựa trên tập dữ liệu `results.csv` được thu thập và xử lý ở Phần 1.

Chương trình sử dụng thư viện **Pandas** để xử lý, thống kê dữ liệu và **Matplotlib** để trực quan hóa các chỉ số của cầu thủ dưới dạng biểu đồ Histogram.

### Các chức năng chính

- Đọc, kiểm tra và chuẩn hóa dữ liệu từ file CSV.
- Tìm 3 cầu thủ có giá trị cao nhất và thấp nhất ở từng chỉ số thống kê.
- Tính Median, Mean và Standard Deviation cho toàn bộ cầu thủ và từng đội bóng.
- Vẽ biểu đồ Histogram thể hiện phân bố các chỉ số của toàn bộ cầu thủ.
- Vẽ biểu đồ Histogram so sánh phân bố 6 chỉ số tiêu biểu giữa các đội bóng.
- So sánh các đội bóng dựa trên giá trị trung bình của từng chỉ số.
- Xuất kết quả phân tích thành các file CSV và PNG.

## 2. Công nghệ sử dụng

- **Python 3**
- **Pandas:** Đọc, xử lý và phân tích dữ liệu.
- **Matplotlib:** Vẽ biểu đồ thống kê.
- **Pathlib:** Quản lý đường dẫn đến các file và thư mục.

## 3. Cấu trúc thư mục

```text
BTL-Python/
├── phan1/
│   └── results.csv
│
└── phan2/
    ├── analysis.py
    ├── README.md
    └── output/
        ├── results2.csv
        ├── top_botton.csv
        ├── missing_values.csv
        ├── team_means.csv
        ├── team_comparison.csv
        ├── team_report.csv
        │
        ├── Histograms_all/
        │   └── *.png
        │
        └── Histograms_teams/
            ├── 01_PTS.png
            ├── 02_TRB.png
            ├── 03_AST.png
            ├── 04_TS%.png
            ├── 05_USG%.png
            └── 06_BPM.png
```

Các thư mục và file kết quả được chương trình tự động tạo khi chạy.

## 4. Hướng dẫn cài đặt và chạy chương trình

### Bước 1: Cài đặt thư viện

```bash
pip install pandas matplotlib
```

### Bước 2: Chuẩn bị dữ liệu

Đảm bảo file dữ liệu đầu vào nằm tại:

```text
phan1/results.csv
```

Dữ liệu phải chứa các cột cần thiết, bao gồm:

`Player`, `Team`, `MP`, `PTS`, `TRB`, `AST`, `TS%`, `USG%`, `BPM`, `WS`, `TOV`, `PF`, `DRtg`.

Chương trình yêu cầu các cầu thủ có số phút thi đấu `MP > 200`.

### Bước 3: Chạy chương trình

Từ thư mục gốc của dự án:

```bash
python3 phan2/analysis.py
```

Sau khi chạy thành công, kết quả được lưu tại:

```text
phan2/output/
```

## 5. Nội dung phân tích

### 5.1. Kiểm tra và xử lý dữ liệu

Chương trình thực hiện:

- Kiểm tra sự tồn tại của file CSV.
- Kiểm tra các cột bắt buộc.
- Kiểm tra dữ liệu rỗng và tên cầu thủ, đội bóng bị thiếu.
- Chuyển đổi các cột thống kê sang kiểu dữ liệu số.
- Chuyển các giá trị không hợp lệ thành `NaN`.
- Kiểm tra điều kiện số phút thi đấu `MP > 200`.
- Thống kê số lượng giá trị thiếu trong từng cột.

Kết quả được lưu trong `missing_values.csv`.

### 5.2. Tìm Top 3 và Bottom 3 cầu thủ

Với mỗi chỉ số thống kê, chương trình sử dụng:

- `nlargest(3, stat)` để tìm 3 cầu thủ có giá trị cao nhất.
- `nsmallest(3, stat)` để tìm 3 cầu thủ có giá trị thấp nhất.

Các dòng thiếu dữ liệu ở chỉ số đang xét được loại bỏ trước khi xếp hạng.

Kết quả được lưu trong `top_botton.csv`, gồm các thông tin:

| Cột | Ý nghĩa |
|---|---|
| Statistic | Chỉ số thống kê |
| Category | Nhóm cao nhất hoặc thấp nhất |
| Rank | Thứ hạng |
| Player | Tên cầu thủ |
| Team | Đội bóng |
| Value | Giá trị chỉ số |

### 5.3. Tính toán các đặc trưng thống kê

Chương trình tính ba đại lượng thống kê cho toàn bộ cầu thủ và từng đội bóng:

- **Median (Trung vị):** Giá trị nằm giữa tập dữ liệu sau khi sắp xếp.
- **Mean (Trung bình):** Tổng các giá trị chia cho số lượng quan sát hợp lệ.
- **Standard Deviation (Độ lệch chuẩn):** Đo mức độ phân tán của dữ liệu quanh giá trị trung bình.

Độ lệch chuẩn được tính theo công thức mẫu với `ddof=1`.

Các giá trị thiếu (`NaN`) không được đưa vào phép tính.

Kết quả được lưu trong `results2.csv`.

### 5.4. Histogram của toàn bộ cầu thủ

Chương trình vẽ biểu đồ Histogram cho từng chỉ số thống kê dạng số.

Mỗi biểu đồ thể hiện:

- Trục X: Giá trị của chỉ số.
- Trục Y: Số lượng cầu thủ thuộc từng khoảng giá trị.
- Số lượng cầu thủ trên mỗi cột Histogram.
- Tổng số cầu thủ có dữ liệu hợp lệ của chỉ số.

Các biểu đồ được lưu trong thư mục:

```text
output/Histograms_all/
```

### 5.5. Histogram theo từng đội bóng

Chương trình phân tích 6 chỉ số tiêu biểu:

| Chỉ số | Ý nghĩa |
|---|---|
| PTS | Điểm ghi được |
| TRB | Tổng số lần bắt bóng bật bảng |
| AST | Số lần kiến tạo |
| TS% | Tỷ lệ ném rổ hiệu quả thực |
| USG% | Tỷ lệ sử dụng các tình huống tấn công |
| BPM | Chỉ số Box Plus/Minus |

Đối với mỗi chỉ số:

- Tạo một hình gồm các biểu đồ Histogram của từng đội.
- Mỗi đội được biểu diễn trong một ô riêng.
- Các biểu đồ sử dụng chung thang đo trục X và Y để thuận tiện so sánh.
- Mỗi Histogram sử dụng 10 khoảng giá trị (`bins=10`).
- Mỗi hình được lưu thành file PNG.

Kết quả được lưu trong:

```text
output/Histograms_teams/
```

### 5.6. So sánh chỉ số trung bình giữa các đội bóng

Chương trình nhóm cầu thủ theo đội bằng `groupby("Team")`, sau đó tính trung bình từng chỉ số.

Các kết quả bao gồm:

**team_means.csv**

Lưu giá trị trung bình của tất cả các chỉ số thống kê theo từng đội bóng.

**team_comparison.csv**

Xác định:

- Đội có giá trị trung bình cao nhất.
- Đội có giá trị trung bình thấp nhất.
- Đội được lựa chọn theo quy tắc đánh giá chỉ số.

Đối với các chỉ số `TOV`, `PF`, `DRtg`, chương trình lựa chọn giá trị nhỏ nhất. Với các chỉ số còn lại, chương trình lựa chọn giá trị lớn nhất.

**team_report.csv**

Tổng hợp giá trị trung bình của 9 chỉ số tiêu biểu:

`PTS`, `TRB`, `AST`, `TS%`, `BPM`, `WS`, `TOV`, `PF`, `DRtg`.

## 6. Các file kết quả

| File / Thư mục | Nội dung |
|---|---|
| `missing_values.csv` | Số lượng dữ liệu thiếu của từng cột |
| `top_botton.csv` | Top 3 và Bottom 3 cầu thủ theo từng chỉ số |
| `results2.csv` | Median, Mean và Std của toàn bộ cầu thủ và từng đội |
| `team_means.csv` | Giá trị trung bình các chỉ số của từng đội |
| `team_comparison.csv` | So sánh giá trị trung bình cao nhất, thấp nhất giữa các đội |
| `team_report.csv` | Bảng tổng hợp 9 chỉ số tiêu biểu của các đội |
| `Histograms_all/` | Biểu đồ phân bố chỉ số của toàn bộ cầu thủ |
| `Histograms_teams/` | Biểu đồ phân bố 6 chỉ số theo từng đội |

## 7. Lưu ý

- Dữ liệu đầu vào phải được chuẩn bị trước ở Phần 1.
- Chương trình chỉ chấp nhận dữ liệu có `MP > 200`.
- Các giá trị thiếu được bỏ qua trong quá trình tính toán thống kê.
- Histogram giúp quan sát sự phân bố dữ liệu, không trực tiếp xác định đội bóng mạnh nhất.
- Việc so sánh đội bóng dựa trên trung bình chỉ số cầu thủ, không phải thống kê thành tích thi đấu thực tế của cả đội.
- Các chỉ số thống kê có thể có đơn vị và ý nghĩa khác nhau, vì vậy cần xem xét từng chỉ số riêng biệt khi đánh giá kết quả.

## 8. Kết luận

Phần 2 giúp tổng hợp và trực quan hóa dữ liệu cầu thủ NBA thông qua các phương pháp thống kê mô tả.

Kết quả phân tích cho phép quan sát sự phân bố của từng chỉ số, xác định những cầu thủ có giá trị thống kê nổi bật và so sánh các đặc điểm thống kê giữa các đội bóng.

Các kết quả được xuất dưới dạng CSV và PNG, thuận tiện cho việc kiểm tra, trình bày và xây dựng báo cáo bài tập lớn.