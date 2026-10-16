#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHẦN III (mục A, B, C) - HỌC MÁY TRÊN DỮ LIỆU CẦU THỦ NBA 2024-25
    A. K-means phân cụm cầu thủ  (chọn đặc trưng -> xử lý N/a -> StandardScaler -> KMeans)
    B. Elbow Method + Silhouette Score để chọn số cụm K
    C. PCA giảm xuống 2 chiều, tô màu theo cụm K-means, chú thích cầu thủ nổi bật
(Mục D - radar chart - đã có ở radarChartPlot.py; file này không đụng tới nó.)

Chạy (đứng trong thư mục phan3):
    python kmeans_pca.py            # K tự chọn theo quy tắc Elbow + Silhouette (xem choose_k)
    python kmeans_pca.py --k 5      # ép K = 5 để so sánh
    python kmeans_pca.py --data đường/dẫn/results.csv

Đầu vào : ../phan1/results.csv   (chỉ ĐỌC, không bao giờ ghi đè)
Đầu ra  : phan3/output/
    elbow_silhouette.png      biểu đồ Elbow + Silhouette theo K
    k_selection.csv           bảng inertia / silhouette / độ gãy theo K
    player_clusters.csv       từng cầu thủ -> cụm + tọa độ PC1, PC2
    cluster_profile.csv       kích thước, trung bình đặc trưng, số phút/đá chính, vị trí của từng cụm
    cluster_centroids_z.csv   tâm cụm theo z-score (so với trung bình toàn giải)
    pca_clusters.png          biểu đồ PCA 2D tô màu theo cụm
    pca_variance.csv          tỷ lệ phương sai của từng thành phần chính
    pca_loadings.csv          hệ số (loading) của PC1, PC2

VÌ SAO CHỌN 12 ĐẶC TRƯNG TRONG FEATURES
  * Mỗi khía cạnh của một cầu thủ có đại diện: ghi điểm, rebound, kiến tạo/xử lý bóng, phòng thủ,
    hiệu quả + vai trò tấn công, tác động tổng hợp, phong cách ném -> cụm phản ánh cả "mức đóng góp"
    lẫn "kiểu chơi".
  * 12 cột này không có N/a nào trong results.csv.
  * Không dùng:
      - Player / Team / Pos: định danh hoặc nhãn (Pos chỉ dùng SAU KHI phân cụm để đối chiếu).
      - Age, G, GS, MP, MP/G: thời lượng thi đấu, không phải phong cách (MP/G tương quan 0.87 với PTS).
      - Cột gần như trùng nhau (tương quan ~ 1.00): 3PAr = %FGA_3P, TRB% = TRB_per100, BLK% = BLK_per100...
        Giữ cả hai sẽ khiến cùng một khía cạnh được tính 2 lần trong khoảng cách K-means.
      - Cột % ném theo vùng / góc (3P%, FG%_3P, Corner3_3P%, %Assisted_3P, FG%_16ft-3P, FG%_10-16ft,
        Corner3_%3PA): có N/a mang tính CẤU TRÚC (cầu thủ chưa từng ném loại đó). Điền trung vị sẽ "bịa" ra
        tay ném cho người không ném; loại bỏ hàng thì mất cầu thủ. Dùng 3PAr/FTr (không bao giờ thiếu) thay thế.
