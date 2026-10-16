# -*- coding: utf-8 -*-
"""
Web tra cứu và phân tích cầu thủ NBA mùa 2024-25 (Streamlit).

Chạy:
    pip install -r web/requirements.txt
    streamlit run web/app.py

Web CHỈ ĐỌC các file đã có sẵn trong repo (không gọi lại crawl.py):
    phan1/results.csv                 dữ liệu cầu thủ (Bài 1)
    phan2/output/*.csv                thống kê đội, top 3 (Bài 2)
    phan3/*.csv, phan3/*.png          cụm K-means, PCA (Bài 3)
"""
import unicodedata
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="NBA 2024-25", page_icon="🏀", layout="wide")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RED, BLUE, GREY = "
#C0362C", "
#2F6F8F", "
#9AA5AE"
CLUSTER_COLORS = ["
#2F6F8F", "
#E8743B", "
#5B8C5A", "
#C0362C", "
#8E6BBF", "
#B8A04A"]
TEXT_COLS = {"Player", "Team", "Pos"}

# ----------------------------------------------------------------------------
# ĐỌC DỮ LIỆU
# ----------------------------------------------------------------------------
def find_file(*candidates):
    """Trả về đường dẫn đầu tiên tồn tại trong các vị trí có thể có, nếu không có thì None."""
    for rel in candidates:
        for base in (ROOT, HERE):
            p = base / rel
            if p.exists():
                return p
    return None

def read_csv_safe(path):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Không đọc được {path} (lỗi bảng mã).")

def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")

def norm(s):
    return strip_accents(s).casefold().strip()

@st.cache_data(show_spinner=False)
def load_players():
    p = find_file("phan1/results.csv", "data/results.csv", "results.csv")
    if p is None:
        return None
    df = read_csv_safe(p)
    for c in df.columns:
        if c not in TEXT_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce")  # "N/a" -> NaN
    df["_key"] = df["Player"].map(norm)
    return df

@st.cache_data(show_spinner=False)
def load_optional(*candidates):
    p = find_file(*candidates)
    return read_csv_safe(p) if p is not None else None

def numeric_cols(df):
    return [c for c in df.columns if c not in TEXT_COLS and not c.startswith("_") and df[c].notna().any()]

def fmt(v, nd=1):
    return "N/a" if pd.isna(v) else f"{v:,.{nd}f}"

# ----------------------------------------------------------------------------
# NHÓM CỘT HIỂN THỊ
# ----------------------------------------------------------------------------
COLUMN_GROUPS = {
    "Cơ bản": ["Team", "Pos", "Age", "G", "MP/G", "PTS", "TRB", "AST", "STL", "BLK", "TOV", "TS%"],
    "Ném rổ": ["Team", "Pos", "FG", "FGA", "FG%", "3P", "3PA", "3P%", "2P", "2PA", "2P%", "FT", "FTA", "FT%", "eFG%"],
    "Nâng cao": ["Team", "Pos", "PER", "TS%", "USG%", "ORtg", "DRtg", "WS", "WS/48", "OBPM", "DBPM", "BPM", "VORP"],
}

# ----------------------------------------------------------------------------
# TRANG 1: TRA CỨU CẦU THỦ
# ----------------------------------------------------------------------------
def page_lookup(df, clusters):
    st.header("Tra cứu cầu thủ")
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    q = c1.text_input("Tìm theo tên", placeholder="ví dụ: jokic, curry...")
    teams = c2.multiselect("Đội", sorted(df["Team"].dropna().unique()))
    poss = c3.multiselect("Vị trí", sorted(df["Pos"].dropna().unique()))
    mp_min = int(df["MP"].min())
    mp_max = int(df["MP"].max())
    mp_sel = c4.slider("Tổng số phút tối thiểu", mp_min, mp_max, mp_min, step=50)

    view = df[df["MP"] >= mp_sel]
    if q.strip():
        view = view[view["_key"].str.contains(norm(q), regex=False)]
    if teams:
        view = view[view["Team"].isin(teams)]
    if poss:
        view = view[view["Pos"].isin(poss)]

    g1, g2 = st.columns([2, 2])
    group = g1.selectbox("Nhóm thống kê hiển thị", list(COLUMN_GROUPS) + ["Tự chọn"])
    if group == "Tự chọn":
        cols = g2.multiselect("Cột hiển thị", [c for c in df.columns if c not in ("Player", "_key")],
                              default=["Team", "Pos", "PTS", "TRB", "AST"])
    else:
        cols = [c for c in COLUMN_GROUPS[group] if c in df.columns]
    sort_col = g2.selectbox("Sắp xếp theo", ["Player"] + [c for c in cols if c in numeric_cols(df)], index=0) if group != "Tự chọn" else "Player"
    desc = st.checkbox("Giảm dần", value=sort_col != "Player")
    view = view.sort_values(sort_col, ascending=not desc, na_position="last")

    st.caption(f"{len(view)} / {len(df)} cầu thủ")
    st.dataframe(view[["Player"] + cols], width="stretch", hide_index=True, height=420)

    st.subheader("Chi tiết một cầu thủ")
    if view.empty:
        st.info("Không có cầu thủ nào khớp bộ lọc.")
        return
    name = st.selectbox("Chọn cầu thủ", view["Player"].tolist())
    r = df[df["Player"] == name].iloc[0]
    m = st.columns(6)
    m[0].metric("Đội / vị trí", f"{r['Team']} / {r['Pos']}")
    m[1].metric("Tuổi", fmt(r["Age"], 0))
    m[2].metric("Số trận", fmt(r["G"], 0))
    m[3].metric("PTS", fmt(r["PTS"]))
    m[4].metric("TRB", fmt(r["TRB"]))
    m[5].metric("AST", fmt(r["AST"]))
    if clusters is not None:
        row = clusters[clusters["Player"] == name]
        if not row.empty:
            st.write(f"**Cụm K-means:** {int(row.iloc[0]['Cluster'])} (xem trang *Phân cụm cầu thủ*)")
    with st.expander("Toàn bộ thống kê"):
        full = r.drop(labels=[c for c in ("_key",) if c in r.index]).rename("Giá trị").astype(str).to_frame()
        st.dataframe(full, width="stretch", height=400)

# ----------------------------------------------------------------------------
# TRANG 2: RADAR
# ----------------------------------------------------------------------------
def radar_figure(df, p1, p2, attrs):
    num = df[attrs]
    lo, hi = num.min(), num.max()
    scaled = (num - lo) / (hi - lo).replace(0, np.nan)
    i1, i2 = df.index[df["Player"] == p1][0], df.index[df["Player"] == p2][0]
    ang = np.linspace(0, 2 * np.pi, len(attrs), endpoint=False).tolist()
    ang += ang[:1]
    fig, ax = plt.subplots(figsize=(6.6, 6.6), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    for idx, color, name in ((i1, RED, p1), (i2, BLUE, p2)):
        vals = scaled.loc[idx].fillna(0).tolist()
        vals += vals[:1]
        ax.plot(ang, vals, color=color, linewidth=2, label=name)
        ax.fill(ang, vals, color=color, alpha=0.2)
    labels = []
    for a in attrs:
        v1, v2 = df.loc[i1, a], df.loc[i2, a]
        labels.append(f"{a}\n{fmt(v1, 2)} | {fmt(v2, 2)}")
    ax.set_xticks(ang[:-1])
    ax.set_xticklabels(labels, fontsize=9)
    ax.tick_params(axis="x", pad=16)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=7, color="gray")
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.12), fontsize=9)
    fig.tight_layout()
    return fig, scaled, (i1, i2)

