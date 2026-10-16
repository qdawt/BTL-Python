import os
import re
import time
import unicodedata
from io import StringIO
from difflib import get_close_matches

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, KFold, cross_val_predict
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import cloudscraper
    SCRAPER = cloudscraper.create_scraper()
except ImportError:
    SCRAPER = requests.Session()

NBA_TEAMS_2025 = [
    "ATL", "BOS", "BRK", "CHO", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHO", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def clean_salary_string(val):
    if pd.isna(val):
        return np.nan
    s = re.sub(r"[^\d.]", "", str(val))
    return float(s) if s else np.nan


def crawl_salaries_bref_2025(output_csv):
    if os.path.exists(output_csv):
        print(f"[INFO] Đã tìm thấy file lương '{output_csv}', đang đọc dữ liệu...")
        return pd.read_csv(output_csv)

    print("[INFO] Bắt đầu thu thập lương mùa 2024-25 từ basketball-reference.com (30 đội)...")
    all_records = []

    for idx, team in enumerate(NBA_TEAMS_2025, 1):
        url = f"https://www.basketball-reference.com/teams/{team}/2025.html"
        print(f"  [{idx:02d}/30] Đang tải {team}: {url}")
        try:
            resp = SCRAPER.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                print(f"    [WARN] HTTP {resp.status_code} tại đội {team}")
                time.sleep(3.5)
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            salary_table_html = None
            table_tag = soup.find("table", {"id": "salaries2"})
            if table_tag is not None:
                salary_table_html = str(table_tag)
            else:
                comments = soup.find_all(string=lambda text: isinstance(text, Comment))
                for c in comments:
                    if 'id="salaries2"' in c:
                        comment_soup = BeautifulSoup(c, "lxml")
                        t = comment_soup.find("table", {"id": "salaries2"})
                        if t is not None:
                            salary_table_html = str(t)
                            break

            if salary_table_html:
                df_team = pd.read_html(StringIO(salary_table_html))[0]
                cols = list(df_team.columns)
                player_col = cols[1]
                salary_col = cols[2]

                for _, row in df_team.iterrows():
                    player_name = str(row[player_col]).strip()
                    salary_val = clean_salary_string(row[salary_col])
                    if (
                        player_name
                        and player_name not in ["Player", "nan", "Team Totals"]
                        and not pd.isna(salary_val)
                    ):
                        all_records.append({
                            "Player_Salary_Raw": player_name,
                            "Team_Salary": team,
                            "Salary": salary_val
                        })
            else:
                print(f"    [WARN] Không tìm thấy bảng salaries2 cho đội {team}")

        except Exception as e:
            print(f"    [ERROR] Lỗi khi cào đội {team}: {e}")

        time.sleep(3.2)

    df_sal = pd.DataFrame(all_records)
    if df_sal.empty:
        raise RuntimeError("Không thu thập được dữ liệu lương! Kiểm tra lại kết nối mạng.")

    df_sal = df_sal.sort_values("Salary", ascending=False)
    df_sal_grouped = (
        df_sal.groupby("Player_Salary_Raw", as_index=False)
        .agg({"Salary": "max", "Team_Salary": "first"})
    )

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_sal_grouped.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"[INFO] Đã lưu {len(df_sal_grouped)} bản ghi lương vào '{output_csv}'.")
    return df_sal_grouped


SPECIAL_NAME_MAP = {
    "nic claxton": "nicolas claxton",
    "cam thomas": "cameron thomas",
    "herb jones": "herbert jones",
    "oggugua anunoby": "og anunoby",
    "santi aldama": "santiago aldama",
    "moe wagner": "moritz wagner",
    "kj martin": "kenyon martin",
    "enyon martin": "kenyon martin",
    "bub carrington": "carlton carrington",
    "gg jackson": "gregory jackson",
    "trey murphy": "trey murphy",
    "pj washington": "pj washington",
    "cj mccollum": "cj mccollum",
    "rj barrett": "rj barrett",
    "aj green": "aj green",
}


def normalize_player_name(name):
    if pd.isna(name):
        return ""
    text = str(name).replace("*", "").strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = text.lower()
    text = re.sub(r"[\.\'\-]", " ", text)
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return SPECIAL_NAME_MAP.get(text, text)


