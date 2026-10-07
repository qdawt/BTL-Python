#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHẦN I - THU THẬP DỮ LIỆU CẦU THỦ NBA MÙA 2024-25 (Basketball-Reference)

Chạy:
    python crawl.py                 # cào + xuất results.csv
    python crawl.py --roster        # thêm Birth, Height, Weight (điểm cộng, ~30 request nữa)
    python crawl.py --list-columns  # in tên cột (data-stat) thật của từng bảng để kiểm tra mapping
    python crawl.py --refresh       # bỏ cache, tải lại từ web

Cài thư viện:
    pip install pandas requests beautifulsoup4 lxml

Cách làm:
  1. Tải 6 bảng của giải: totals, per_game, per_poss, advanced, shooting, play-by-play.
     HTML thô được lưu vào thư mục raw/ -> chạy lại lần sau không gọi web nữa.
  2. Đọc bảng bằng BeautifulSoup, lấy cột theo thuộc tính data-stat (ổn định, không bị
     rắc rối header 2 tầng) và lấy Player-ID (vd: jokicni01) làm khóa gộp.
  3. Cầu thủ bị trade giữa mùa: giữ DÒNG TỔNG (2TM/3TM/TOT) để số liệu là cả mùa,
     cột Team ghi ĐỘI CUỐI CÙNG (dòng đội cuối cùng trong nhóm dòng của cầu thủ đó).
  4. Gộp 6 bảng theo Player-ID, lọc MP > 200, sắp xếp, điền "N/a", xuất results.csv.
