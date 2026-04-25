import streamlit as st
import random
import csv
from datetime import datetime
import os
import re
import io
from urllib.request import urlopen
from urllib.error import URLError

DATA_PATH = os.path.join("stage4_reorganized_top4_thr0_65_with_id.csv")
LOCAL_RESULTS_PATH = os.path.join("preview_results.csv")


DATA_CSV_URL = os.getenv("DATA_CSV_URL", "")


@st.cache_data
def load_data(path, csv_url=""):
    samples = []

    def to_sample(row):
        return {
            "id": row.get("id") or row.get("conversation_id", ""),
            "question": row.get("question", ""),
            "candidate_1": row.get("candidate_1") or row.get("candidate1", ""),
            "candidate_2": row.get("candidate_2") or row.get("candidate2", ""),
            "candidate_3": row.get("candidate_3") or row.get("candidate3", ""),
            "candidate_4": row.get("candidate_4") or row.get("candidate4", ""),
        }

    # 优先从 URL 读取（适合云部署）
    if csv_url:
        try:
            with urlopen(csv_url) as resp:
                content = resp.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                samples.append(to_sample(row))
            if samples:
                return samples, "cloud"
        except (URLError, UnicodeDecodeError, csv.Error):
            # URL 失败则回退本地文件
            pass

    if not os.path.exists(path):
        return samples, "none"

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            samples.append(to_sample(row))
    return samples, "local"


def render_candidate_text(text: str):
    """Render candidate text while extracting [sponsored ...] into a separate paragraph."""
    if not text:
        st.write("")
        return


    def normalize_markdown_headings(raw: str) -> str:
        # 先把行内标题（如：文字 #### 标题）断到新行，便于按 markdown 标题解析
        raw = re.sub(r"(?<!\n)\s+(#{1,6})\s+", r"\n\1 ", raw)

        # 自动将连续编号（如1. xxx 2. xxx）分行
        def split_numbered_list(text):
            # 用正则将 1. xxx 2. xxx 3. xxx 拆成多行
            # 只处理英文句点编号（防止误伤小数点等），且编号后有空格
            pattern = r"(\d+\.)\s+"
            # 在每个编号前加特殊分隔符，再split
            text = re.sub(pattern, r"|||\1 ", text)
            lines = [l.strip() for l in text.split("|||") if l.strip()]
            # 如果分出来多行且每行以编号开头，则用markdown有序列表渲染
            if len(lines) > 1 and all(re.match(r"^\d+\. ", l) for l in lines):
                return "\n".join(lines)
            return text

        raw = split_numbered_list(raw)

        # 保留 markdown 标题语义，但整体降三级，避免标题过大（# -> ####）
        def _shift_heading(match):
            hashes = match.group(1)
            level = min(len(hashes) + 3, 6)
            return "#" * level + " "

        # 仅处理行首标题（上面已将行内标题改写为行首）
        return re.sub(r"(?m)^(#{1,6})\s+", _shift_heading, raw)

    pattern = re.compile(r"\[(?i:sponsored)\s+(.*?)\]", flags=re.DOTALL)
    cursor = 0

    for match in pattern.finditer(text):
        # 前置普通段落
        normal_part = text[cursor:match.start()].strip()
        if normal_part:
            st.markdown(normalize_markdown_headings(normal_part))

        # sponsored 段落（独立显示，不改颜色）
        sponsored_content = match.group(1).strip()
        if sponsored_content:
            st.markdown(
                f"<p style='color:#8A8A8A;'><strong>Sponsored:</strong> {sponsored_content}</p>",
                unsafe_allow_html=True,
            )

        cursor = match.end()

    # 后置普通段落
    tail = text[cursor:].strip()
    if tail:
        st.markdown(normalize_markdown_headings(tail))


data, data_source = load_data(DATA_PATH, DATA_CSV_URL)

if not data:
    st.error(f"No data found. Please check: {DATA_PATH}")
    st.stop()

if data_source == "cloud":
    data_source_msg = f"Data source: Cloud URL ({DATA_CSV_URL})"
elif data_source == "local":
    data_source_msg = f"Data source: Local file ({DATA_PATH})"
else:
    data_source_msg = "Data source: Unknown"