def merge_stats_and_salary(stats_csv, df_salary, output_merged_csv):
    df_stats = pd.read_csv(stats_csv)
    player_col = "Player" if "Player" in df_stats.columns else df_stats.columns[0]

    df_stats["name_norm"] = df_stats[player_col].apply(normalize_player_name)
    df_salary["name_norm"] = df_salary["Player_Salary_Raw"].apply(normalize_player_name)

    salary_dict = dict(zip(df_salary["name_norm"], df_salary["Salary"]))
    salary_names = list(salary_dict.keys())

    matched_salaries = []
    fuzzy_matches_log = []

    for idx, row in df_stats.iterrows():
        n_norm = row["name_norm"]
        if n_norm in salary_dict:
            matched_salaries.append(salary_dict[n_norm])
        else:
            close = get_close_matches(n_norm, salary_names, n=1, cutoff=0.85)
            if close:
                matched_salaries.append(salary_dict[close[0]])
                fuzzy_matches_log.append((row[player_col], close[0], salary_dict[close[0]]))
            else:
                matched_salaries.append(np.nan)

    df_stats["Salary"] = matched_salaries
    if fuzzy_matches_log:
        print(f"[INFO] Đã khớp mờ (Fuzzy Match) thành công {len(fuzzy_matches_log)} cầu thủ khác cách viết tên:")
        for orig, matched, sal in fuzzy_matches_log[:10]:
            print(f"   - '{orig}' <---> '{matched}' (${sal:,.0f})")

    df_merged = df_stats.dropna(subset=["Salary"]).copy()
    df_merged = df_merged[df_merged["Salary"] > 0].reset_index(drop=True)
    df_merged.drop(columns=["name_norm"], inplace=True)

    df_merged.to_csv(output_merged_csv, index=False, encoding="utf-8-sig")
    print(f"[INFO] Gộp thành công {len(df_merged)}/{len(df_stats)} cầu thủ. Đã lưu '{output_merged_csv}'.")
    return df_merged


def preprocess_and_select_features(df):
    df_clean = df.replace(["N/a", "N/A", "na", "-", ""], np.nan).copy()

    if "Pos" in df_clean.columns:
        df_clean["Pos_Main"] = df_clean["Pos"].astype(str).apply(lambda x: x.split("-")[0].strip())
    else:
        df_clean["Pos_Main"] = "UNK"

    candidate_num_cols = [
        "Age", "G", "GS", "MP/G", "MP",
        "PTS", "TRB", "AST", "STL", "BLK", "TOV",
        "PER", "TS%", "USG%", "WS", "BPM", "VORP"
    ]
    num_features = [c for c in candidate_num_cols if c in df_clean.columns]

    for col in num_features:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")

    if "Age" in df_clean.columns:
        df_clean["Age_Sq"] = df_clean["Age"] ** 2
        num_features.append("Age_Sq")

    cat_features = ["Pos_Main"]

    y = np.log(df_clean["Salary"].values)
    X = df_clean[num_features + cat_features]

    return df_clean, X, y, num_features, cat_features


