#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHẦN I - THU THẬP DỮ LIỆU CẦU THỦ NBA MÙA 2024-25 (Basketball-Reference)

Chạy:
    python crawl.py                 # cào + xuất results.csv
    python crawl.py --roster        # thêm Birth, Height, Weight (điểm cộng, ~30 request nữa)
    python crawl.py --list-columns  # in tên cột (data-stat) thật của từng bảng để kiểm tra mapping
    python crawl.py --refresh       # bỏ cache, tải lại từ web
    python crawl.py --delay 6       # đổi thời gian nghỉ giữa các request (giây)
    python crawl.py --no-excel      # không xuất file .xlsx

Cài thư viện:
    pip install pandas requests beautifulsoup4 lxml openpyxl

Cách làm:
  1. Tải 6 bảng của giải: totals, per_game, per_poss, advanced, shooting, play-by-play.
     HTML thô lưu vào thư mục raw/ -> chạy lại lần sau không gọi web nữa.
  2. Trích đúng thẻ <table> theo id bằng regex (cả khi bảng nằm trong comment HTML),
     đọc bằng BeautifulSoup, lấy cột theo data-stat và Player-ID (vd: jokicni01) làm khóa gộp.
  3. Cầu thủ bị trade giữa mùa: giữ DÒNG TỔNG (2TM/3TM/TOT) để số liệu là cả mùa,
     cột Team ghi ĐỘI CUỐI CÙNG (dòng đội cuối cùng trong nhóm dòng của cầu thủ đó).
  4. Gộp 6 bảng theo Player-ID, lọc MP > 200, sắp xếp theo TÊN ĐẦU TIÊN (không dấu),
     trùng tên đầu thì tuổi giảm dần, điền "N/a", xuất results.csv.