def page_radar(df):
    st.header("So sánh hai cầu thủ (biểu đồ radar)")
    names = df.sort_values("Player")["Player"].tolist()

    def default(n, fallback):
        return names.index(n) if n in names else fallback

    c1, c2 = st.columns(2)
    p1 = c1.selectbox("Cầu thủ 1", names, index=default("Shai Gilgeous-Alexander", 0))
    p2 = c2.selectbox("Cầu thủ 2", names, index=default("Nikola Jokić", 1))
    cols = numeric_cols(df)
    default_attrs = [a for a in ["PTS", "TRB", "AST", "STL", "BLK", "TS%"] if a in cols]
    attrs = st.multiselect("Thống kê so sánh (ít nhất 3)", cols, default=default_attrs)

    if p1 == p2:
        st.warning("Hãy chọn hai cầu thủ khác nhau.")
        return
    if len(attrs) < 3:
        st.warning("Cần chọn ít nhất 3 thống kê để vẽ radar.")
        return

    fig, scaled, (i1, i2) = radar_figure(df, p1, p2, attrs)
    left, right = st.columns([3, 2])
    left.pyplot(fig, width="stretch")
    with right:
        st.markdown("**Giá trị thật**")
        raw = df.loc[[i1, i2], ["Player"] + attrs].set_index("Player").T
        st.dataframe(raw.round(3), width="stretch")
        miss = [(n, a) for n, i in ((p1, i1), (p2, i2)) for a in attrs if pd.isna(df.loc[i, a])]
        if miss:
            st.warning("Thiếu dữ liệu (tính là 0 trên biểu đồ): " + ", ".join(f"{n}: {a}" for n, a in miss))
    st.caption("Mỗi trục được chuẩn hóa min-max trên toàn bộ cầu thủ: 0% là thấp nhất giải, 100% là cao nhất giải. "
               "Số dưới tên trục là giá trị thật (cầu thủ 1 | cầu thủ 2). Với TOV, PF, DRtg, giá trị càng cao nghĩa là càng nhiều, không phải càng tốt.")

