
# Phần 2: Phân tích dữ liệu cầu thủ NBA

Phân tích dữ liệu trong `phan1/results.csv` bằng Python.

## Chức năng

- Tìm 3 cầu thủ có giá trị cao nhất và thấp nhất cho mỗi chỉ số số.
- Tính trung vị (median), trung bình (mean) và độ lệch chuẩn (std)
  trên toàn bộ cầu thủ và theo từng đội.
- Vẽ histogram cho các chỉ số trên toàn bộ cầu thủ.
- Vẽ histogram theo đội cho 6 chỉ số:
  PTS, TRB, AST, TS%, USG%, BPM.
- Với mỗi chỉ số được chọn, ghép biểu đồ của 30 đội vào một ảnh.

## Cấu trúc thư mục

- `phan1/results.csv`: dữ liệu đầu vào do phần 1 thu thập.
- `phan2/analysis.py`: chương trình phân tích.
- `phan2/output/`: các bảng kết quả và ảnh biểu đồ.

## Thư viện cần thiết

Cài pandas và matplotlib trong môi trường Python đang sử dụng:

```bash
python3 -m pip install pandas matplotlib
```

## Cách chạy

Từ thư mục gốc `BTL-Python`:

```bash
python3 phan2/analysis.py
```

Hoặc từ thư mục `phan2`:

```bash
python3 analysis.py
```

## Kết quả

Kết quả được lưu trong `phan2/output/`:

| File hoặc thư mục | Nội dung |
|---|---|
| `top_bottom.csv` | 3 cầu thủ cao nhất và thấp nhất cho mỗi chỉ số |
| `results2.csv` | Median, mean và std của toàn bộ cầu thủ và từng đội |
| `Histograms_all/` | Histogram trên toàn bộ cầu thủ |
| `Histograms_teams/` | Histogram theo đội cho 6 chỉ số được chọn |

## Cách xử lý dữ liệu

- Bỏ qua giá trị thiếu khi tính toán và vẽ biểu đồ; không thay bằng 0.
- Độ lệch chuẩn được tính theo công thức mẫu (`ddof=1`).
- Dòng `all` trong `results2.csv` sử dụng dữ liệu toàn bộ cầu thủ.
- Dòng của mỗi đội sử dụng dữ liệu các cầu thủ thuộc đội đó trong CSV.
- Các đội dùng chung mốc chia histogram cho cùng một chỉ số để dễ so sánh.

Các thống kê theo đội mô tả dữ liệu cầu thủ trong CSV,
không phải thống kê thi đấu chính thức của cả đội.