"""

import argparse
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


SEASON = 2025          
MIN_MP = 200           
SLEEP_SECONDS = 5      
MAX_RETRIES = 4
RAW_DIR = Path("raw")
BASE = "https://www.basketball-reference.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TOTAL_ROW_RE = re.compile(r"^(\d+TM|TOT)$")   
TEXT_COLS = {"Player", "Team", "Pos", "Height", "Birth", "_pid"}


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
    ("Blkd", ["own_shots_blk", "own_shot_blk", "shots_blocked", "blocked_shots",
              "own_shot_blocked", "blk_by_opp", "blkd", "blocked"]),
]


TABLES = {
    "per_game": (f"{BASE}/leagues/NBA_{SEASON}_per_game.html", ["per_game_stats", "per_game"], PER_GAME),
    "totals": (f"{BASE}/leagues/NBA_{SEASON}_totals.html", ["totals_stats", "totals"], TOTALS),
    "per_poss": (f"{BASE}/leagues/NBA_{SEASON}_per_poss.html", ["per_poss_stats", "per_poss"], PER_POSS),
    "advanced": (f"{BASE}/leagues/NBA_{SEASON}_advanced.html", ["advanced_stats", "advanced"], ADVANCED),
    "shooting": (f"{BASE}/leagues/NBA_{SEASON}_shooting.html", ["shooting_stats", "shooting"], SHOOTING),
    "play-by-play": (f"{BASE}/leagues/NBA_{SEASON}_play-by-play.html", ["pbp_stats", "play-by-play"], PBP),
}

TEAM_ALIASES = ["team_name_abbr", "team_id", "team"]

SESSION = requests.Session()          
SESSION.headers.update(HEADERS)



def fetch(url: str, refresh: bool = False, delay: float = SLEEP_SECONDS) -> str:
    RAW_DIR.mkdir(exist_ok=True)
    fname = re.sub(r"[^A-Za-z0-9_.-]+", "_", url.split(".com/")[-1])
    path = RAW_DIR / fname

    if path.exists() and not refresh:
        html = path.read_text(encoding="utf-8")
        if "<table" in html:                       
            print(f"  [cache] {path}")
            return html
        print(f"  [cache hỏng] {path} không có bảng nào -> tải lại")

    print(f"  [web]   {url}")
    last_status = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = SESSION.get(url, timeout=30)
        except requests.RequestException as e:
            print(f"  lỗi mạng: {e}")
            time.sleep(10 * attempt)
            continue
        last_status = r.status_code
        if r.status_code == 200:
            html = r.content.decode("utf-8", errors="replace")
            if "<table" not in html:               
                print("  trang trả về không có bảng (có thể bị chặn bot), chờ 30s rồi thử lại...")
                time.sleep(30)
                continue
            tmp = path.with_suffix(path.suffix + ".tmp")   
            tmp.write_text(html, encoding="utf-8")
            tmp.replace(path)
            time.sleep(delay)
            return html
        if r.status_code in (429, 500, 502, 503, 504):     
            ra = r.headers.get("Retry-After", "")
            wait = int(ra) if ra.isdigit() else 60 * attempt
            print(f"  HTTP {r.status_code}, chờ {wait}s rồi thử lại ({attempt}/{MAX_RETRIES})...")
            time.sleep(wait)
            continue
        break

    raise RuntimeError(
        f"Không tải được {url} (status {last_status}).\n"
        f"Cách khắc phục: mở link bằng trình duyệt, lưu trang (Ctrl+S, 'Webpage, HTML only') "
        f"thành file:\n    {path}\nrồi chạy lại - chương trình sẽ đọc từ file này."
    )



def extract_table_html(html: str, ids: list) -> str:
    for i in ids:
        m = re.search(rf'<table\b[^>]*(?<![\w-])id="{re.escape(i)}"[^>]*>.*?</table>', html, re.S | re.I)
        if m:
            return m.group(0)
    found = re.findall(r'<table\b[^>]*(?<![\w-])id="([^"]+)"', html)
    raise RuntimeError(f"Không tìm thấy bảng nào có id {ids}. Các bảng có trong trang: {found}")


def parse_table(table_html: str) -> pd.DataFrame:
    table = BeautifulSoup(table_html, "lxml").find("table")
    body = table.find("tbody") or table
    rows = []
    for tr in body.find_all("tr"):
        if "thead" in (tr.get("class") or []):   
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
    tcol = first_present(df, TEAM_ALIASES)
    if tcol is None:
        out = df.drop_duplicates("_pid", keep="first").copy()
        out["_final_team"] = pd.NA
        return out.reset_index(drop=True)

    df = df.copy()
    df["_is_total"] = df[tcol].astype(str).str.match(TOTAL_ROW_RE)
    final_team = df.loc[~df["_is_total"]].groupby("_pid", sort=False)[tcol].last()

    keep = (df.assign(_prio=(~df["_is_total"]).astype(int))
              .sort_values("_prio", kind="stable")
              .drop_duplicates("_pid", keep="first")
              .sort_index())
    keep["_final_team"] = keep["_pid"].map(final_team).fillna(keep[tcol])
    return keep.drop(columns=["_is_total", "_prio"]).reset_index(drop=True)


def build_table(name: str, html: str, ids: list, spec: list) -> pd.DataFrame:
    raw = collapse_trades(parse_table(extract_table_html(html, ids)))

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
        print("           (chạy `python crawl.py --list-columns` để xem tên thật rồi sửa mapping)")
        print(f"           Các cột trong bảng này: {[c for c in raw.columns if c not in ('_pid', '_final_team')]}")
    return out



def fetch_rosters(teams: list, refresh: bool, delay: float) -> pd.DataFrame:
    frames = []
    for t in teams:
        url = f"{BASE}/teams/{t}/{SEASON}.html"
        try:
            html = fetch(url, refresh, delay)
            df = parse_table(extract_table_html(html, ["roster"]))
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



def clean_numeric(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.replace(r"[%+,]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").astype("float64")


def to_numeric_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        if c not in TEXT_COLS:
            df[c] = clean_numeric(df[c])
    return df


def strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch)).casefold()


def sort_players(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_first"] = out["Player"].map(lambda n: strip_accents(str(n).split()[0]) if str(n).split() else "")
    out["_full"] = out["Player"].map(lambda n: strip_accents(str(n)))
    out = out.sort_values(["_first", "Age", "_full"], ascending=[True, False, True], kind="stable")
    return out.drop(columns=["_first", "_full"])


def format_output(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if c in TEXT_COLS:
            continue
        s = df[c]
        nn = s.dropna()
        if len(nn) and (nn == nn.round()).all():
            df[c] = s.astype("Int64")
    df = df.astype(object)
    return df.where(df.notna(), "N/a")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results.csv")
    ap.add_argument("--min-mp", type=float, default=MIN_MP)
    ap.add_argument("--delay", type=float, default=SLEEP_SECONDS, help="giây nghỉ giữa các request")
    ap.add_argument("--roster", action="store_true", help="lấy thêm Birth/Height/Weight từ roster 30 đội")
    ap.add_argument("--refresh", action="store_true", help="bỏ cache, tải lại")
    ap.add_argument("--no-excel", action="store_true", help="không xuất file .xlsx")
    ap.add_argument("--list-columns", action="store_true", help="in data-stat của từng bảng rồi thoát")
    args = ap.parse_args()

    
    htmls = {}
    for name, (url, ids, spec) in TABLES.items():
        print(f"Tải bảng {name} ...")
        htmls[name] = fetch(url, args.refresh, args.delay)

    if args.list_columns:
        for name, (url, ids, spec) in TABLES.items():
            df = parse_table(extract_table_html(htmls[name], ids))
            print(f"\n== {name} ==\n{list(df.columns)}")
        return

    
    built = {}
    for name, (url, ids, spec) in TABLES.items():
        print(f"Xử lý bảng {name} ...")
        built[name] = build_table(name, htmls[name], ids, spec)
    htmls.clear()   

   
    df = built["per_game"]
    for name in ["totals", "per_poss", "advanced", "shooting", "play-by-play"]:
        df = df.merge(built[name], on="_pid", how="left", validate="one_to_one")

    
    if args.roster:
        teams = sorted(t for t in df["Team"].dropna().unique() if not TOTAL_ROW_RE.match(str(t)))
        print(f"Tải roster {len(teams)} đội ...")
        df = df.merge(fetch_rosters(teams, args.refresh, args.delay), on="_pid", how="left")

    
    df = to_numeric_cols(df)
    before = len(df)
    df = df[df["MP"] > args.min_mp].copy()
    print(f"Lọc MP > {args.min_mp:g}: {before} -> {len(df)} cầu thủ")
    if not 300 <= len(df) <= 600:
        print("CẢNH BÁO: số cầu thủ nằm ngoài khoảng thường gặp (300-600), kiểm tra lại cột MP / mapping.")

    
    df = sort_players(df)

    
    front = ["Player", "Team", "Pos", "Age", "G", "GS", "MP", "MP/G"]
    if args.roster:
        front += ["Birth", "Height", "Weight"]
    cols = front + [c for c in df.columns if c not in front and c != "_pid"]
    df = df[cols]

    
    dup = df[df.duplicated("Player", keep=False)]["Player"].unique()
    if len(dup):
        print(f"LƯU Ý: có tên trùng nhau (khác người, đã được xếp theo tuổi giảm dần): {list(dup)}")

    
    df = format_output(df)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"\nXong! Đã ghi {len(df)} dòng, {len(df.columns)} cột vào {args.out}")

    if not args.no_excel:
        xlsx_path = Path(args.out).with_suffix(".xlsx")
        try:
            df.to_excel(xlsx_path, index=False)
            print(f"Đã ghi thêm bản Excel: {xlsx_path}")
        except ImportError:
            print("Muốn xuất file Excel, cài thêm:  pip install openpyxl  rồi chạy lại.")

   
    na_count = (df == "N/a").sum()
    na_cols = [c for c in df.columns if na_count[c] == len(df)]
    if na_cols:
        print(f"CHÚ Ý: các cột toàn N/a (nhiều khả năng sai tên data-stat): {na_cols}")
    partial = na_count[(na_count > 0) & (na_count < len(df))].sort_values(ascending=False).head(8)
    if len(partial):
        print("Các cột có nhiều ô N/a nhất (bình thường với % khi chưa ném lần nào):")
        for c, n in partial.items():
            print(f"   {c}: {n}/{len(df)}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, pd.errors.MergeError) as e:
        print(f"LỖI: {e}", file=sys.stderr)
        sys.exit(1)