# ----------------------------------------------------------------------------
# TRANG 3: PHÂN CỤM
# ----------------------------------------------------------------------------
def describe_clusters(centroids):
    """Gợi ý đọc cụm: 3 đặc trưng cao nhất (z-score) của mỗi cụm - tính từ file tâm cụm."""
    out = {}
    for cl, row in centroids.iterrows():
        top = row.sort_values(ascending=False).head(3)
        out[int(cl)] = ", ".join(f"{k} ({v:+.2f})" for k, v in top.items())
    return out

def page_clusters(df, clusters):
    st.header("Phân cụm cầu thủ (K-means + PCA)")
    if clusters is None:
        st.info("Chưa tìm thấy phan3/player_clusters.csv. Hãy chạy python phan3/kmeans_pca.py rồi tải lại trang.")
        return
    data = clusters.merge(df[["Player", "PTS", "TRB", "AST", "MP", "USG%"]], on="Player", how="left")
    k = data["Cluster"].nunique()
    var = load_optional("phan3/pca_variance.csv")
    c1, c2, c3 = st.columns(3)
    c1.metric("Số cụm (k)", k)
    c2.metric("Số cầu thủ", len(data))
    if var is not None and len(var) >= 2:
        c3.metric("Phương sai PCA giữ lại (PC1 + PC2)", f"{var['Cumulative'].iloc[1]:.1%}")

    # Biểu đồ PCA
    st.subheader("Biểu đồ PCA 2 chiều")
    top_default = data.sort_values("PTS", ascending=False).groupby("Cluster").head(2)["Player"].tolist()
    label_players = st.multiselect("Cầu thủ cần ghi tên trên biểu đồ", data.sort_values("Player")["Player"].tolist(), default=top_default)
    fig, ax = plt.subplots(figsize=(10, 6.2))
    for i, cl in enumerate(sorted(data["Cluster"].unique())):
        sub = data[data["Cluster"] == cl]
        ax.scatter(sub["PC1"], sub["PC2"], s=26, alpha=0.7, color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)], label=f"Cụm {cl} (n={len(sub)})")
    for n in label_players:
        r = data[data["Player"] == n].iloc[0]
        ax.annotate(n, (r["PC1"], r["PC2"]), xytext=(6, 6), textcoords="offset points", fontsize=8,
                    arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))
    if var is not None and len(var) >= 2:
        ax.set_xlabel(f"PC1 ({var['Explained_variance_ratio'].iloc[0]:.1%} phương sai)")
        ax.set_ylabel(f"PC2 ({var['Explained_variance_ratio'].iloc[1]:.1%} phương sai)")
    ax.axhline(0, color="lightgray", lw=0.8)
    ax.axvline(0, color="lightgray", lw=0.8)
    ax.grid(alpha=0.2)
    ax.legend()
    fig.tight_layout()
    st.pyplot(fig, width="stretch")

    # Hồ sơ cụm
    st.subheader("Đặc điểm từng cụm")
    prof = load_optional("phan3/cluster_profile.csv")
    cent = load_optional("phan3/cluster_centroids_z.csv")
    if prof is not None:
        show = [c for c in ["Cluster", "N", "Share_pct", "PTS", "TRB", "AST", "STL", "BLK", "TS%", "USG%", "PER", "BPM", "MP/G"] if c in prof.columns]
        st.dataframe(prof[show].round(2), width="stretch", hide_index=True)
    if cent is not None:
        hints = describe_clusters(cent.set_index("Cluster"))
        st.markdown("**Gợi ý đọc cụm** (3 đặc trưng nổi bật nhất so với trung bình toàn giải, theo z-score):")
        for cl, txt in hints.items():
            st.markdown(f"- Cụm {cl}: {txt}")
    st.caption("Phần gợi ý chỉ là số liệu; tên gọi và nhận xét cho từng cụm do nhóm tự đặt trong báo cáo.")

    # Cầu thủ trong cụm
    st.subheader("Cầu thủ trong từng cụm")
    cl_sel = st.selectbox("Chọn cụm", sorted(data["Cluster"].unique()))
    members = data[data["Cluster"] == cl_sel].sort_values("PTS", ascending=False)
    st.dataframe(members[["Player", "Team", "Pos", "PTS", "TRB", "AST", "MP"]], width="stretch", hide_index=True, height=320)

    # Chọn k
    with st.expander("Vì sao chọn k này? (Elbow và Silhouette)"):
        ks = load_optional("phan3/k_selection.csv")
        if ks is not None:
            st.dataframe(ks, width="stretch", hide_index=True)
        img = find_file("phan3/elbow_silhouette.png")
        if img is not None:
            st.image(str(img), width="stretch")