"""

import argparse
from pathlib import Path

import matplotlib
# Lưu biểu đồ thành ảnh, không mở cửa sổ (giống analysis.py).
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_samples, silhouette_score
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

RANDOM_STATE = 42          # cố định để chạy lại luôn ra đúng kết quả
N_INIT = 20                # mỗi K chạy 20 lần khởi tạo, lấy lần có inertia nhỏ nhất
K_MIN, K_MAX = 2, 10       # khoảng K khảo sát (Silhouette cần K >= 2)
ELBOW_TOLERANCE = 0.9      # "vùng khuỷu" = các K có độ gãy >= 90% độ gãy lớn nhất
MIN_CLUSTER_SHARE = 0.05   # mỗi cụm phải có >= 5% số cầu thủ
MAX_MISSING_PER_ROW = 0.5  # hàng thiếu quá 50% đặc trưng thì bỏ
HIGHLIGHT_COL = "VORP"     # tiêu chí chọn cầu thủ "nổi bật" để chú thích (không dùng để phân cụm)
N_LABELS_TOTAL = 12        # tổng số tên cầu thủ ghi trên biểu đồ PCA (chia đều cho các cụm)

# Đặc trưng dùng để phân cụm: tên cột trong results.csv -> nhóm ý nghĩa
FEATURES = {
    "PTS": "ghi điểm",
    "TRB": "rebound",
    "AST": "kiến tạo / xử lý bóng",
    "TOV": "kiến tạo / xử lý bóng",
    "STL": "phòng thủ",
    "BLK": "phòng thủ",
    "TS%": "hiệu quả + vai trò tấn công",
    "USG%": "hiệu quả + vai trò tấn công",
    "PER": "tác động tổng hợp",
    "BPM": "tác động tổng hợp",
    "3PAr": "phong cách ném",
    "FTr": "phong cách ném",
}


# ----------------------------------------------------------------------------
# ĐỌC DỮ LIỆU
# ----------------------------------------------------------------------------
def find_data():
    """results.csv nằm ở ../phan1/ (hoặc cùng thư mục với file code) - cùng cách tìm với radarChartPlot.py."""
    for p in (BASE_DIR.parent / "phan1" / "results.csv", BASE_DIR / "results.csv"):
        if p.is_file():
            return p
    return BASE_DIR.parent / "phan1" / "results.csv"


def read_csv_safe(path):
    """Đọc CSV: thử UTF-8 (có/không BOM) rồi cp1252 (CSV lưu lại từ Excel). 'N/a' được hiểu là thiếu dữ liệu."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, na_values=["N/a"], encoding=enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit("Không đọc được file CSV (lỗi bảng mã).")


# ----------------------------------------------------------------------------
# A. TIỀN XỬ LÝ
# ----------------------------------------------------------------------------
def prepare_features(df):
    """Chọn đặc trưng, ép về số, xử lý N/a và dữ liệu không hợp lệ.
    Trả về (X, meta, nhật ký). X và meta CÙNG chỉ số hàng nên mỗi hàng luôn ứng với đúng một cầu thủ."""
    X = df[list(FEATURES)].apply(pd.to_numeric, errors="coerce")   # "N/a" hoặc chữ lạ -> NaN
    X = X.replace([np.inf, -np.inf], np.nan)                       # vô cực -> NaN
    log = {"missing_per_feature": X.isna().sum()}

    # Cột toàn thiếu hoặc không biến thiên: không có thông tin, và StandardScaler sẽ chia cho 0.
    all_nan = [c for c in X.columns if X[c].isna().all()]
    constant = [c for c in X.columns if c not in all_nan and X[c].nunique() <= 1]
    X = X.drop(columns=all_nan + constant)
    log["dropped_columns"] = all_nan + constant
    if X.shape[1] < 2:
        raise SystemExit("Còn dưới 2 đặc trưng hợp lệ, không thể phân cụm / PCA.")

    # Hàng thiếu quá nửa số đặc trưng: quá ít thông tin để xếp cụm -> bỏ.
    too_empty = X.isna().mean(axis=1) > MAX_MISSING_PER_ROW
    log["dropped_rows"] = df.loc[too_empty[too_empty].index, "Player"].tolist()
    X = X[~too_empty]
    if len(X) < 3:
        raise SystemExit("Quá ít cầu thủ hợp lệ để phân cụm (cần ít nhất 3).")

    # Ô thiếu còn lại: điền TRUNG VỊ của cột (ít bị ngoại lai kéo lệch hơn trung bình).
    log["cells_imputed"] = int(X.isna().sum().sum())
    X = X.fillna(X.median())

    meta = df.loc[X.index, [c for c in ("Player", "Team", "Pos") if c in df.columns]]
    return X, meta, log


