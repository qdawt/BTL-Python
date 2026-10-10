# # # # import pandas as pd

# # # # df = pd.DataFrame({
# # # #     "Player": ["LeBron James", "Chris Paul", "Taj Gibson"],
# # # #     "Age": [40, 39, 39]
# # # # })

# # # # for idx, player in df.iterrows():
# # # #     print(idx, player["Player"], player["Age"])


# # # # names = ["Shai", "Giannis", "Jokić"]

# # # # for idx, name in enumerate(names, start=1):
# # # #     print(idx, name)
# import pandas as pd
# import matplotlib.pyplot as plt
# # # df = pd.DataFrame({
# # #     "Player": ["An", "Bình", "Cường", "Minh"],
# # #     "Team": ["BOS", "LAL", "BOS", "ASS"],
# # #     "PTS": [10, 20, 30, 12]
# # # })

# # # # team = "BOS"

# # # # print("1. Bảng ban đầu:")
# # # # print(df)

# # # # dieu_kien = df["Team"] == team

# # # # print("\n2. Điều kiện của từng dòng:")
# # # # print(dieu_kien)

# # # # team_data = df[dieu_kien]

# # # # print("\n3. Bảng sau khi lọc:")
# # # # print(team_data)
# # # values = df["PTS"].dropna()
# # # fig, ax = plt.subplots(figsize = (8, 5))
# # # ax.hist(values, bins=3, color="steelblue")

# # # ax.grid(axis="y", color="red", linewidth=2, alpha=1)
# # # ax.set_axisbelow(True)  # Lưới đỏ nằm đè lên các cột
# # # ax.set_title("Đụ má mày")

# # # # ax.set_axisbelow(True)       # Lưới nằm phía sau các cột
# # # # ax.grid(axis="y", alpha=0.3) # Bật lưới ngang
# # # plt.show()

# # teams = ["Lakers", "Warriors", "Celtics"]
# # for i, team in enumerate(teams, start=1):
# #     print(i, team) 
# fig, ax = plt.subplots(figsize = (8,5))
# bars = ax.bar(["BOS", "LAL", "MIL"], [10, 20, 15])

# plt.show()

import matplotlib.pyplot as plt

bos = [5, 10, 10, 15, 20]
lal = [20, 25, 25, 25, 30]

fig, axes = plt.subplots(
    1, 2,                   # 1 hàng, 2 biểu đồ
    figsize=(10, 4),
    sharex=True,
    sharey=True
)

# Dùng cùng các khoảng để so sánh
bins = [0, 10, 20, 30, 40]

axes[0].hist(bos, bins=bins, edgecolor="black")
axes[0].set_title("BOS")

axes[1].hist(lal, bins=bins, edgecolor="black")
axes[1].set_title("LAL")

plt.show()