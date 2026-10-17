import argparse
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
 
import numpy as np
import pandas as pd
 
HERE = Path(__file__).resolve().parent  # thư mục chứa file code
 
# --- Các nhóm chỉ số: (tên cột, chiều tốt) ; +1 = càng cao càng tốt, -1 = càng thấp càng tốt
COMPONENTS = {
    "Impact":   [("BPM", +1), ("WS/48", +1), ("PER", +1)],
    "Offense":  [("PTS_per100", +1), ("TS%", +1), ("USG%", +1), ("AST%", +1), ("TOV%", -1)],
    "Defense":  [("DBPM", +1), ("STL%", +1), ("BLK%", +1), ("TRB%", +1)],
    "Volume":   [("VORP", +1), ("WS", +1), ("MP/G", +1)],
}
WEIGHTS = {"Impact": 0.35, "Offense": 0.25, "Defense": 0.15, "Volume": 0.25}
 
Z_CLIP = 3.0            # cắt z-score ngoài ±3 để vài cầu thủ cực đoan không làm lệch thang
FULL_RELIABILITY_MP = 1000  # đủ số phút này thì tin hoàn toàn vào chỉ số; ít hơn thì thu nhỏ về 0
 
# Thang lương ước tính (USD, mùa 2024-25: trần lương 140.588 triệu; lương tối thiểu ~1,16 triệu;
# lương tối đa ~35% trần ≈ 49,2 triệu). Đây là GIẢ ĐỊNH để quy đổi điểm -> tiền, có thể chỉnh.
MIN_SALARY = 1_157_153
MAX_SALARY = 49_200_000
SALARY_CURVE = 1.4      # >1: lương tăng chậm ở nửa dưới, vọt lên ở nhóm đầu (đúng thực tế NBA)
 
TIERS = [  # (phần trăm xếp hạng tối thiểu, tên bậc)
    (0.95, "Superstar"),
    (0.85, "All-Star"),
    (0.60, "Starter"),
    (0.25, "Rotation"),
    (0.00, "Bench"),
]
 
 
def die(msg):
    print(f"Lỗi: {msg}", file=sys.stderr)
    sys.exit(1)
 
 
def find_data():
    """results.csv nằm ở ../phan1/ (hoặc cùng thư mục với file code)."""
    for p in (HERE.parent / "phan1" / "results.csv", HERE / "results.csv"):
        if p.exists():
            return p
    return HERE.parent / "phan1" / "results.csv"
 
 