def train_and_evaluate_models(X, y, num_features, cat_features, output_dir):
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler())
            ]), num_features),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore"))
            ]), cat_features)
        ]
    )

    models = {
        "Linear Regression": LinearRegression(),
        "Ridge Regression": Ridge(alpha=10.0, random_state=42),
        "Random Forest": RandomForestRegressor(
            n_estimators=300, max_depth=8, min_samples_leaf=3, random_state=42
        ),
    }
    if HAS_XGB:
        models["XGBoost"] = XGBRegressor(
            n_estimators=250, learning_rate=0.05, max_depth=4,
            subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0
        )
    else:
        models["Gradient Boosting"] = GradientBoostingRegressor(
            n_estimators=250, learning_rate=0.05, max_depth=4, random_state=42
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    metrics_list = []
    trained_pipelines = {}
    cv_predictions = {}

    print("\n" + "=" * 75)
    print("KẾT QUẢ ĐÁNH GIÁ CÁC MÔ HÌNH DỰ ĐOÁN LOG(LƯƠNG)")
    print("=" * 75)

    for name, model in models.items():
        pipe = Pipeline([
            ("prep", preprocessor),
            ("reg", model)
        ])

        pipe.fit(X_train, y_train)
        y_pred_test = pipe.predict(X_test)

        rmse_test = np.sqrt(mean_squared_error(y_test, y_pred_test))
        mae_test = mean_absolute_error(y_test, y_pred_test)
        r2_test = r2_score(y_test, y_pred_test)

        y_pred_cv = cross_val_predict(pipe, X, y, cv=kf)
        rmse_cv = np.sqrt(mean_squared_error(y, y_pred_cv))
        mae_cv = mean_absolute_error(y, y_pred_cv)
        r2_cv = r2_score(y, y_pred_cv)

        pipe.fit(X, y)
        trained_pipelines[name] = pipe
        cv_predictions[name] = y_pred_cv

        metrics_list.append({
            "Model": name,
            "Test_RMSE (log)": round(rmse_test, 4),
            "Test_MAE (log)": round(mae_test, 4),
            "Test_R2": round(r2_test, 4),
            "CV_RMSE (log)": round(rmse_cv, 4),
            "CV_MAE (log)": round(mae_cv, 4),
            "CV_R2": round(r2_cv, 4)
        })

    df_metrics = pd.DataFrame(metrics_list).sort_values("CV_R2", ascending=False)
    print(df_metrics.to_string(index=False))

    metrics_path = os.path.join(output_dir, "model_metrics.csv")
    df_metrics.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    best_model_name = df_metrics.iloc[0]["Model"]
    best_pipe = trained_pipelines[best_model_name]
    best_cv_pred = cv_predictions[best_model_name]
    print(f"\n[INFO] Mô hình tốt nhất được chọn: {best_model_name} (CV R² = {df_metrics.iloc[0]['CV_R2']:.4f})")

    return best_model_name, best_pipe, best_cv_pred, df_metrics


def analyze_valuation_and_plot(df_clean, y_true_log, y_pred_log, best_model_name, best_pipe, num_features, cat_features, output_dir):
    player_col = "Player" if "Player" in df_clean.columns else df_clean.columns[0]

    df_res = pd.DataFrame({
        "Player": df_clean[player_col],
        "Team": df_clean["Team"] if "Team" in df_clean.columns else "",
        "Pos": df_clean["Pos_Main"],
        "Age": df_clean["Age"],
        "PTS": df_clean["PTS"] if "PTS" in df_clean.columns else np.nan,
        "VORP": df_clean["VORP"] if "VORP" in df_clean.columns else np.nan,
        "Actual_Salary_USD": df_clean["Salary"],
        "Predicted_Salary_USD": np.exp(y_pred_log),
        "Log_Actual": y_true_log,
        "Log_Predicted": y_pred_log,
    })

    df_res["Log_Residual"] = df_res["Log_Actual"] - df_res["Log_Predicted"]
    df_res["Diff_Million_USD"] = (df_res["Actual_Salary_USD"] - df_res["Predicted_Salary_USD"]) / 1e6
    df_res["Actual_Million_USD"] = df_res["Actual_Salary_USD"] / 1e6
    df_res["Predicted_Million_USD"] = df_res["Predicted_Salary_USD"] / 1e6

    ranking_csv = os.path.join(output_dir, "player_valuation_ranking.csv")
    df_res.sort_values("Diff_Million_USD", ascending=False).to_csv(ranking_csv, index=False, encoding="utf-8-sig")

    top_overpaid = df_res.sort_values("Diff_Million_USD", ascending=False).head(10)
    top_underpaid = df_res.sort_values("Diff_Million_USD", ascending=True).head(10)

    print("\n" + "=" * 75)
    print("TOP 10 CẦU THỦ BỊ 'ĐỊNH GIÁ CAO' (OVERPAID - LƯƠNG THỰC TẾ >> MÔ HÌNH)")
    print("=" * 75)
    print(top_overpaid[["Player", "Team", "Age", "PTS", "Actual_Million_USD", "Predicted_Million_USD", "Diff_Million_USD"]].to_string(index=False))

    print("\n" + "=" * 75)
    print("TOP 10 CẦU THỦ BỊ 'ĐỊNH GIÁ THẤP' (UNDERPAID - LƯƠNG THỰC TẾ << MÔ HÌNH)")
    print("=" * 75)
    print(top_underpaid[["Player", "Team", "Age", "PTS", "Actual_Million_USD", "Predicted_Million_USD", "Diff_Million_USD"]].to_string(index=False))

    plt.figure(figsize=(9, 7))
    plt.scatter(df_res["Log_Actual"], df_res["Log_Predicted"], alpha=0.6, edgecolors="k", linewidth=0.5)
    min_v = min(df_res["Log_Actual"].min(), df_res["Log_Predicted"].min())
    max_v = max(df_res["Log_Actual"].max(), df_res["Log_Predicted"].max())
    plt.plot([min_v, max_v], [min_v, max_v], "r--", lw=2, label="Đường lý tưởng (y = x)")

    highlight = pd.concat([top_overpaid.head(4), top_underpaid.head(4)])
    for _, r in highlight.iterrows():
        plt.annotate(
            r["Player"],
            (r["Log_Actual"], r["Log_Predicted"]),
            xytext=(5, 5), textcoords="offset points", fontsize=8.5, fontweight="bold"
        )

    plt.title(f"So sánh Log(Lương thực tế) và Log(Lương dự đoán) - {best_model_name}")
    plt.xlabel("Log(Lương thực tế - USD)")
    plt.ylabel("Log(Lương dự đoán - USD)")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "01_actual_vs_predicted.png"), dpi=300)
    plt.close()

    reg_step = best_pipe.named_steps["reg"]
    ohe = best_pipe.named_steps["prep"].named_transformers_["cat"].named_steps["onehot"]
    cat_names = list(ohe.get_feature_names_out(cat_features))
    all_feature_names = num_features + cat_names

    if hasattr(reg_step, "feature_importances_"):
        importances = reg_step.feature_importances_
        title_imp = f"Mức độ quan trọng của các đặc trưng ({best_model_name})"
    else:
        importances = np.abs(reg_step.coef_)
        title_imp = f"Độ lớn trọng số hồi quy chuẩn hóa ({best_model_name})"

    df_imp = pd.DataFrame({"Feature": all_feature_names, "Importance": importances})
    df_imp = df_imp.sort_values("Importance", ascending=True).tail(15)

    plt.figure(figsize=(9, 6))
    plt.barh(df_imp["Feature"], df_imp["Importance"], color="steelblue", edgecolor="black")
    plt.title(title_imp)
    plt.xlabel("Mức độ ảnh hưởng đến Log(Lương)")
    plt.grid(axis="x", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "02_feature_importance.png"), dpi=300)
    plt.close()

    df_compare = pd.concat([top_underpaid.head(8), top_overpaid.head(8)]).sort_values("Diff_Million_USD")
    colors = ["#2ca02c" if val < 0 else "#d62728" for val in df_compare["Diff_Million_USD"]]

    plt.figure(figsize=(10, 7))
    plt.barh(df_compare["Player"], df_compare["Diff_Million_USD"], color=colors, edgecolor="black")
    plt.axvline(0, color="black", linewidth=1.2)
    plt.title("Top cầu thủ Định giá cao (Đỏ: Overpaid) và Định giá thấp (Xanh: Underpaid)")
    plt.xlabel("Chênh lệch: Lương thực tế - Lương dự đoán (Triệu USD)")
    plt.grid(axis="x", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "03_overpaid_underpaid.png"), dpi=300)
    plt.close()

    print(f"\n[INFO] Đã xuất toàn bộ bảng kết quả và 3 biểu đồ vào thư mục '{output_dir}'.")


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    stats_csv = os.path.abspath(os.path.join(base_dir, "..", "phan1", "results.csv"))
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    salary_csv = os.path.join(output_dir, "salaries_2024_25.csv")
    merged_csv = os.path.join(output_dir, "merged_salary_stats.csv")

    df_salary = crawl_salaries_bref_2025(salary_csv)
    df_merged = merge_stats_and_salary(stats_csv, df_salary, merged_csv)

    df_clean, X, y, num_features, cat_features = preprocess_and_select_features(df_merged)
    best_model_name, best_pipe, best_cv_pred, _ = train_and_evaluate_models(
        X, y, num_features, cat_features, output_dir
    )

    analyze_valuation_and_plot(
        df_clean, y, best_cv_pred, best_model_name, best_pipe,
        num_features, cat_features, output_dir
    )


if __name__ == "__main__":
    main()
