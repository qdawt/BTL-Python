from pathlib import Path

import pandas as pd
import matplotlib

# Lưu biểu đồ thành ảnh, không mở hàng loạt cửa sổ.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# Đặt analysis.py trong phan2, results.csv trong phan1.
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR.parent / "phan1" / "results.csv"
OUTPUT_DIR = BASE_DIR / "output"
ALL_CHART_DIR = OUTPUT_DIR / "histograms_all"
TEAM_CHART_DIR = OUTPUT_DIR / "histograms_teams"

SELECTED_STATS = ["PTS", "TRB", "AST", "TS%", "USG%", "BPM"] #chọn chỉ số để vẽ biểu đồ theo đội
LOWER_IS_BETTER = {"TOV", "PF", "DRtg"} #quyết định chọn đội có giá trị thấp nhất khi so sánh

# Birth là quốc tịch, Height thường là chuỗi feet-inch: không ép thành số.
TEXT_COLUMNS = ["Player", "Team", "Pos", "Birth", "Height"]


# ==========================================================
# 1. Đọc và chuẩn bị dữ liệu
# ==========================================================
if not INPUT_FILE.is_file():
    raise SystemExit(f"Không tìm thấy CSV: {INPUT_FILE}")

df = pd.read_csv(INPUT_FILE, na_values=["N/a"], encoding="utf-8-sig")

required_columns = {
    "Player", "Team", "MP", *SELECTED_STATS,
    "WS", "TOV", "PF", "DRtg",
}
missing_columns = required_columns - set(df.columns)
if missing_columns:
    raise SystemExit(f"CSV thiếu các cột: {sorted(missing_columns)}")
if df.empty:
    raise SystemExit("CSV không có dữ liệu.")
if df[["Player", "Team"]].isna().any().any():
    raise SystemExit("CSV có dòng thiếu tên cầu thủ hoặc tên đội.")

for column in ["Player", "Team"]:
    df[column] = df[column].astype(str).str.strip()
    if df[column].eq("").any():
        raise SystemExit(f"Cột {column} có giá trị rỗng.")

# Các cột số, bao gồm cả cột đang hoàn toàn thiếu như Weight.
stats = [column for column in df.columns if column not in TEXT_COLUMNS]

# Giá trị không chuyển được trở thành NaN; không điền 0.
df[stats] = df[stats].apply(pd.to_numeric, errors="coerce")
df[stats] = df[stats].replace([float("inf"), -float("inf")], float("nan"))

if df["MP"].isna().any() or (df["MP"] <= 200).any():
    raise SystemExit("Dữ liệu phần 1 cần có MP hợp lệ và MP > 200.")

teams = sorted(df["Team"].unique())
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


# ==========================================================
# 2. Tìm ba cầu thủ cao nhất và thấp nhất mỗi chỉ số
# ==========================================================
top_bottom_rows = []

for stat in stats:
    valid = df.dropna(subset=[stat])
    if valid.empty:
        continue

    # Nếu bằng điểm: giữ đúng 3 người theo thứ tự dòng trong CSV.
    selections = {
        "highest": valid.nlargest(3, stat),
        "lowest": valid.nsmallest(3, stat),
    }

    for category, selected in selections.items():
        for rank, (_, player) in enumerate(selected.iterrows(), start=1):
            top_bottom_rows.append({
                "Statistic": stat,
                "Category": category,
                "Rank": rank,
                "Player": player["Player"],
                "Team": player["Team"],
                "Value": player[stat],
            })

pd.DataFrame(top_bottom_rows).to_csv(
    OUTPUT_DIR / "top_bottom.csv", index=False, encoding="utf-8-sig",
)


# ==========================================================
# 3. Tính median, mean, std cho toàn bộ và từng đội
# ==========================================================
summary_rows = []
count_rows = []

groups = [("all", df)]
groups.extend((team, df[df["Team"] == team]) for team in teams)

for group_name, group_data in groups:
    row = {"Team": group_name}
    count_row = {"Team": group_name}

    for stat in stats:
        values = group_data[stat].dropna()
        count_row[stat] = len(values)
        row[f"Median of {stat}"] = values.median() if len(values) else float("nan")
        row[f"Mean of {stat}"] = values.mean() if len(values) else float("nan")
        # ddof=1: độ lệch chuẩn mẫu, chia cho n-1.
        # Nếu chỉ có 0 hoặc 1 giá trị hợp lệ thì không xác định được.
        row[f"Std of {stat}"] = values.std(ddof=1) if len(values) > 1 else float("nan")

    summary_rows.append(row)
    count_rows.append(count_row)

summary = pd.DataFrame(summary_rows)
summary.index.name = "STT"
summary.to_csv(
    OUTPUT_DIR / "results2.csv", encoding="utf-8-sig", na_rep="N/a",
)

