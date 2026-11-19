import json, yaml
import pandas as pd

cfg = yaml.safe_load(open("configs/porto.yaml", encoding="utf-8"))
llm = cfg["kpi"]["k7"]["llm"]
lab = pd.read_csv(llm["labels_path"])
df = pd.read_csv("data/processed/reviews_valid.csv")
txt = df.set_index("id")["comment_clean"]

s = lab[lab["evidence"].notna()].sample(20, random_state=1)
for _, r in s.iterrows():
    print(f"[{r['id']}] {r['aspects_criticized']}")
    print("  evidence:", r["evidence"])
    print("  review  :", str(txt.get(r["id"], ""))[:300], "\n")