def read_csv_safe(path):
    """Đọc CSV: thử UTF-8 (có/không BOM) rồi tới cp1252 (CSV lưu từ Excel)."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, na_values=["N/a", "N/A", "n/a"])
        except UnicodeDecodeError:
            continue
    raise ValueError("không đọc được file CSV (lỗi bảng mã).")
 
 
def zscore(s):
    s = pd.to_numeric(s, errors="coerce")
    s = s.fillna(s.median())
    std = s.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=s.index)
    return ((s - s.mean()) / std).clip(-Z_CLIP, Z_CLIP)
 
 
def assign_tier(pct):
    for threshold, name in TIERS:
        if pct >= threshold:
            return name
    return TIERS[-1][1]
 
 
def build_ratings(df):
    needed = ["Player", "Team", "Pos", "Age", "G", "MP"] + \
             [c for cols in COMPONENTS.values() for c, _ in cols]
    missing = [c for c in dict.fromkeys(needed) if c not in df.columns]
    if missing:
        die(f"results.csv thiếu các cột: {missing}")
 
    out = df[["Player", "Team", "Pos", "Age", "G", "MP", "MP/G", "PTS", "TRB", "AST"]].copy()
    out["Pos_Main"] = df["Pos"].astype(str).str.split("-").str[0].str.strip()
 
    # 1) Điểm từng nhóm = trung bình z-score của các chỉ số trong nhóm
    for comp, cols in COMPONENTS.items():
        out[f"{comp}_Score"] = np.mean([sign * zscore(df[c]) for c, sign in cols], axis=0)
 
    # 2) Điểm tổng có trọng số
    out["Raw_Z"] = sum(WEIGHTS[c] * out[f"{c}_Score"] for c in COMPONENTS)
 
    # 3) Hiệu chỉnh độ tin cậy: ít phút thì thu nhỏ về mức trung bình
    mp = pd.to_numeric(df["MP"], errors="coerce").fillna(0)
    out["Reliability"] = (mp / FULL_RELIABILITY_MP).clip(0, 1).round(2)
    out["Value_Z"] = out["Raw_Z"] * out["Reliability"]
 
    # 4) Xếp hạng theo phần trăm -> điểm 0-100 và bậc
    pct = out["Value_Z"].rank(pct=True, method="average")
    out["Value_Score"] = ((pct - pct.min()) / (pct.max() - pct.min()) * 100).round(1)
    out["Tier"] = pct.apply(assign_tier)
    out["Overall_Rank"] = out["Value_Z"].rank(ascending=False, method="min").astype(int)
    out["Pos_Rank"] = out.groupby("Pos_Main")["Value_Z"].rank(ascending=False, method="min").astype(int)
 
    # 5) Quy đổi ra lương ước tính theo thang mũ
    f = ((pct - pct.min()) / (pct.max() - pct.min())) ** SALARY_CURVE
    out["Est_Value_Million_USD"] = (MIN_SALARY * (MAX_SALARY / MIN_SALARY) ** f / 1e6).round(2)
 
    score_cols = [f"{c}_Score" for c in COMPONENTS]
    out[score_cols + ["Raw_Z", "Value_Z"]] = out[score_cols + ["Raw_Z", "Value_Z"]].round(3)
 
    cols = ["Overall_Rank", "Player", "Team", "Pos", "Pos_Rank", "Age", "G", "MP/G", "PTS", "TRB", "AST",
            *score_cols, "Reliability", "Value_Z", "Value_Score", "Tier", "Est_Value_Million_USD"]
    return out.sort_values("Overall_Rank")[cols].reset_index(drop=True)
 
 
# ----------------------------------------------------------------------------
# TÌM KIẾM THEO TÊN + LỌC THEO TIER
# ----------------------------------------------------------------------------
TIER_NAMES = [name for _, name in TIERS]  # Superstar, All-Star, Starter, Rotation, Bench
SHOW_COLS = ["Overall_Rank", "Player", "Team", "Pos", "Pos_Rank", "Value_Score", "Tier",
             "Est_Value_Million_USD"]
 
 
def norm_text(text):
    """Bỏ dấu, hạ chữ thường, bỏ dấu chấm/nháy: 'Dončić' -> 'doncic', 'A.J. Green' -> 'aj green'."""
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("utf-8")
    s = s.lower().replace(".", "").replace("'", "").replace("’", "").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()
 
 
def slugify(text):
    return re.sub(r"[^A-Za-z0-9\-]+", "_", norm_text(text).replace(" ", "_")).strip("_") or "ketqua"
 
 
def search_players(ratings, query, max_suggest=5):
    """Trả về (loại kết quả, DataFrame):
       exact   : trùng tên (không phân biệt hoa/thường, dấu)
       partial : tên chứa mọi từ trong câu tìm kiếm (vd 'jam' -> LeBron James, ...)
       suggest : không có kết quả trực tiếp, đây là các gợi ý gần giống (gõ sai chính tả)
       none    : không có gì gần giống."""
    q = norm_text(query)
    empty = ratings.iloc[0:0]
    if not q:
        return "none", empty
    names = ratings["Player"].map(norm_text)
 
    exact = ratings[names == q]
    if len(exact):
        return "exact", exact
 
    tokens = q.split()
    partial = ratings[names.map(lambda n: all(t in n for t in tokens))]
    if len(partial):
        return "partial", partial
 
    scored = []
    for idx, n in names.items():
        sims = [SequenceMatcher(None, q, n).ratio()] + [SequenceMatcher(None, q, w).ratio() for w in n.split()]
        scored.append((max(sims), idx))
    scored.sort(reverse=True)
    best = [idx for sc, idx in scored if sc >= 0.6][:max_suggest]
    if best:
        return "suggest", ratings.loc[best]
    return "none", empty
 
 
def parse_tiers(items):
    """Nhận danh sách chuỗi (có thể chứa dấu phẩy). Chấp nhận tên (không phân biệt hoa/thường,
    'allstar' = 'All-Star') hoặc số thứ tự 1-5. Trả về (danh sách tier, thông báo lỗi)."""
    key = {re.sub(r"[^a-z]", "", t.lower()): t for t in TIER_NAMES}
    chosen, bad = [], []
    for raw in items:
        for x in re.split(r"[,;]", raw):
            x = x.strip()
            if not x:
                continue
            if x.isdigit() and 1 <= int(x) <= len(TIER_NAMES):
                t = TIER_NAMES[int(x) - 1]
            else:
                t = key.get(re.sub(r"[^a-z]", "", x.lower()))
            if t is None:
                sug = [key[k] for k in __import__("difflib").get_close_matches(
                    re.sub(r"[^a-z]", "", x.lower()), list(key), n=2, cutoff=0.5)]
                bad.append(f"'{x}'" + (f" (có phải {', '.join(sug)}?)" if sug else ""))
            elif t not in chosen:
                chosen.append(t)
    if bad:
        return None, "tier không hợp lệ: " + "; ".join(bad) + f". Tier hợp lệ: {', '.join(TIER_NAMES)}"
    if not chosen:
        return None, f"chưa chọn tier nào. Tier hợp lệ: {', '.join(TIER_NAMES)}"
    return chosen, None
 
 
def filter_by_tier(ratings, tiers):
    return ratings[ratings["Tier"].isin(tiers)].sort_values("Overall_Rank").reset_index(drop=True)
 
 
def save_result(df, out_dir, filename):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path
 
 
def print_players(df, detailed=False):
    cols = SHOW_COLS + (["Age", "G", "MP/G", "PTS", "TRB", "AST", "Impact_Score", "Offense_Score",
                         "Defense_Score", "Volume_Score", "Reliability"] if detailed else [])
    print(df[cols].to_string(index=False))
 
 
def do_tier_filter(ratings, tiers, out_dir, top):
    res = filter_by_tier(ratings, tiers)
    path = save_result(res, out_dir, "tier_" + "_".join(tiers) + ".csv")
    print(f"\nLọc theo tier: {', '.join(tiers)} -> {len(res)} cầu thủ")
    print(res["Tier"].value_counts().reindex(tiers).to_string())
    if len(res):
        print(f"\nTop {min(top, len(res))} trong kết quả lọc:")
        print_players(res.head(top))
    print(f"Đã lưu kết quả lọc: {path}")
    return res
 
 
def finish_search(found, query, out_dir):
    print()
    print_players(found, detailed=True)
    path = save_result(found, out_dir, f"search_{slugify(query)}.csv")
    print(f"Đã lưu kết quả tìm kiếm: {path}")
 
 
def do_search_cli(view, query, out_dir):
    """Chế độ không tương tác (--search). Có gợi ý nếu gõ sai tên."""
    kind, found = search_players(view, query)
    if kind in ("exact", "partial"):
        print(f"\nKết quả tìm '{query}': {len(found)} cầu thủ")
        finish_search(found, query, out_dir)
    elif kind == "suggest":
        print(f"\nKhông tìm thấy cầu thủ '{query}'. Có phải bạn muốn tìm:")
        for _, r in found.iterrows():
            print(f"  - {r['Player']} ({r['Team']}, hạng {r['Overall_Rank']}, {r['Tier']})")
        print("Hãy chạy lại với tên đúng, ví dụ: --search \"" + found.iloc[0]["Player"] + "\"")
    else:
        print(f"\nKhông tìm thấy cầu thủ '{query}' và không có gợi ý nào gần giống.")
 
 
# ---------------- chế độ tương tác ----------------
def prompt(text):
    try:
        return input(text).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nĐã thoát.")
        sys.exit(0)
 
 
def pick_from_list(cands, header):
    """Cho người dùng chọn trong danh sách đánh số. Trả về DataFrame đã chọn (có thể rỗng)."""
    print(header)
    for i, (_, r) in enumerate(cands.iterrows(), 1):
        print(f"  {i}. {r['Player']} ({r['Team']}, {r['Pos']}, hạng {r['Overall_Rank']}, {r['Tier']})")
    while True:
        ans = prompt("Chọn số (vd 1 hoặc 1,3), 'a' = tất cả, Enter = bỏ qua: ").lower()
        if not ans:
            return cands.iloc[0:0]
        if ans in ("a", "all"):
            return cands
        try:
            idx = [int(x) for x in re.split(r"[,\s]+", ans) if x]
            if idx and all(1 <= i <= len(cands) for i in idx):
                return cands.iloc[[i - 1 for i in dict.fromkeys(idx)]]
        except ValueError:
            pass
        print("Lựa chọn không hợp lệ.")
 
 
def interactive_search(view, out_dir):
    query = prompt("Nhập tên cầu thủ (hoặc một phần tên): ")
    if not query:
        return
    kind, found = search_players(view, query)
    if kind == "none":
        print(f"Không tìm thấy '{query}' và không có gợi ý nào gần giống.")
        return
    if kind == "exact" or (kind == "partial" and len(found) == 1):
        chosen = found
    elif kind == "partial":
        chosen = pick_from_list(found, f"Có {len(found)} cầu thủ khớp '{query}':")
    else:
        chosen = pick_from_list(found, f"Không tìm thấy '{query}'. Có phải bạn muốn tìm:")
    if len(chosen):
        finish_search(chosen, query, out_dir)
 
 
def interactive_tier(ratings, out_dir, top):
    counts = ratings["Tier"].value_counts()
    print("\nCác tier (chọn 1 hoặc nhiều, cách nhau bằng dấu phẩy):")
    for i, t in enumerate(TIER_NAMES, 1):
        print(f"  {i}. {t} ({counts.get(t, 0)} cầu thủ)")
    while True:
        ans = prompt("Nhập tier (vd 1,2 hoặc Superstar,All-Star), Enter = bỏ qua: ")
        if not ans:
            return
        tiers, err = parse_tiers([ans])
        if err is None:
            do_tier_filter(ratings, tiers, out_dir, top)
            return
        print("Lỗi:", err)
 
 
def interactive_menu(ratings, out_dir, top):
    while True:
        print("\n=== MENU ===\n  1. Tìm cầu thủ theo tên\n  2. Lọc theo tier\n  0. Thoát")
        choice = prompt("Chọn: ")
        if choice == "1":
            interactive_search(ratings, out_dir)
        elif choice == "2":
            interactive_tier(ratings, out_dir, top)
        elif choice in ("0", "q", "exit", ""):
            return
        else:
            print("Vui lòng chọn 1, 2 hoặc 0.")
 
 
def main():
    ap = argparse.ArgumentParser(description="Định giá cầu thủ NBA từ file CSV thống kê.")
    ap.add_argument("--data", default=str(find_data()), help="file thống kê results.csv")
    ap.add_argument("--out", default=str(HERE / "output" / "player_valuation_result.csv"),
                    help="file kết quả đầy đủ (mặc định: thư mục output cạnh file code)")
    ap.add_argument("--top", type=int, default=15, help="số cầu thủ in ra màn hình")
    ap.add_argument("--search", help="tìm cầu thủ theo tên (không tương tác, có gợi ý)")
    ap.add_argument("--tier", nargs="+", help="lọc theo 1 hoặc nhiều tier, vd: --tier Superstar \"All-Star\"")
    args = ap.parse_args()
 
    try:
        df = read_csv_safe(args.data)
    except FileNotFoundError:
        die(f"không tìm thấy file '{args.data}'.")
 
    ratings = build_ratings(df)
    out_path = Path(args.out)
    out_dir = out_path.parent
    save_result(ratings, out_dir, out_path.name)  # tạo thư mục output nếu chưa có
 
    print(f"Top {args.top} cầu thủ giá trị nhất:")
    print_players(ratings.head(args.top))
    print("\nSố cầu thủ mỗi bậc:")
    print(ratings["Tier"].value_counts().reindex(TIER_NAMES).to_string())
    print(f"\nĐã lưu {len(ratings)} cầu thủ vào: {out_path}")
 
    view = ratings
    if args.tier:
        tiers, err = parse_tiers(args.tier)
        if err:
            die(err)
        view = do_tier_filter(ratings, tiers, out_dir, args.top)
 
    if args.search:
        do_search_cli(view, args.search, out_dir)
    elif not args.tier:
        interactive_menu(ratings, out_dir, args.top)
 
 
if __name__ == "__main__":
    main()