# Số quan sát dùng để tính từng chỉ số, giúp giải thích dữ liệu thiếu.
pd.DataFrame(count_rows).to_csv(
    OUTPUT_DIR / "valid_counts.csv", index=False,
    encoding="utf-8-sig", na_rep="N/a",
)


# ==========================================================
# 4. Histogram trên toàn bộ cầu thủ
# ==========================================================
def image_filename(number, stat):
    """Thêm số thứ tự và thay ký tự đặc biệt để tránh trùng/lỗi tên ảnh."""
    safe_name = "".join(char if char.isalnum() else "_" for char in stat)
    return f"{number:02d}_{safe_name}.png"


all_image_count = 0
for number, stat in enumerate(stats, start=1):
    values = df[stat].dropna()
    if values.empty:
        continue

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(values, bins=20, color="steelblue", edgecolor="white")
    ax.set_title(f"{stat} distribution - all players (n={len(values)})")
    ax.set_xlabel(stat)
    ax.set_ylabel("Number of players")
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ALL_CHART_DIR / image_filename(number, stat), dpi=150)
    plt.close(fig)
    all_image_count += 1


# ==========================================================
# 5. Histogram theo đội cho sáu chỉ số tiêu biểu
# ==========================================================
team_image_count = 0
for number, stat in enumerate(SELECTED_STATS, start=1):
    all_values = df[stat].dropna()
    if all_values.empty:
        print(f"Bỏ qua {stat}: không có dữ liệu để vẽ theo đội.")
        continue

    minimum = all_values.min()
    maximum = all_values.max()
    if minimum == maximum:
        minimum -= 0.5
        maximum += 0.5

    # Thường là 6 hàng x 5 cột cho 30 đội; tự tăng hàng nếu có thêm đội.
    number_of_rows = max(1, (len(teams) + 4) // 5)
    fig, axes = plt.subplots(
        number_of_rows, 5,
        figsize=(18, number_of_rows * 3.3),
        sharex=True, sharey=True, squeeze=False,
    )

    for ax, team in zip(axes.flat, teams):
        values = df.loc[df["Team"] == team, stat].dropna()
        ax.hist(
            values, bins=10, range=(minimum, maximum),
            color="darkorange", edgecolor="white",
        )
        ax.set_title(f"{team} (n={len(values)})")
        ax.set_xlim(minimum, maximum)
        ax.set_axisbelow(True)
        ax.grid(axis="y", alpha=0.25)

    for ax in list(axes.flat)[len(teams):]:
        ax.set_visible(False)

    fig.suptitle(f"{stat} distribution by team", fontsize=18)
    fig.supxlabel(stat)
    fig.supylabel("Number of players")
    fig.tight_layout(rect=(0.03, 0.03, 1, 0.97))
    fig.savefig(TEAM_CHART_DIR / image_filename(number, stat), dpi=150)
    plt.close(fig)
    team_image_count += 1
    print(f"Đã vẽ phân bố {stat} theo đội.")


# ==========================================================
# 6. So sánh đội bằng trung bình chỉ số của cầu thủ
# ==========================================================
team_means = df.groupby("Team")[stats].mean()
team_means.to_csv(
    OUTPUT_DIR / "team_means.csv", encoding="utf-8-sig", na_rep="N/a",
)

comparison_rows = []
for stat in stats:
    values = team_means[stat].dropna()
    if values.empty:
        continue

    highest_value = values.max()
    lowest_value = values.min()
    highest_teams = values[values == highest_value].index.tolist()
    lowest_teams = values[values == lowest_value].index.tolist()
    choose_lowest = stat in LOWER_IS_BETTER

    comparison_rows.append({
        "Statistic": stat,
        "Highest_teams": ", ".join(highest_teams),
        "Highest_mean": highest_value,
        "Lowest_teams": ", ".join(lowest_teams),
        "Lowest_mean": lowest_value,
        "Selection_rule": "min" if choose_lowest else "max",
        "Selected_teams": ", ".join(lowest_teams if choose_lowest else highest_teams),
        "Selected_mean": lowest_value if choose_lowest else highest_value,
    })

pd.DataFrame(comparison_rows).to_csv(
    OUTPUT_DIR / "team_comparison.csv", index=False, encoding="utf-8-sig",
)

report_stats = ["PTS", "TRB", "AST", "TS%", "BPM", "WS", "TOV", "PF", "DRtg"]
report_table = team_means[report_stats]
report_table.to_csv(
    OUTPUT_DIR / "team_report.csv", encoding="utf-8-sig", na_rep="N/a",
)


print("\nTrung bình các chỉ số tiêu biểu theo đội:")
print(report_table.round(3).to_string())
print(f"\nĐã lưu {all_image_count} ảnh toàn giải và {team_image_count} ảnh tổng hợp theo đội.")
print(f"Đã lưu kết quả vào: {OUTPUT_DIR}")