# ----------------------------------------------------------------------------
# TRANG 4: THỐNG KÊ ĐỘI
# ----------------------------------------------------------------------------
def page_teams(df):
    st.header("Thống kê và so sánh đội")
    means = load_optional("phan2/output/team_means.csv")
    comp = load_optional("phan2/output/team_comparison.csv")
    tops = load_optional("phan2/output/top_botton.csv")
    if means is None:
        st.info("Chưa tìm thấy phan2/output/team_means.csv.")
        return
    for c in means.columns:
        if c != "Team":
            means[c] = pd.to_numeric(means[c], errors="coerce")
    stats = [c for c in means.columns if c != "Team" and means[c].notna().any()]
    default_ix = stats.index("PTS") if "PTS" in stats else 0
    stat = st.selectbox("Thống kê", stats, index=default_ix)

    # Đội dẫn đầu
    leader_txt = None
    if comp is not None and (comp["Statistic"] == stat).any():
        r = comp[comp["Statistic"] == stat].iloc[0]
        rule = "cao nhất" if r["Selection_rule"] == "max" else "thấp nhất (thống kê càng thấp càng tốt)"
        leader_txt = f"**Đội dẫn đầu {stat}: {r['Selected_teams']}** ({r['Selected_mean']:.2f}), tính theo giá trị {rule}."
    if leader_txt:
        st.success(leader_txt)
    leader = comp[comp["Statistic"] == stat].iloc[0]["Selected_teams"] if leader_txt else None

    # Biểu đồ cột
    s = means[["Team", stat]].dropna().sort_values(stat, ascending=False)
    fig, ax = plt.subplots(figsize=(11, 4.2))
    colors = [RED if (leader and t in str(leader).split(",")) else BLUE for t in s["Team"]]
    ax.bar(s["Team"], s[stat], color=colors)
    if stat in df.columns:
        ax.axhline(df[stat].mean(), color=GREY, ls="--", lw=1, label=f"Trung bình toàn giải ({df[stat].mean():.2f})")
        ax.legend()
    ax.set_ylabel(f"Trung bình {stat}")
    ax.tick_params(axis="x", rotation=60)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    st.pyplot(fig, width="stretch")
    st.caption("Giá trị mỗi đội là trung bình của các cầu thủ trong đội (cầu thủ bị trade tính cho đội cuối cùng). Cột đỏ là đội dẫn đầu.")

    # Top 3
    if tops is not None and (tops["Statistic"] == stat).any():
        t = tops[tops["Statistic"] == stat]
        a, b = st.columns(2)
        a.markdown("**3 cầu thủ cao nhất**")
        a.dataframe(t[t["Category"] == "highest"][["Rank", "Player", "Team", "Value"]], hide_index=True, width="stretch")
        b.markdown("**3 cầu thủ thấp nhất**")
        b.dataframe(t[t["Category"] == "lowest"][["Rank", "Player", "Team", "Value"]], hide_index=True, width="stretch")

    # Histogram
    if stat in df.columns:
        st.subheader(f"Phân bố {stat}")
        team_opt = st.selectbox("Đánh dấu một đội trên histogram", ["(không)"] + sorted(df["Team"].dropna().unique()))
        vals = df[stat].dropna()
        fig2, ax2 = plt.subplots(figsize=(9, 3.8))
        _, bins, _ = ax2.hist(vals, bins=24, color=BLUE, alpha=0.55, edgecolor="white", label="Toàn giải")
        if team_opt != "(không)":
            ax2.hist(df.loc[df["Team"] == team_opt, stat].dropna(), bins=bins, color=RED, alpha=0.85, edgecolor="white", label=team_opt)
        ax2.set_xlabel(stat)
        ax2.set_ylabel("Số cầu thủ")
        ax2.grid(axis="y", alpha=0.25)
        ax2.legend()
        fig2.tight_layout()
        st.pyplot(fig2, width="stretch")

    with st.expander("Bảng trung vị, trung bình, độ lệch chuẩn (results2.csv)"):
        r2 = load_optional("phan2/output/results2.csv")
        if r2 is not None:
            st.dataframe(r2, width="stretch", hide_index=True, height=360)

# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    df = load_players()
    st.sidebar.title("🏀 NBA 2024-25")
    if df is None:
        st.error("Không tìm thấy phan1/results.csv. Hãy chạy web từ repo gốc (đã có thư mục phan1/) rồi thử lại.")
        st.stop()
    page = st.sidebar.radio("Trang", ["Tra cứu cầu thủ", "So sánh radar", "Phân cụm cầu thủ", "Thống kê đội"])
    st.sidebar.caption(f"{len(df)} cầu thủ · {len(df.columns) - 1} thống kê · nguồn Basketball-Reference")
    clusters = load_optional("phan3/player_clusters.csv")

    if page == "Tra cứu cầu thủ":
        page_lookup(df, clusters)
    elif page == "So sánh radar":
        page_radar(df)
    elif page == "Phân cụm cầu thủ":
        page_clusters(df, clusters)
    else:
        page_teams(df)

main()
