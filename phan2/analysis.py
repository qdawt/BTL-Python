from pathlib import Path
import pandas as pd
import matplotlib
# Lưu biểu đồ thành ảnh, không mở hàng loạt cửa sổ.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Lấy thư mục chứa analysis.py:
#resolve: chuyển thành đường dẫn tuyệt đối
BASE_DIR = Path(__file__).resolve().parent

#Tim thu muc results.py
INPUT_FILE = BASE_DIR.parent /"phan1" / "results.csv"
OUTPUT_DIR = BASE_DIR/"output"

ALL_CHART_DIR = OUTPUT_DIR / "Histograms_all"
TEAM_CHART_DIR = OUTPUT_DIR / "Histograms_teams"

SELECT_STATS = ["PTS", "TRB", "AST", "TS%", "USG%", "BPM"]
LOWER_IS_BETTER = {"TOV", "PF", "DRtg"}
TEXT_COLUMNS = ['Player', "Team", "Pos", "Birth", "Height"]


#1. Chuẩn vị dữ liệu
if not INPUT_FILE.is_file():
    raise SystemExit(f"Không tìm thấy file CSV: {INPUT_FILE}")

df = pd.read_csv(
    INPUT_FILE,
    na_values=["N/a"],
    encoding="utf-8-sig",
)
#
required_columns = {
    "Player", "Team", "MP", *SELECT_STATS,
    "WS", "TOV", "PF", "DRtg"
}

missing_columns = required_columns - set(df.columns)

if missing_columns:
    raise SystemExit(f"CSV còn thiếu các cột: {sorted(missing_columns)}")

if df.empty:
    raise SystemExit("CSV không có dữ liệu.")
if df[["Player", "Team"]].isna().any().any():
    raise SystemExit("CSV không đủ tên cầu thủ và tên đội bóng")
#isna: phat hien xem co thieu du lieu ko
#.any() kiểm tra xem có ít nhất một giá trị True hay không.
stats = [column for column in df.columns if column not in TEXT_COLUMNS]

df[stats] = df[stats].apply(pd.to_numeric, errors = "coerce")
# thay dữ liệu bằng dạng số, nếu ko chuyển được thì cho sang NaN(errors = "coerce"
df[stats] = df[stats].replace([float("inf"),-float("inf")], float("nan"))

if df["MP"].isna().any() or (df["MP"] <= 200).any():
    raise SystemExit("Dữ liệu phần 1 cần có MP hợp lệ và MP > 200.")

teams = sorted(df["Team"].unique()) #unique : lấy các đội không trùng nhau
empty_stats = [stat for stat in stats if df[stat].isna().all()]

print(f"Số cầu thủ: {len(df)}")
print(f"Số đội: {len(teams)}")
print(f"Số cột thống kê số: {len(stats)}")
print(f"Các cột số toàn dữ liệu thiếu: {empty_stats}")
if len(teams) != 30:
    print("Lưu ý: số đội khác 30, hãy kiểm tra lại dữ liệu phần 1.")

for directory in [OUTPUT_DIR, ALL_CHART_DIR, TEAM_CHART_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Ghi cả cột chữ để thấy Birth/Height đang thiếu bao nhiêu.
df.isna().sum().rename("Missing_count").to_csv(
    OUTPUT_DIR / "missing_values.csv",
    index_label="Statistic",
    encoding="utf-8-sig",
)

# Tìm 3 người có chỉ số cao nhất và thấp nhất mỗi chỉ số
top_bottom_rows = []

for stat in stats:
    valid = df.dropna(subset=[stat])
    #valid là một dataframe

    if valid.empty:
        continue

    selections = {
        "highest": valid.nlargest(3, stat),
        "lowest": valid.nsmallest(3, stat),
    }  

    for category, selected in selections.items():
        # print("Nhóm đang xét:", category)
        # print(selected[["Player", stat]])
        for rank, (idx, player) in enumerate(selected.iterrows(), start=1):
            top_bottom_rows.append({
                "Statistic": stat, # chi so
                "Category": category, # nhom dang xet(high or low)
                "Rank": rank, # stt
                "Player": player["Player"],
                "Team": player["Team"],
                "Value": player[stat], # gia tri cua chi so dang xet
            })

pd.DataFrame(top_bottom_rows).to_csv(OUTPUT_DIR / "top_botton.csv",encoding="utf-8-sig", na_rep="N/a")

# 3. Tính median, mean, std cho toàn bộ và từng đội

summary_rows = [] #luu gia tri median, mean, std

#nhom gom cac cau thu:
groups = [("all", df)]

for team in teams:
    team_data = df[df["Team"] == team]
    groups.append((team, team_data))

for group_name, group_data in groups:
    rows = {"Team": group_name}

    for stat in stats:
        values = df[stat].dropna()

        rows[f"Median of {stat}"] = values.median() if len(values) else float("nan")
        rows[f"Mean of {stat}"] = values.mean() if len(values) else float("nan")
        rows[f"Std of {stat}"] = values.std() if len(values) > 1 else float("nan")

    summary_rows.append(rows)

summary = pd.DataFrame(summary_rows)
summary.index.name = "STT"
summary.to_csv(OUTPUT_DIR/"results2.csv",encoding="utf-8-sig", na_rep="N/a")

# 4. Vẽ histogram

# hàm đặt tên ảnh biểu đồ + đánh stt

def image_file_name(number, stat):
    name = stat.replace("/", "_")
    return f"{number:02d}_{name}.png"

cnt_image = 0

for number, stat in enumerate (stats, start=1):
    values = df[stat].dropna()

    if values.empty:
        continue

    fig, ax = plt.subplots(figsize=(8, 5))
    count,bin_edge, bars = ax.hist(
        values,
        bins='auto',
        color="skyblue",
        edgecolor="black",
    )
    #Hiện số cầu thủ trên mỗi cột
    ax.bar_label(bars, fmt="%.0f", padding=3, fontsize=8)

    #Chừa khoảng trống phía trên để nhãn không bị sát mép
    ax.margins(y=0.15)

    ax.set_title(f"Phân bố  chỉ số {stat} của các cầu thủ (n = {len(values)})")
    ax.set_xlabel(f"Chỉ số {stat}")
    ax.set_ylabel(f"Số lượng cầu thủ")
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    plt.savefig(ALL_CHART_DIR/image_file_name(number, stat), dpi=200)
    plt.close(fig)
    cnt_image += 1

print("------DONE!------")