"""

import argparse
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment

# ----------------------------------------------------------------------------
# CẤU HÌNH
# ----------------------------------------------------------------------------
SEASON = 2025          # Basketball-Reference gọi mùa 2024-25 là NBA_2025
MIN_MP = 200           # chỉ lấy cầu thủ có tổng phút > 200
SLEEP_SECONDS = 5      # nghỉ giữa các request (giới hạn ~20 request/phút)
RAW_DIR = Path("raw")
BASE = "https://www.basketball-reference.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TOTAL_ROW_RE = re.compile(r"^(\d+TM|TOT)$")   # 2TM, 3TM, TOT
TEXT_COLS = {"Player", "Team", "Pos", "Height", "Birth", "_pid"}

# ----------------------------------------------------------------------------
# ĐỊNH NGHĨA BẢNG VÀ MAPPING CỘT
# Mỗi phần tử: (tên cột xuất ra, [các data-stat có thể có - lấy cái đầu tiên tìm thấy])
# ----------------------------------------------------------------------------
PER_GAME = [
    ("Player", ["name_display", "player"]),
    ("Team", ["_final_team"]),
    ("Pos", ["pos"]),
    ("Age", ["age"]),
    ("G", ["g", "games"]),
    ("GS", ["gs", "games_started"]),
    ("MP/G", ["mp_per_g"]),
    ("PTS", ["pts_per_g"]),
    ("TRB", ["trb_per_g"]),
    ("ORB", ["orb_per_g"]),
    ("DRB", ["drb_per_g"]),
    ("AST", ["ast_per_g"]),
    ("STL", ["stl_per_g"]),
    ("BLK", ["blk_per_g"]),
    ("TOV", ["tov_per_g"]),
    ("PF", ["pf_per_g"]),
]

TOTALS = [
    ("MP", ["mp"]),
    ("FG", ["fg"]), ("FGA", ["fga"]), ("FG%", ["fg_pct"]),
    ("3P", ["fg3"]), ("3PA", ["fg3a"]), ("3P%", ["fg3_pct"]),
    ("2P", ["fg2"]), ("2PA", ["fg2a"]), ("2P%", ["fg2_pct"]),
    ("FT", ["ft"]), ("FTA", ["fta"]), ("FT%", ["ft_pct"]),
    ("eFG%", ["efg_pct"]),
]

PER_POSS = [
    ("PTS_per100", ["pts_per_poss"]),
    ("TRB_per100", ["trb_per_poss"]),
    ("AST_per100", ["ast_per_poss"]),
    ("STL_per100", ["stl_per_poss"]),
    ("BLK_per100", ["blk_per_poss"]),
    ("TOV_per100", ["tov_per_poss"]),
    ("ORtg", ["off_rtg"]),
    ("DRtg", ["def_rtg"]),
]

ADVANCED = [
    ("PER", ["per"]),
    ("TS%", ["ts_pct"]),
    ("3PAr", ["fg3a_per_fga_pct"]),
    ("FTr", ["fta_per_fga_pct"]),
    ("USG%", ["usg_pct"]),
    ("ORB%", ["orb_pct"]), ("DRB%", ["drb_pct"]), ("TRB%", ["trb_pct"]),
    ("AST%", ["ast_pct"]), ("STL%", ["stl_pct"]), ("BLK%", ["blk_pct"]),
    ("TOV%", ["tov_pct"]),
    ("OWS", ["ows"]), ("DWS", ["dws"]), ("WS", ["ws"]), ("WS/48", ["ws_per_48"]),
    ("OBPM", ["obpm"]), ("DBPM", ["dbpm"]), ("BPM", ["bpm"]), ("VORP", ["vorp"]),
]

SHOOTING = [
    ("AvgDist", ["avg_dist"]),
    ("%FGA_2P", ["pct_fga_fg2a"]),
    ("%FGA_0-3ft", ["pct_fga_00_03"]),
    ("%FGA_3-10ft", ["pct_fga_03_10"]),
    ("%FGA_10-16ft", ["pct_fga_10_16"]),
    ("%FGA_16ft-3P", ["pct_fga_16_xx"]),
    ("%FGA_3P", ["pct_fga_fg3a"]),
    ("FG%_2P", ["fg_pct_fg2a"]),
    ("FG%_0-3ft", ["fg_pct_00_03"]),
    ("FG%_3-10ft", ["fg_pct_03_10"]),
    ("FG%_10-16ft", ["fg_pct_10_16"]),
    ("FG%_16ft-3P", ["fg_pct_16_xx"]),
    ("FG%_3P", ["fg_pct_fg3a"]),
    ("%Assisted_2P", ["pct_ast_fg2"]),
    ("%Assisted_3P", ["pct_ast_fg3"]),
    ("Dunks_%FGA", ["pct_fga_dunk"]),
    ("Dunks", ["fg_dunk", "dunks"]),
    ("Corner3_%3PA", ["pct_fg3a_corner3", "fg3a_pct_corner", "pct_fga_corner3"]),
    ("Corner3_3P%", ["fg_pct_corner3", "fg3_pct_corner", "fg3_pct_corner3"]),
]

PBP = [
    ("%Time_PG", ["pct_1"]),
    ("%Time_SG", ["pct_2"]),
    ("%Time_SF", ["pct_3"]),
    ("%Time_PF", ["pct_4"]),
    ("%Time_C", ["pct_5"]),
    ("OnCourt_per100", ["plus_minus_on"]),
    ("OnOff_per100", ["plus_minus_net"]),
    ("BadPass", ["tov_bad_pass"]),
    ("LostBall", ["tov_lost_ball"]),
    ("Foul_Shooting", ["fouls_shooting"]),
    ("Foul_Offensive", ["fouls_offensive"]),
    ("Drawn_Shooting", ["drawn_shooting"]),
    ("Drawn_Offensive", ["drawn_offensive"]),
    ("PGA", ["astd_pts"]),
    ("And1", ["and1s"]),
    ("Blkd", ["own_shots_blk", "own_shot_blk", "shots_blocked", "blocked_shots", "own_shot_blocked", "blk_by_opp", "blkd", "blocked"]),
]

# name -> (url, [id bảng có thể có], spec)
TABLES = {
    "per_game": (f"{BASE}/leagues/NBA_{SEASON}_per_game.html", ["per_game_stats", "per_game"], PER_GAME),
    "totals": (f"{BASE}/leagues/NBA_{SEASON}_totals.html", ["totals_stats", "totals"], TOTALS),
    "per_poss": (f"{BASE}/leagues/NBA_{SEASON}_per_poss.html", ["per_poss_stats", "per_poss"], PER_POSS),
    "advanced": (f"{BASE}/leagues/NBA_{SEASON}_advanced.html", ["advanced_stats", "advanced"], ADVANCED),
    "shooting": (f"{BASE}/leagues/NBA_{SEASON}_shooting.html", ["shooting_stats", "shooting"], SHOOTING),
    "play-by-play": (f"{BASE}/leagues/NBA_{SEASON}_play-by-play.html", ["pbp_stats", "play-by-play"], PBP),
}

TEAM_ALIASES = ["team_name_abbr", "team_id", "team"]


# ----------------------------------------------------------------------------
# TẢI TRANG (có cache)
# ----------------------------------------------------------------------------
def fetch(url: str, refresh: bool = False) -> str:
    """Tải HTML của url. Nếu đã có trong raw/ thì đọc từ máy, không gọi web."""
    RAW_DIR.mkdir(exist_ok=True)
    fname = re.sub(r"[^A-Za-z0-9_.-]+", "_", url.split(".com/")[-1])
    path = RAW_DIR / fname

    if path.exists() and not refresh:
        print(f"  [cache] {path}")
        return path.read_text(encoding="utf-8")

    print(f"  [web]   {url}")
    last_status = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            print(f"  lỗi mạng: {e}")
            time.sleep(10)
            continue
        last_status = r.status_code
        if r.status_code == 200:
            html = r.content.decode("utf-8", errors="replace")
            path.write_text(html, encoding="utf-8")
            time.sleep(SLEEP_SECONDS)
            return html
        if r.status_code == 429:  # bị giới hạn tốc độ -> chờ rồi thử lại
            wait = 60 * (attempt + 1)
            print(f"  bị giới hạn tốc độ (429), chờ {wait}s...")
            time.sleep(wait)
            continue
        break

    raise RuntimeError(
        f"Không tải được {url} (status {last_status}).\n"
        f"Cách khắc phục: mở link bằng trình duyệt, lưu trang (Ctrl+S, 'Webpage, HTML only') "
        f"thành file:\n    {path}\nrồi chạy lại - chương trình sẽ đọc từ file này."
    )


# ----------------------------------------------------------------------------
# PHÂN TÍCH HTML
# ----------------------------------------------------------------------------
def find_table(html: str, ids: list):
    """Tìm <table> theo id; nếu không thấy thì tìm trong các thẻ comment; cuối cùng lấy bảng lớn nhất."""
    soup = BeautifulSoup(html, "lxml")
    for i in ids:
        t = soup.find("table", id=i)
        if t is not None:
            return t
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        if "<table" in c:
            sub = BeautifulSoup(str(c), "lxml")
            for i in ids:
                t = sub.find("table", id=i)
                if t is not None:
                    return t
    tables = soup.find_all("table")
    if tables:
        print(f"  CẢNH BÁO: không thấy id {ids}, dùng bảng lớn nhất trong trang.")
        return max(tables, key=lambda t: len(t.find_all("tr")))
    raise RuntimeError(f"Không tìm thấy bảng nào với id {ids}")


def parse_table(table) -> pd.DataFrame:
    """Chuyển <table> thành DataFrame, tên cột = data-stat, thêm cột _pid (Player-ID)."""
    body = table.find("tbody") or table
    rows = []
    for tr in body.find_all("tr"):
        if "thead" in (tr.get("class") or []):   # dòng tiêu đề lặp lại giữa bảng
            continue
        rec, pid = {}, None
        for cell in tr.find_all(["th", "td"]):
            stat = cell.get("data-stat")
            if not stat:
                continue
            rec[stat] = cell.get_text(strip=True)
            if stat in ("name_display", "player"):
                pid = cell.get("data-append-csv")
                if not pid:
                    a = cell.find("a")
                    if a and a.get("href"):
                        m = re.search(r"/players/\w/(\w+)\.html", a["href"])
                        pid = m.group(1) if m else None
        if pid:
            rec["_pid"] = pid
            rows.append(rec)
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("Bảng rỗng - có thể trang chưa tải đúng.")
    return df.replace("", pd.NA)


def first_present(df: pd.DataFrame, aliases: list):
    for a in aliases:
        if a in df.columns:
            return a
    return None


def collapse_trades(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mỗi cầu thủ giữ đúng 1 dòng.
    - Cầu thủ không bị trade: giữ nguyên.
    - Cầu thủ bị trade: giữ dòng TỔNG (2TM/3TM/TOT) để số liệu là cả mùa,
      còn cột _final_team = đội của dòng cuối cùng (đội hiện tại cuối mùa).
    """
    tcol = first_present(df, TEAM_ALIASES)
    if tcol is None:
        out = df.drop_duplicates("_pid", keep="first").copy()
        out["_final_team"] = pd.NA
        return out

    is_total = df[tcol].astype(str).str.match(TOTAL_ROW_RE)
    out_rows = []
    for _, g in df.assign(_is_total=is_total).groupby("_pid", sort=False):
        if len(g) == 1:
            r = g.iloc[0].copy()
            r["_final_team"] = r[tcol]
        else:
            tot = g[g["_is_total"]]
            base = tot.iloc[0] if len(tot) else g.iloc[0]
            non_tot = g[~g["_is_total"]]
            r = base.copy()
            r["_final_team"] = non_tot.iloc[-1][tcol] if len(non_tot) else base[tcol]
        out_rows.append(r)
    return pd.DataFrame(out_rows).drop(columns="_is_total").reset_index(drop=True)