# 仅在终端打印来源，不在问卷页面显示；并避免每次 rerun 重复刷屏
if st.session_state.get("_last_data_source_msg") != data_source_msg:
    print(f"[Ad-Arena] {data_source_msg}")
    st.session_state["_last_data_source_msg"] = data_source_msg


# 随机选取一个样本和两个不同的候选
def pick_sample_and_candidates():
    sample = random.choice(data)
    candidates = [sample.get(f"candidate_{i}", "") for i in range(1, 5)]
    # 过滤空候选
    candidates = [c for c in candidates if c]
    idxs = random.sample(range(len(candidates)), 2)
    cand1, cand2 = candidates[idxs[0]], candidates[idxs[1]]
    # 记录索引，便于保存
    return sample, cand1, cand2, idxs[0]+1, idxs[1]+1

if "current_sample" not in st.session_state:
    s, c1, c2, idx1, idx2 = pick_sample_and_candidates()
    st.session_state.current_sample = s
    st.session_state.candidate_1 = c1
    st.session_state.candidate_2 = c2
    st.session_state.candidate_1_idx = idx1
    st.session_state.candidate_2_idx = idx2

sample = st.session_state.current_sample
shown_candidate_1 = st.session_state.candidate_1
shown_candidate_2 = st.session_state.candidate_2
candidate_1_idx = st.session_state.candidate_1_idx
candidate_2_idx = st.session_state.candidate_2_idx


st.info("Preview mode: Submissions are saved to local preview_results.csv")

user_id = st.text_input("User ID", placeholder="e.g. user_001")


st.markdown("<p style='font-size:28px; font-weight:700;'>Assume you are talking with a generative AI assistant.</p>", unsafe_allow_html=True)
st.markdown(f"### Question\n{sample['question']}")


col1, col2 = st.columns(2)
with col1:
    st.subheader("1")
    render_candidate_text(shown_candidate_1)
with col2:
    st.subheader("2")
    render_candidate_text(shown_candidate_2)


# 五个主观评价问题
q_labels = [
    "Q1. Naturalness of flow — Which version reads more smoothly and feels less disruptive?",
    "Q2. Helpfulness — Which version better answers the user's question?",
    "Q3. Ad noticeability — In which version does the recommendation stand out more?",
    "Q4. Appropriateness — Which version feels more trustworthy and less manipulative?",
    "Q5. Overall preference — All things considered, which version is preferred?",
]
q_options = ["1", "2", "tie"]

choices = []
for i, label in enumerate(q_labels):
    st.markdown(f"<p style='font-size:18px; font-weight:600; margin: 0.5rem 0 0.2rem 0;'>{label}</p>", unsafe_allow_html=True)
    choice = st.radio(
        label,
        q_options,
        index=None,
        key=f"q{i+1}_{sample['id']}",
        label_visibility="collapsed",
    )
    choices.append(choice)

# ====== 保存函数 ======

def save_result(sample_id, user_id, choices, candidate_1_idx, candidate_2_idx):
    payload = {
        "sample_id": sample_id,
        "user_id": user_id,
        "candidate_1_idx": candidate_1_idx,
        "candidate_2_idx": candidate_2_idx,
        "Q1": choices[0],
        "Q2": choices[1],
        "Q3": choices[2],
        "Q4": choices[3],
        "Q5": choices[4],
        "timestamp": datetime.utcnow().isoformat(),
    }
    file_exists = os.path.exists(LOCAL_RESULTS_PATH)
    with open(LOCAL_RESULTS_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["sample_id", "user_id", "candidate_1_idx", "candidate_2_idx", "Q1", "Q2", "Q3", "Q4", "Q5", "timestamp"],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(payload)


# ====== 提交按钮 ======
if st.button("Submit"):
    if not user_id.strip():
        st.warning("Please enter your User ID before submitting.")
        st.stop()
    if not all(choices):
        st.warning("Please answer all 5 questions before submitting.")
        st.stop()
    save_result(sample["id"], user_id.strip(), choices, candidate_1_idx, candidate_2_idx)
    st.success("Saved!")
    # 换下一题
    s, c1, c2, idx1, idx2 = pick_sample_and_candidates()
    st.session_state.current_sample = s
    st.session_state.candidate_1 = c1
    st.session_state.candidate_2 = c2
    st.session_state.candidate_1_idx = idx1
    st.session_state.candidate_2_idx = idx2
    st.rerun()