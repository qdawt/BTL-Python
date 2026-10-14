import argparse
import sys
from pathlib import Path
 
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
 
 
def read_csv_safe(path):
    """Đọc results.csv; thử UTF-8 (có/không BOM) rồi tới cp1252 (CSV lưu từ Excel)."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("không đọc được file CSV (lỗi bảng mã).")
 
 
# Các thống kê dùng để phân cụm (đều là số, ít bị trùng lặp thông tin)
FEATURES = [
    "PTS", "TRB", "AST", "STL", "BLK", "TOV", "PF",
    "FG%", "3P", "3PA", "FT", "FTA", "eFG%", "TS%", "USG%", "PER",
    "ORB%", "DRB%", "AST%", "STL%", "BLK%", "TOV%", "WS/48", "BPM",
]
 
 
HERE = Path(__file__).resolve().parent  # thư mục chứa file code (phan3)
 
 
def find_data():
    """results.csv nằm ở ../phan1/ (hoặc cùng thư mục với file code)."""
    for p in (HERE.parent / "phan1" / "results.csv", HERE / "results.csv"):
        if p.exists():
            return p
    return HERE.parent / "phan1" / "results.csv"
 
 
DATA_FILE = find_data()
 
 
def load_data(path):
    df = read_csv_safe(path)
    # Giá trị lỗi như "N/a" -> NaN, ép toàn bộ cột thống kê về số
    for c in FEATURES:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
 
 
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DATA_FILE), help="file dữ liệu CSV")
    ap.add_argument("--k", type=int, default=4, help="số cụm K-means")
    ap.add_argument("--top", type=int, default=2,
                    help="số cầu thủ nổi bật được chú thích ở mỗi cụm")
    ap.add_argument("--out", default=str(HERE / "pca_image.png"), help="file ảnh đầu ra")
    args = ap.parse_args()
 
    try:
        df = load_data(args.data)
    except FileNotFoundError:
        sys.exit(f"Lỗi: không tìm thấy file '{args.data}'.")
    except KeyError as e:
        sys.exit(f"Lỗi: file thiếu cột {e}.")
 
    # 1) Chuẩn hóa: thay NaN bằng trung vị rồi đưa về mean=0, std=1
    X = df[FEATURES].fillna(df[FEATURES].median())
    X_std = StandardScaler().fit_transform(X)
 
    # 2) PCA xuống 2 chiều
    pca = PCA(n_components=2, random_state=42)
    Z = pca.fit_transform(X_std)
    ratio = pca.explained_variance_ratio_
    total = ratio.sum()
 
    # 3) K-means (chạy trên không gian đã chuẩn hóa, không phải trên 2 chiều PCA)
    km = KMeans(n_clusters=args.k, n_init=10, random_state=42)
    df["Cluster"] = km.fit_predict(X_std)
    df["PC1"], df["PC2"] = Z[:, 0], Z[:, 1]
 
    print("Tỉ lệ phương sai được giữ lại:")
    print(f"  PC1: {ratio[0]:.2%}")
    print(f"  PC2: {ratio[1]:.2%}")
    print(f"  Tổng 2 thành phần: {total:.2%}  (mất {1 - total:.2%})")
    print("\nSố cầu thủ mỗi cụm:")
    print(df["Cluster"].value_counts().sort_index().to_string())
 
    # 4) Vẽ
    fig, ax = plt.subplots(figsize=(12, 8))
    cmap = plt.get_cmap("tab10")
    for c in range(args.k):
        sub = df[df["Cluster"] == c]
        ax.scatter(sub["PC1"], sub["PC2"], s=28, alpha=0.7,
                   color=cmap(c), label=f"Cụm {c} (n={len(sub)})")
 
    # Chú thích cầu thủ nổi bật: top theo PTS trong mỗi cụm
    for c in range(args.k):
        sub = df[df["Cluster"] == c].nlargest(args.top, "PTS")
        for _, r in sub.iterrows():
            ax.annotate(r["Player"], (r["PC1"], r["PC2"]),
                        xytext=(6, 6), textcoords="offset points", fontsize=8,
                        arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))
 
    ax.set_xlabel(f"PC1 ({ratio[0]:.1%} phương sai)")
    ax.set_ylabel(f"PC2 ({ratio[1]:.1%} phương sai)")
    ax.set_title(f"PCA 2D + K-means (k={args.k}) - 2 thành phần giữ lại {total:.1%} phương sai")
    ax.axhline(0, color="lightgray", lw=0.8)
    ax.axvline(0, color="lightgray", lw=0.8)
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"\nĐã lưu biểu đồ: {args.out}")
 
 
if __name__ == "__main__":
    main()