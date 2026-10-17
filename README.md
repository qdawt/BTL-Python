# BTL Python – Phân tích dữ liệu cầu thủ NBA mùa giải 2024-25

Bài tập lớn Python: thu thập, phân tích, phân cụm và định giá cầu thủ NBA
từ dữ liệu [Basketball-Reference](https://www.basketball-reference.com/).

**Web demo:** https://btl-python-jkb6yyrkfpdq2ebgxkc3rq.streamlit.app/

## Cấu trúc thư mục

```
.
├── app.py                  # Ứng dụng web Streamlit (5 trang)
├── requirements.txt        # Thư viện cho web (Streamlit Cloud đọc file này)
├── requirements-analysis.txt  # Thư viện cho các script phân tích
├── phan1/                  # Bài 1: thu thập dữ liệu
│   ├── crawl.py
│   └── results.csv         # Thống kê cầu thủ (MP > 200)
├── phan2/                  # Bài 2: thống kê & biểu đồ
│   ├── analysis.py
│   └── output/             # CSV tổng hợp + histogram
├── phan3/                  # Bài 3: K-means, PCA, radar
│   ├── kmeans_pca.py
│   ├── radarChartPlot.py
│   └── *.csv, *.png
└── phan4/                  # Bài 4: định giá cầu thủ theo lương
    ├── valuation.py
    └── output/             # kết quả sau khi chạy valuation.py
```

## Cài đặt

```bash
pip install -r requirements.txt            # chỉ để chạy web
pip install -r requirements-analysis.txt   # để chạy các script phân tích
```

## Cách chạy từng phần

| Phần | Lệnh | Kết quả |
|------|------|---------|
| Bài 1 | `python phan1/crawl.py` | `phan1/results.csv` |
| Bài 2 | `python phan2/analysis.py` | `phan2/output/` |
| Bài 3 | `python phan3/kmeans_pca.py` | CSV và ảnh trong `phan3/` |
| Radar | `python phan3/radarChartPlot.py --p1 "Nikola Jokić" --p2 "Shai Gilgeous-Alexander" --Attribute PTS,TRB,AST,STL,BLK,TS%` | `radar.png` |
| Bài 4 | `python phan4/valuation.py` | `phan4/output/` |

Nên chạy các script từ thư mục gốc của repo (riêng `phan4/valuation.py` tự đọc `../phan1/results.csv`).
Bài 4 cần truy cập mạng để lấy bảng lương; Basketball-Reference có thể chặn truy cập tự động,
khi đó hãy thử mạng khác hoặc cài thêm `cloudscraper`.

## Chạy web Streamlit

```bash
streamlit run app.py
```
`https://btl-python-jkb6yyrkfpdq2ebgxkc3rq.streamlit.app/`

Web có 5 trang: tra cứu cầu thủ, biểu đồ radar, phân cụm (K-means/PCA), so sánh đội,
**Định giá & Lương**. Trang Định giá & Lương chỉ hiển thị kết quả sau khi đã có
`phan4/output/`: chạy `python phan4/valuation.py`, sau đó commit và push thư mục
`phan4/output/` lên GitHub rồi tải lại web.

## Triển khai trên Streamlit Community Cloud

1. Đăng nhập [share.streamlit.io](https://share.streamlit.io) bằng tài khoản GitHub.
2. Chọn repo này, nhánh `main`.
3. **Main file path: `app.py`** (không dùng `crawl.py` hay file trong thư mục khác).
4. Cloud tự cài thư viện từ `requirements.txt` (chỉ gồm streamlit, pandas, numpy, matplotlib).

## Ghi chú dữ liệu

- Cầu thủ chuyển đội trong mùa được gộp theo Player-ID (dòng 2TM/3TM/TOT), chỉ giữ cầu thủ có MP > 200.
- Giá trị thiếu ghi là `N/a`; file CSV mã hóa `utf-8-sig`.
- Các cột Birth, Height, Weight hiện chưa có dữ liệu (toàn `N/a`).
- Lương dự đoán lấy từ mô hình hồi quy trên log(lương); chênh lệch = lương thực tế − lương dự đoán
  (dương = overpaid, âm = underpaid).

## Thành viên nhóm

Danh sách 10 thành viên: (điền tên và MSSV).