def build_table(name: str, html: str, ids: list, spec: list) -> pd.DataFrame:
    raw = parse_table(find_table(html, ids))
    raw = collapse_trades(raw).reset_index(drop=True)

    out = pd.DataFrame({"_pid": raw["_pid"]})
    missing = []
    for out_name, aliases in spec:
        col = first_present(raw, aliases)
        if col is None:
            out[out_name] = pd.NA
            missing.append(out_name)
        else:
            out[out_name] = raw[col]
    if missing:
        print(f"  CẢNH BÁO [{name}] không tìm thấy cột: {missing}")
        used = {a for n, al in spec if n in missing for a in al}
        print(f"           (chạy `python crawl.py --list-columns` để xem tên thật rồi sửa mapping)")
        print(f"           Các cột trong bảng này: {[c for c in raw.columns if c not in ('_pid', '_final_team')]}")
    return out


# ----------------------------------------------------------------------------
# ROSTER (tùy chọn): Birth, Height, Weight
# ----------------------------------------------------------------------------
def fetch_rosters(teams: list, refresh: bool) -> pd.DataFrame:
    frames = []
    for t in teams:
        url = f"{BASE}/teams/{t}/{SEASON}.html"
        try:
            html = fetch(url, refresh)
            df = parse_table(find_table(html, ["roster"]))
        except Exception as e:
            print(f"  bỏ qua roster {t}: {e}")
            continue
        sub = pd.DataFrame({"_pid": df["_pid"]})
        sub["Birth"] = df["birth_country"] if "birth_country" in df.columns else pd.NA
        sub["Height"] = df["height"] if "height" in df.columns else pd.NA
        sub["Weight"] = df["weight"] if "weight" in df.columns else pd.NA
        frames.append(sub)
    if not frames:
        return pd.DataFrame(columns=["_pid", "Birth", "Height", "Weight"])
    return pd.concat(frames).drop_duplicates("_pid", keep="first")