# ----------------------------------------------------------------------------
# B. ELBOW + SILHOUETTE
# ----------------------------------------------------------------------------
def evaluate_k(Xs):
    """Chạy K-means cho từng K hợp lệ; tính inertia, silhouette, % giảm inertia và 'độ gãy' Elbow."""
    n = len(Xs)
    ks = [k for k in range(K_MIN, K_MAX + 1) if 2 <= k <= n - 1]   # K hợp lệ cho Silhouette: 2 <= K <= n-1
    rows = []
    for k in ks:
        km = KMeans(n_clusters=k, n_init=N_INIT, random_state=RANDOM_STATE).fit(Xs)
        sizes = np.bincount(km.labels_, minlength=k)
        n_used = int((sizes > 0).sum())
        sil = silhouette_score(Xs, km.labels_) if 2 <= n_used <= n - 1 else np.nan
        rows.append({"K": k, "Inertia": km.inertia_, "Silhouette": sil, "Min_cluster_size": int(sizes.min())})
    t = pd.DataFrame(rows)
    t["Inertia_drop_pct"] = -t["Inertia"].pct_change() * 100

    # Độ gãy Elbow: chuẩn hóa cả hai trục về [0,1] sao cho điểm đầu của đường cong thành (0, 1) và điểm cuối
    # thành (1, 0), rồi đo khoảng cách từ từng điểm tới đường thẳng nối hai đầu (x + y = 1). Càng xa = càng "gãy".
    if len(t) >= 3:
        x = (t["K"] - t["K"].iloc[0]) / (t["K"].iloc[-1] - t["K"].iloc[0])
        y = (t["Inertia"] - t["Inertia"].iloc[-1]) / (t["Inertia"].iloc[0] - t["Inertia"].iloc[-1])
        t["Elbow_dist"] = (x + y - 1).abs() / np.sqrt(2)
    else:
        t["Elbow_dist"] = 0.0
    return t


def choose_k(t, n):
    """Quy tắc chọn K (đặt ra trước khi nhìn kết quả):
      1) Elbow: K có độ gãy lớn nhất là điểm gãy. Đường cong thường trơn nên lấy cả 'vùng khuỷu'
         = các K có độ gãy >= 90% độ gãy lớn nhất.
      2) Silhouette: trong vùng khuỷu, chọn K có Silhouette cao nhất.
      3) Điều kiện diễn giải: cụm nhỏ nhất phải có >= 5% số cầu thủ (tránh cụm chỉ gồm vài ngoại lai).
    Trả về (K chọn, K theo điểm gãy Elbow, K có Silhouette cao nhất toàn khoảng, danh sách K trong vùng khuỷu)."""
    k_elbow = int(t.loc[t["Elbow_dist"].idxmax(), "K"])
    k_sil = int(t.loc[t["Silhouette"].idxmax(), "K"]) if t["Silhouette"].notna().any() else k_elbow

    ok_size = t["Min_cluster_size"] >= MIN_CLUSTER_SHARE * n
    in_elbow = t["Elbow_dist"] >= ELBOW_TOLERANCE * t["Elbow_dist"].max()
    region = t[in_elbow & ok_size]
    if region["Silhouette"].notna().any():
        k_final = int(region.loc[region["Silhouette"].idxmax(), "K"])
    else:
        k_final = k_elbow
    return k_final, k_elbow, k_sil, region["K"].tolist()


