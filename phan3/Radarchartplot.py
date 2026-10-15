import argparse
import difflib
import sys
from pathlib import Path
 
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
 
HERE = Path(__file__).resolve().parent  # thư mục chứa file code (phan3)
 
 
def find_data():
    """results.csv nằm ở ../phan1/ (hoặc cùng thư mục với file code)."""
    for p in (HERE.parent / "phan1" / "results.csv", HERE / "results.csv"):
        if p.exists():
            return p
    return HERE.parent / "phan1" / "results.csv"
 
 
DATA_FILE = find_data()
 
 
def read_csv_safe(path):
    """Đọc results.csv; thử UTF-8 (có/không BOM) rồi tới cp1252 (CSV lưu từ Excel)."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("không đọc được file CSV (lỗi bảng mã).")
 
 
 
def die(msg):
    print(f"Lỗi: {msg}", file=sys.stderr)
    sys.exit(1)
 
 
def ask_yes_no(question):
    """Hỏi y/n trong terminal. Trả về None nếu không thể hỏi (không có bàn phím)."""
    try:
        while True:
            ans = input(f"{question} (y/n): ").strip().lower()
            if ans in ("y", "yes", "c", "co", "có"):
                return True
            if ans in ("n", "no", "k", "khong", "không"):
                return False
            print("Vui lòng nhập y hoặc n.")
    except (EOFError, KeyboardInterrupt):
        return None
 
 
def find_player(df, name, retry=False):
    """Tìm cầu thủ (không phân biệt hoa/thường). Nếu gõ sai tên thì gợi ý và hỏi xác nhận."""
    mask = df["Player"].str.strip().str.lower() == name.strip().lower()
    if mask.any():
        return df[mask].iloc[0]
 
    suggestions = difflib.get_close_matches(name, df["Player"].tolist(), n=3, cutoff=0.5)
    if not suggestions:
        if retry:
            print(f"Không tìm thấy cầu thủ '{name}'. Hãy nhập lại.")
            return None
        die(f"không tìm thấy cầu thủ '{name}'.")
 
    print(f"Không tìm thấy cầu thủ '{name}'.")
    for s in suggestions:
        ok = ask_yes_no(f"Có phải bạn muốn chọn '{s}'?")
        if ok is None:  # không tương tác được
            die(f"không tìm thấy cầu thủ '{name}'. Có phải bạn muốn: {', '.join(suggestions)}?")
        if ok:
            return df[df["Player"] == s].iloc[0]
    if retry:
        print("Hãy nhập lại tên cầu thủ.")
        return None
    die(f"không tìm thấy cầu thủ '{name}'. Hãy kiểm tra lại tên rồi chạy lại.")
 
 
def numeric_columns(df):
    """Các cột có thể dùng làm thuộc tính (dạng số, bỏ Player/Team/Pos)."""
    cols = []
    for c in df.columns:
        if c in ("Player", "Team", "Pos"):
            continue
        if pd.to_numeric(df[c], errors="coerce").notna().any():
            cols.append(c)
    return cols
 
 
def parse_attributes(raw, df, valid):
    """Trả về (danh sách thuộc tính, thông báo lỗi). Lỗi = None nếu hợp lệ."""
    attrs = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
    attrs = list(dict.fromkeys(attrs))  # bỏ trùng, giữ thứ tự
    if len(attrs) < 3:
        return None, "cần ít nhất 3 thuộc tính để vẽ radar."
    lookup = {c.lower(): c for c in df.columns}
    fixed, bad = [], []
    for x in attrs:
        col = lookup.get(x.lower())
        if col is None:
            bad.append(x)
        elif col not in valid:
            bad.append(x + " (không phải dạng số)")
        else:
            fixed.append(col)
    if bad:
        msgs = []
        for x in bad:
            base = x.split(" (")[0]
            sug = difflib.get_close_matches(base, valid, n=3, cutoff=0.5)
            msgs.append(f"'{x}'" + (f" (gợi ý: {', '.join(sug)})" if sug else ""))
        return None, "thuộc tính không hợp lệ: " + "; ".join(msgs)
    return fixed, None
 
 
def prompt(text):
    try:
        return input(text).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nĐã hủy.")
        sys.exit(0)
 
 
def prompt_player(df, label):
    while True:
        name = prompt(f"Nhập tên {label}: ")
        if not name:
            continue
        row = find_player(df, name, retry=True)
        if row is not None:
            return row
 
 
def prompt_attributes(df, valid):
    print("\nCác thuộc tính hợp lệ:")
    print(", ".join(valid))
    print("(Chọn ít nhất 3, cách nhau bằng dấu phẩy, ví dụ: PTS,TRB,AST,STL,BLK,TS%)")
    while True:
        raw = prompt("Nhập Attribute: ")
        attrs, err = parse_attributes(raw, df, valid)
        if err is None:
            return attrs
        print("Lỗi:", err)
 
 
def main():
    ap = argparse.ArgumentParser(
        description="Vẽ radar so sánh hai cầu thủ. Nếu không truyền tham số, "
                    "chương trình sẽ hỏi lần lượt p1, p2, Attribute.")
    ap.add_argument("--p1", help="tên cầu thủ thứ nhất")
    ap.add_argument("--p2", help="tên cầu thủ thứ hai")
    ap.add_argument("--Attribute",
                    help="danh sách thống kê, cách nhau bởi dấu phẩy (vd: PTS,TRB,AST,STL,BLK,TS%%)")
    ap.add_argument("--data", default=str(DATA_FILE), help="file dữ liệu CSV")
    ap.add_argument("--out", default=str(HERE / "radar_chart.png"), help="file ảnh đầu ra")
    args = ap.parse_args()
 
    try:
        df = read_csv_safe(args.data)
    except FileNotFoundError:
        die(f"không tìm thấy file dữ liệu '{args.data}'.")
 
    valid = numeric_columns(df)
    if args.p1 is None or args.p2 is None or args.Attribute is None:
        print("=== RADAR SO SÁNH HAI CẦU THỦ ===")
 
    # Mỗi thông tin: nếu đã truyền bằng tham số thì dùng luôn, chưa có thì hỏi
    p1 = find_player(df, args.p1) if args.p1 else prompt_player(df, "cầu thủ thứ nhất (p1)")
    while True:
        p2 = find_player(df, args.p2) if args.p2 else prompt_player(df, "cầu thủ thứ hai (p2)")
        if p1["Player"] != p2["Player"]:
            break
        if args.p2:
            die("hai cầu thủ phải khác nhau.")
        print("Hai cầu thủ phải khác nhau, hãy nhập lại p2.")
 
    if args.Attribute:
        attrs, err = parse_attributes(args.Attribute, df, valid)
        if err:
            die(err)
    else:
        attrs = prompt_attributes(df, valid)
 
    # Ép về số ("N/a" -> NaN)
    for a in attrs:
        df[a] = pd.to_numeric(df[a], errors="coerce")
    p1 = df[df["Player"] == p1["Player"]].iloc[0]
    p2 = df[df["Player"] == p2["Player"]].iloc[0]
 
    missing = [a for a in attrs if pd.isna(p1[a]) or pd.isna(p2[a])]
    if missing:
        die(f"thiếu dữ liệu (N/a) của một trong hai cầu thủ ở: {', '.join(missing)}")
 
    # Chuẩn hóa min-max trên TOÀN BỘ cầu thủ -> mỗi thuộc tính nằm trong [0, 1]
    lo, hi = df[attrs].min(), df[attrs].max()
    span = (hi - lo).replace(0, np.nan)
    norm = lambda row: ((row[attrs].astype(float) - lo) / span).fillna(0).values
 
    v1, v2 = norm(p1), norm(p2)
 
    # Vẽ radar
    n = len(attrs)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    for vals, row, color in ((v1, p1, "tab:blue"), (v2, p2, "tab:red")):
        data = list(vals) + [vals[0]]
        ax.plot(angles, data, color=color, lw=2, label=f"{row['Player']} ({row['Team']})")
        ax.fill(angles, data, color=color, alpha=0.2)
 
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(attrs, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.5", "0.75", "1.0"], fontsize=8, color="gray")
    ax.set_title("So sánh cầu thủ (min-max trên toàn bộ dữ liệu)", pad=24)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.12))
    fig.tight_layout()
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
 
    print(pd.DataFrame({"Thuộc tính": attrs,
                        p1["Player"]: [p1[a] for a in attrs],
                        p2["Player"]: [p2[a] for a in attrs]}).to_string(index=False))
    print(f"Đã lưu biểu đồ: {args.out}")
    plt.show()
 
 
if __name__ == "__main__":
    main()