# ----------------------------------------------------------------------------
# GỘP, LÀM SẠCH, XUẤT
# ----------------------------------------------------------------------------
def to_numeric_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        if c not in TEXT_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results.csv")
    ap.add_argument("--min-mp", type=float, default=MIN_MP)
    ap.add_argument("--roster", action="store_true", help="lấy thêm Birth/Height/Weight từ roster 30 đội")
    ap.add_argument("--refresh", action="store_true", help="bỏ cache, tải lại")
    ap.add_argument("--list-columns", action="store_true", help="in data-stat của từng bảng rồi thoát")
    args = ap.parse_args()

    # 1) Tải HTML 6 bảng
    htmls = {}
    for name, (url, ids, spec) in TABLES.items():
        print(f"Tải bảng {name} ...")
        htmls[name] = fetch(url, args.refresh)

    if args.list_columns:
        for name, (url, ids, spec) in TABLES.items():
            df = parse_table(find_table(htmls[name], ids))
            print(f"\n== {name} ==\n{list(df.columns)}")
        return

    # 2) Parse + xử lý trade + chọn cột
    built = {}
    for name, (url, ids, spec) in TABLES.items():
        print(f"Xử lý bảng {name} ...")
        built[name] = build_table(name, htmls[name], ids, spec)

    # 3) Gộp theo Player-ID (lấy per_game làm gốc vì có Player/Team/Pos/Age)
    df = built["per_game"]
    for name in ["totals", "per_poss", "advanced", "shooting", "play-by-play"]:
        df = df.merge(built[name], on="_pid", how="left", validate="one_to_one")

    # 4) Roster (tùy chọn)
    if args.roster:
        teams = sorted(t for t in df["Team"].dropna().unique() if not TOTAL_ROW_RE.match(str(t)))
        print(f"Tải roster {len(teams)} đội ...")
        df = df.merge(fetch_rosters(teams, args.refresh), on="_pid", how="left")

    # 5) Ép kiểu số, lọc MP > 200
    df = to_numeric_cols(df)
    before = len(df)
    df = df[df["MP"] > args.min_mp].copy()
    print(f"Lọc MP > {args.min_mp:g}: {before} -> {len(df)} cầu thủ")

    # 6) Sắp xếp: tên theo bảng chữ cái, trùng tên thì tuổi giảm dần
    df["_key"] = df["Player"].str.casefold()
    df = df.sort_values(["_key", "Age"], ascending=[True, False]).drop(columns="_key")

    # 7) Sắp xếp thứ tự cột cho dễ đọc, bỏ cột khóa
    front = ["Player", "Team", "Pos", "Age", "G", "GS", "MP", "MP/G"]
    if args.roster:
        front += ["Birth", "Height", "Weight"]
    cols = front + [c for c in df.columns if c not in front and c != "_pid"]
    df = df[cols]

    # 8) Thống kê không có -> "N/a"
    df = df.fillna("N/a")
    # utf-8-sig: Excel hiển thị đúng tên có dấu (Dončić, Jokić...); pandas vẫn đọc bình thường
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"\nXong! Đã ghi {len(df)} dòng, {len(df.columns)} cột vào {args.out}")

    # File Excel để xem cho dễ (đã tách cột sẵn, không phụ thuộc dấu phân cách của máy)
    xlsx_path = Path(args.out).with_suffix(".xlsx")
    try:
        df.to_excel(xlsx_path, index=False)
        print(f"Đã ghi thêm bản Excel: {xlsx_path}")
    except ImportError:
        print("Muốn xuất file Excel, cài thêm:  pip install openpyxl  rồi chạy lại.")
    na_cols = [c for c in df.columns if (df[c] == "N/a").all()]
    if na_cols:
        print(f"CHÚ Ý: các cột toàn N/a (nhiều khả năng sai tên data-stat): {na_cols}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"LỖI: {e}", file=sys.stderr)
        sys.exit(1)