def plot_k_selection(t, k_final, k_elbow, k_sil, region_ks, path):
    """Hai biểu đồ cạnh nhau: Elbow (inertia) và Silhouette theo K."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.6))
    for ax in (ax1, ax2):
        for k in region_ks:                                   # tô nền vùng khuỷu
            ax.axvspan(k - 0.5, k + 0.5, color="gold", alpha=0.2, lw=0)
        ax.axvline(k_elbow, color="gray", ls="--", lw=1)      # điểm gãy Elbow
        ax.set_xticks(t["K"])
        ax.set_xlabel("Số cụm K")
        ax.set_axisbelow(True)
        ax.grid(alpha=0.25)

    ax1.plot(t["K"], t["Inertia"], "o-", color="tab:blue")
    ax1.set_ylabel("Inertia (tổng bình phương khoảng cách tới tâm cụm)")
    ax1.set_title("Elbow Method")
    ax2.plot(t["K"], t["Silhouette"], "o-", color="tab:green")
    ax2.set_ylabel("Silhouette Score trung bình")
    ax2.set_title("Silhouette Score")

    for ax, col, fmt in ((ax1, "Inertia", "{:.0f}"), (ax2, "Silhouette", "{:.3f}")):
        ax.margins(y=0.12)                                    # chừa chỗ phía trên cho nhãn giá trị
        for k, v in zip(t["K"], t[col]):
            ax.annotate(fmt.format(v), (k, v), textcoords="offset points", xytext=(0, 12),
                        ha="center", fontsize=8)
        if k_final in set(t["K"]):                            # khoanh đỏ K được chọn
            v = float(t.loc[t["K"] == k_final, col].iloc[0])
            ax.scatter([k_final], [v], s=190, facecolors="none", edgecolors="red", linewidths=2, zorder=4)
    ax2.scatter([k_sil], [float(t.loc[t["K"] == k_sil, "Silhouette"].iloc[0])],
                marker="*", s=170, color="darkgreen", zorder=5)

    handles = [
        Patch(color="gold", alpha=0.35, label=f"Vùng khuỷu (độ gãy ≥ {ELBOW_TOLERANCE:.0%} mức cao nhất): K = "
                                              + ", ".join(map(str, region_ks))),
        Line2D([0], [0], color="gray", ls="--", label=f"Điểm gãy Elbow: K = {k_elbow}"),
        Line2D([0], [0], marker="*", ls="", color="darkgreen", markersize=13,
               label=f"Silhouette cao nhất: K = {k_sil}"),
        Line2D([0], [0], marker="o", ls="", markerfacecolor="none", markeredgecolor="red",
               markersize=11, markeredgewidth=2, label=f"K được chọn: {k_final}"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False, fontsize=9)
    fig.suptitle("Chọn số cụm K cho K-means (dữ liệu đã chuẩn hóa StandardScaler)", fontsize=13)
    fig.tight_layout(rect=(0, 0.12, 1, 0.96))
    fig.savefig(path, dpi=200)
    plt.close(fig)


# ----------------------------------------------------------------------------
# A. K-MEANS CUỐI + PHÂN TÍCH CỤM
# ----------------------------------------------------------------------------
def relabel_by_size(raw, index):
    """Đánh số lại cụm theo kích thước giảm dần (cụm 1 = đông nhất). Nhãn gốc của K-means là ngẫu nhiên,
    đánh số lại giúp số hiệu cụm ổn định giữa các lần chạy / phiên bản thư viện."""
    sizes = np.bincount(raw)
    order = sorted(range(len(sizes)), key=lambda c: (-sizes[c], c))
    mapping = {old: new for new, old in enumerate(order, start=1)}
    return pd.Series(raw, index=index).map(mapping)


def describe_columns(df, index):
    """Biến CHỈ để mô tả cụm sau khi đã phân xong (KHÔNG nằm trong FEATURES nên không ảnh hưởng K-means):
    MP/G = số phút mỗi trận, GS_rate = GS / G = tỷ lệ số trận đá chính."""
    extra = pd.DataFrame(index=index)
    if "MP/G" in df.columns:
        extra["MP/G"] = pd.to_numeric(df.loc[index, "MP/G"], errors="coerce")
    if {"GS", "G"} <= set(df.columns):
        gs = pd.to_numeric(df.loc[index, "GS"], errors="coerce")
        g = pd.to_numeric(df.loc[index, "G"], errors="coerce")
        extra["GS_rate"] = (gs / g).replace([np.inf, -np.inf], np.nan)
    return extra


def summarize_clusters(X, Xs, labels, meta, sil_samples, extra):
    """Hồ sơ từng cụm: kích thước, silhouette, trung bình đặc trưng (đơn vị gốc), biến mô tả, vị trí,
    tâm cụm theo z-score."""
    n = len(labels)
    sizes = labels.value_counts().sort_index()
    profile = X.groupby(labels).mean()                              # trung bình theo đơn vị gốc
    centroids = Xs.groupby(labels).mean()                           # tâm cụm trong không gian đã chuẩn hóa
    profile.insert(0, "N", sizes)
    profile.insert(1, "Share_pct", sizes / n * 100)
    profile.insert(2, "Mean_silhouette", pd.Series(sil_samples, index=Xs.index).groupby(labels).mean())
    profile = profile.join(extra.groupby(labels).mean())
    if "Pos" in meta:
        profile = profile.join(pd.crosstab(labels, meta["Pos"]).add_prefix("n_"))
    profile.index.name = centroids.index.name = "Cluster"
    return profile, centroids


def print_clusters(profile, centroids, Xs, labels, meta, highlight):
    """In đặc điểm từng cụm bằng số liệu thực tế (không gán nhãn 'siêu sao', 'big man'... ở đây)."""
    # khoảng cách của mỗi cầu thủ tới tâm cụm của chính mình -> tìm người "điển hình" nhất
    own_center = centroids.loc[labels].to_numpy()
    dist = pd.Series(np.linalg.norm(Xs.to_numpy() - own_center, axis=1), index=Xs.index)
    pos_cols = [c for c in profile.columns if c.startswith("n_")]

    print("\n(z = tâm cụm tính bằng độ lệch chuẩn so với trung bình toàn giải: z > 0 cao hơn, z < 0 thấp hơn)")
    for c in profile.index:
        row = profile.loc[c]
        print(f"\n--- Cụm {c}: {int(row['N'])} cầu thủ ({row['Share_pct']:.1f}%), "
              f"silhouette trung bình = {row['Mean_silhouette']:.3f}")
        if pos_cols:
            pos = row[pos_cols].astype(int).sort_values(ascending=False)
            print("    Vị trí (Pos): " + ", ".join(f"{k[2:]} {v}" for k, v in pos.items() if v > 0))
        z = centroids.loc[c].sort_values(ascending=False)
        print("    3 đặc trưng cao nhất (z) : " + ", ".join(f"{k} {v:+.2f}" for k, v in z.head(3).items()))
        print("    3 đặc trưng thấp nhất (z): " + ", ".join(f"{k} {v:+.2f}" for k, v in z.tail(3)[::-1].items()))
        members = labels[labels == c].index
        typical = meta.loc[dist[members].nsmallest(3).index, "Player"].tolist()
        top = meta.loc[highlight[members].nlargest(5).index, "Player"].tolist()
        print(f"    Điển hình (gần tâm cụm nhất): {', '.join(typical)}")
        print(f"    Nổi bật ({HIGHLIGHT_COL} cao nhất): {', '.join(top)}")


# ----------------------------------------------------------------------------
# C. PCA
# ----------------------------------------------------------------------------
def annotate_players(ax, points):
    """Ghi tên cầu thủ. Với mỗi tên, thử lần lượt vài vị trí quanh điểm và lấy vị trí đầu tiên nằm trong
    khung biểu đồ, không đè lên tên đã ghi (để biểu đồ không bị rối)."""
    fig = ax.figure
    fig.canvas.draw()                                   # vẽ trước để biết kích thước chữ
    renderer = fig.canvas.get_renderer()
    frame = ax.get_window_extent(renderer)
    placed = []
    options = [(7, 7, "left", "bottom"), (7, -7, "left", "top"),
               (-7, 7, "right", "bottom"), (-7, -7, "right", "top"),
               (0, 14, "center", "bottom"), (0, -14, "center", "top"),
               (24, 0, "left", "center"), (-24, 0, "right", "center")]
    style = dict(textcoords="offset points", fontsize=9, fontweight="bold", zorder=5,
                 bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    for name, x, y in points:
        for dx, dy, ha, va in options:
            text = ax.annotate(name, (x, y), xytext=(dx, dy), ha=ha, va=va, **style)
            box = text.get_window_extent(renderer)
            inside = frame.x0 <= box.x0 and box.x1 <= frame.x1 and frame.y0 <= box.y0 and box.y1 <= frame.y1
            if inside and not any(box.overlaps(b) for b in placed):
                placed.append(box)
                break
            text.remove()
        else:                                           # hết chỗ trống: chấp nhận vị trí đầu tiên
            ax.annotate(name, (x, y), xytext=options[0][:2], ha="left", va="bottom", **style)


def plot_pca(coords, labels, meta, highlight, evr, k, path):
    """Biểu đồ PC1-PC2, tô màu theo cụm K-means, khoanh tròn + ghi tên vài cầu thủ nổi bật mỗi cụm."""
    n = len(labels)
    fig, ax = plt.subplots(figsize=(11, 8))
    cmap = plt.get_cmap("tab10")
    for c in sorted(labels.unique()):
        mask = (labels == c).to_numpy()
        ax.scatter(coords.loc[mask, "PC1"], coords.loc[mask, "PC2"], s=32, alpha=0.75,
                   color=cmap((c - 1) % 10), edgecolor="white", linewidth=0.4,
                   label=f"Cụm {c} (n = {mask.sum()})")

    per_cluster = max(1, round(N_LABELS_TOTAL / k))     # số cầu thủ ghi tên ở mỗi cụm
    picks = []
    for c in sorted(labels.unique()):
        picks += highlight[labels == c].nlargest(per_cluster).index.tolist()
    ax.scatter(coords.loc[picks, "PC1"], coords.loc[picks, "PC2"], s=95, facecolors="none",
               edgecolors="black", linewidths=1.2, zorder=4)

    ax.axhline(0, color="gray", lw=0.6)
    ax.axvline(0, color="gray", lw=0.6)
    ax.set_xlabel(f"PC1 ({evr[0]:.1%} phương sai)")
    ax.set_ylabel(f"PC2 ({evr[1]:.1%} phương sai)")
    ax.set_title(f"PCA 2 chiều của {n} cầu thủ NBA 2024-25, tô màu theo K-means (K = {k})\n"
                 f"PC1 + PC2 giữ lại {evr.sum():.1%} tổng phương sai")
    ax.grid(alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(title="Cụm K-means", loc="best", framealpha=0.9)
    fig.tight_layout()
    annotate_players(ax, [(meta.loc[i, "Player"], coords.loc[i, "PC1"], coords.loc[i, "PC2"]) for i in picks])
    fig.savefig(path, dpi=200)
    plt.close(fig)


# ----------------------------------------------------------------------------
# CHƯƠNG TRÌNH CHÍNH
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Phần III: K-means, Elbow, Silhouette và PCA cho cầu thủ NBA 2024-25.")
    ap.add_argument("--k", type=int, help="ép số cụm K (mặc định: tự chọn theo Elbow + Silhouette)")
    ap.add_argument("--data", default=str(find_data()), help="đường dẫn results.csv")
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.is_file():
        raise SystemExit(f"Không tìm thấy file CSV: {data_path}")
    df = read_csv_safe(data_path)
    lost = sorted({"Player", *FEATURES} - set(df.columns))
    if lost:
        raise SystemExit(f"CSV còn thiếu các cột: {lost}")
    if df["Player"].isna().any():
        raise SystemExit("CSV có dòng thiếu tên cầu thủ.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ===== 1. TIỀN XỬ LÝ =====
    X, meta, log = prepare_features(df)
    n, p = X.shape
    print("===== 1. DỮ LIỆU VÀ TIỀN XỬ LÝ =====")
    print(f"File dữ liệu : {data_path}")
    mp_note = f" (MP nhỏ nhất = {df['MP'].min():g})" if "MP" in df.columns else ""
    print(f"Số cầu thủ   : {n}/{len(df)}{mp_note}")
    print(f"Số đặc trưng : {p}")
    print(f"Ô thiếu / không hợp lệ trong các đặc trưng ban đầu: {int(log['missing_per_feature'].sum())}")
    print(f"  - cột bị bỏ (toàn thiếu / không biến thiên): {log['dropped_columns'] or 'không có'}")
    print(f"  - hàng bị bỏ (thiếu > {MAX_MISSING_PER_ROW:.0%} đặc trưng): {log['dropped_rows'] or 'không có'}")
    print(f"  - ô được điền trung vị: {log['cells_imputed']}")
    other_na = [c for c in df.columns
                if c not in FEATURES and pd.api.types.is_numeric_dtype(df[c]) and df[c].isna().any()]
    print(f"Cột số khác có N/a (KHÔNG dùng làm đặc trưng): {other_na or 'không có'}")

    info = pd.DataFrame({
        "Nhóm": pd.Series(FEATURES),
        "Thiếu": log["missing_per_feature"],
        "Trung bình": X.mean(),
        "Độ lệch chuẩn": X.std(),
    }).loc[X.columns]
    print("\nĐặc trưng dùng để phân cụm:")
    print(info.round(3).to_string())

    # Chuẩn hóa z = (x - trung bình) / độ lệch chuẩn: mọi đặc trưng có trọng số ngang nhau trong khoảng cách K-means.
    Xs = pd.DataFrame(StandardScaler().fit_transform(X), index=X.index, columns=X.columns)

    # ===== 2. CHỌN K =====
    table = evaluate_k(Xs)
    k_final, k_elbow, k_sil, region_ks = choose_k(table, n)
    if args.k is not None:
        if not 2 <= args.k <= n - 1:
            raise SystemExit(f"--k phải nằm trong khoảng 2..{n - 1}.")
        k_final = args.k
    table["In_elbow_region"] = table["K"].isin(region_ks)
    table["Chosen"] = table["K"] == k_final

    print("\n===== 2. CHỌN SỐ CỤM K (Elbow + Silhouette) =====")
    print(table.round(4).to_string(index=False))
    print(f"\nK theo điểm gãy Elbow           : {k_elbow}")
    print(f"K có Silhouette cao nhất        : {k_sil} (silhouette = {table.loc[table['K'] == k_sil, 'Silhouette'].iloc[0]:.4f})")
    print(f"Vùng khuỷu (độ gãy >= {ELBOW_TOLERANCE:.0%} mức cao nhất): K = {region_ks}")
    if args.k is not None:
        print(f"=> K = {k_final} (do người dùng ép bằng --k)")
    else:
        sil_final = table.loc[table["K"] == k_final, "Silhouette"].iloc[0]
        print(f"=> K = {k_final}: Silhouette cao nhất trong vùng khuỷu ({sil_final:.4f}), "
              f"cụm nhỏ nhất >= {MIN_CLUSTER_SHARE:.0%} số cầu thủ")
    if k_elbow != k_sil:
        print(f"Lưu ý: Elbow (K = {k_elbow}) và Silhouette (K = {k_sil}) gợi ý khác nhau, xem giải thích trong báo cáo.")

    # ===== 3. K-MEANS CUỐI + ĐẶC ĐIỂM CỤM =====
    km = KMeans(n_clusters=k_final, n_init=N_INIT, random_state=RANDOM_STATE).fit(Xs)
    labels = relabel_by_size(km.labels_, Xs.index)
    sil_samples = silhouette_samples(Xs, km.labels_)
    extra = describe_columns(df, X.index)
    profile, centroids = summarize_clusters(X, Xs, labels, meta, sil_samples, extra)
    highlight = (pd.to_numeric(df.loc[X.index, HIGHLIGHT_COL], errors="coerce")
                 if HIGHLIGHT_COL in df.columns else Xs.sum(axis=1))

    print(f"\n===== 3. K-MEANS VỚI K = {k_final} =====")
    print(f"Silhouette tổng thể = {sil_samples.mean():.4f}; inertia = {km.inertia_:.1f}; "
          f"{(sil_samples < 0).mean():.1%} cầu thủ có silhouette < 0 (nằm gần ranh giới cụm khác)")
    print("\nTrung bình đặc trưng của từng cụm (đơn vị gốc):")
    print(profile[["N", "Mean_silhouette", *X.columns]].round(2).to_string())
    if len(extra.columns):
        print("\nBiến mô tả, KHÔNG dùng để phân cụm (trung bình mỗi cụm):")
        print(profile[list(extra.columns)].round(2).to_string())
    print_clusters(profile, centroids, Xs, labels, meta, highlight)

    # ===== 4. PCA =====
    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    coords = pd.DataFrame(pca.fit_transform(Xs), index=Xs.index, columns=["PC1", "PC2"])   # cùng thứ tự với Xs
    evr = pca.explained_variance_ratio_
    full = PCA(random_state=RANDOM_STATE).fit(Xs).explained_variance_ratio_                # tất cả thành phần
    cum = np.cumsum(full)
    n80, n90 = int(np.searchsorted(cum, 0.80) + 1), int(np.searchsorted(cum, 0.90) + 1)
    loadings = pd.DataFrame(pca.components_.T, index=Xs.columns, columns=["PC1", "PC2"])

    print("\n===== 4. PCA 2 CHIỀU =====")
    print(f"PC1 giải thích {evr[0]:.4f} ({evr[0]:.1%}) phương sai")
    print(f"PC2 giải thích {evr[1]:.4f} ({evr[1]:.1%}) phương sai")
    print(f"PC1 + PC2 = {evr.sum():.4f} ({evr.sum():.1%}); phần phương sai bị mất khi chỉ giữ 2 chiều: {1 - evr.sum():.1%}")
    print(f"Cần {n80} thành phần để giữ >= 80% và {n90} thành phần để giữ >= 90% phương sai (trên tổng {p}).")
    for pc in ("PC1", "PC2"):
        top = loadings[pc].reindex(loadings[pc].abs().sort_values(ascending=False).index).head(4)
        print(f"Loading lớn nhất của {pc}: " + ", ".join(f"{k} {v:+.2f}" for k, v in top.items()))

    # ===== 5. LƯU KẾT QUẢ =====
    result = meta.copy()
    result["Cluster"] = labels
    result[["PC1", "PC2"]] = coords
    result.to_csv(OUTPUT_DIR / "player_clusters.csv", index=False, encoding="utf-8-sig")
    table.round(4).to_csv(OUTPUT_DIR / "k_selection.csv", index=False, encoding="utf-8-sig")
    profile.round(3).to_csv(OUTPUT_DIR / "cluster_profile.csv", encoding="utf-8-sig")
    centroids.round(3).to_csv(OUTPUT_DIR / "cluster_centroids_z.csv", encoding="utf-8-sig")
    pd.DataFrame({"Component": [f"PC{i}" for i in range(1, len(full) + 1)],
                  "Explained_variance_ratio": full, "Cumulative": cum}
                 ).round(4).to_csv(OUTPUT_DIR / "pca_variance.csv", index=False, encoding="utf-8-sig")
    loadings.round(4).to_csv(OUTPUT_DIR / "pca_loadings.csv", index_label="Feature", encoding="utf-8-sig")
    plot_k_selection(table, k_final, k_elbow, k_sil, region_ks, OUTPUT_DIR / "elbow_silhouette.png")
    plot_pca(coords, labels, meta, highlight, evr, k_final, OUTPUT_DIR / "pca_clusters.png")
    print(f"\nĐã lưu kết quả (CSV, biểu đồ) vào: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
