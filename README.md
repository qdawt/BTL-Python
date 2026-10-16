# Web NBA 2024-25 (Streamlit)

Web chỉ đọc các file có sẵn trong repo (phan1/results.csv, phan2/output/*.csv, phan3/*.csv), không gọi lại crawl.py.

## Chạy trên máy
```
pip install -r web/requirements.txt
streamlit run web/app.py
```
(chạy từ thư mục gốc của repo, nơi có phan1/, phan2/, phan3/)

## Deploy trên Streamlit Community Cloud (không bắt buộc)
- Main file path: `web/app.py`
- Dependency file `web/requirements.txt` sẽ được tự nhận.

## Các trang
1. Tra cứu cầu thủ: lọc theo tên, đội, vị trí, số phút; xem chi tiết một cầu thủ.
2. So sánh radar: chọn hai cầu thủ và các thống kê (chuẩn hóa min-max toàn giải).
3. Phân cụm cầu thủ: biểu đồ PCA, hồ sơ cụm, Elbow/Silhouette (đọc từ phan3/).
4. Thống kê đội: đội dẫn đầu theo từng thống kê, top 3 cầu thủ, histogram (đọc từ phan2/).
