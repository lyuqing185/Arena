import streamlit as st
import random
import csv
from datetime import datetime
import os
import re
import io
from itertools import combinations
from urllib.request import urlopen
from urllib.error import URLError

st.set_page_config(
    page_title="Part 1 Position Survey",
    layout="wide",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "stage4_reorganized_top4_thr0_65_with_id.csv")
LOCAL_RESULTS_PATH = os.path.join("preview_results_part1_candidate.csv")
DATA_CSV_URL = os.getenv("DATA_CSV_URL", "")

# Current program version: ordinary candidate fields only.
# For the prime version, copy this file and change CANDIDATE_FIELD_SPECS.
CANDIDATE_FIELD_SPECS = [
    ("candidate_1", ["candidate_1", "candidate1"]),
    ("candidate_2", ["candidate_2", "candidate2"]),
    ("candidate_3", ["candidate_3", "candidate3"]),
    ("candidate_4", ["candidate_4", "candidate4"]),
]

Q_LABELS = [
    "Q1. Naturalness of flow — Which version reads more smoothly and feels less disruptive?",
    "Q2. Helpfulness — Which version better answers the user's question?",
    "Q3. Ad noticeability — In which version does the recommendation stand out more?",
    "Q4. Appropriateness — Which version feels more trustworthy and less manipulative?",
    "Q5. Overall preference — All things considered, which version is preferred?",
]

Q_KEYS = ["Q1", "Q2", "Q3", "Q4", "Q5"]
Q_OPTIONS = ["Version A", "Version B", "Tie"]


def inject_layout_css():
    st.html(
        """
        <style>
        .block-container {
            max-width: 1150px;
            padding-top: 2.5rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }

        div[role="radiogroup"] label p {
            font-size: 18px !important;
        }

        .candidate-card {
            border: 1px solid #E5E7EB;
            border-radius: 10px;
            padding: 1rem 1.1rem;
            background-color: #FFFFFF;
            min-height: 280px;
        }

        .meta-text {
            color: #666666;
            font-size: 0.9rem;
        }
        </style>
        """
    )


def first_nonempty(row, names):
    for name in names:
        value = row.get(name, "")
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


@st.cache_data
def load_data(path, csv_url=""):
    samples = []

    def to_sample(row, row_idx):
        sample_id = row.get("id") or row.get("conversation_id") or f"row_{row_idx}"
        sample = {
            "id": str(sample_id),
            "question": row.get("question", ""),
            "context": row.get("context", ""),
            "turn": row.get("turn", ""),
        }
        for canonical_field, possible_names in CANDIDATE_FIELD_SPECS:
            sample[canonical_field] = first_nonempty(row, possible_names)
        return sample

    if csv_url:
        try:
            with urlopen(csv_url) as resp:
                content = resp.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))
            for row_idx, row in enumerate(reader):
                samples.append(to_sample(row, row_idx))
            if samples:
                return samples, "cloud"
        except (URLError, UnicodeDecodeError, csv.Error):
            pass

    if not os.path.exists(path):
        return samples, "none"

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader):
            samples.append(to_sample(row, row_idx))
    return samples, "local"


@st.cache_data
def build_task_pool(samples):
    """Expand each CSV row into all candidate-pair tasks.

    If one row has 4 non-empty candidates, it creates 6 tasks:
    1-vs-2, 1-vs-3, 1-vs-4, 2-vs-3, 2-vs-4, 3-vs-4.
    """
    task_pool = []

    for sample in samples:
        candidates = []
        for canonical_field, _ in CANDIDATE_FIELD_SPECS:
            text = sample.get(canonical_field, "")
            if text and str(text).strip():
                candidates.append((canonical_field, str(text).strip()))

        for (field_a, text_a), (field_b, text_b) in combinations(candidates, 2):
            task_id = f"{sample['id']}__{field_a}_vs_{field_b}"
            task_pool.append({
                "task_id": task_id,
                "sample_id": sample["id"],
                "question": sample.get("question", ""),
                "context": sample.get("context", ""),
                "turn": sample.get("turn", ""),
                "field_a": field_a,
                "field_b": field_b,
                "text_a": text_a,
                "text_b": text_b,
            })

    # Fixed order gives deterministic coverage. We randomize left/right display separately.
    return task_pool


def render_candidate_text(text: str):
    """Render candidate text while extracting [sponsored ...] into a separate paragraph."""
    if not text:
        st.write("")
        return

    def split_numbered_list(raw: str) -> str:
        pattern = r"(\d+\.)\s+"
        marked = re.sub(pattern, r"|||\1 ", raw)
        lines = [line.strip() for line in marked.split("|||") if line.strip()]
        if len(lines) > 1 and all(re.match(r"^\d+\. ", line) for line in lines):
            return "\n".join(lines)
        return raw

    def normalize_markdown_headings(raw: str) -> str:
        raw = re.sub(r"(?<!\n)\s+(#{1,6})\s+", r"\n\1 ", raw)
        raw = split_numbered_list(raw)

        def _shift_heading(match):
            hashes = match.group(1)
            level = min(len(hashes) + 3, 6)
            return "#" * level + " "

        return re.sub(r"(?m)^(#{1,6})\s+", _shift_heading, raw)

    pattern = re.compile(r"\[(?i:sponsored)\s+(.*?)\]", flags=re.DOTALL)
    cursor = 0

    for match in pattern.finditer(text):
        normal_part = text[cursor:match.start()].strip()
        if normal_part:
            st.markdown(normalize_markdown_headings(normal_part))

        sponsored_content = match.group(1).strip()
        if sponsored_content:
            st.markdown(
                f"<p style='color:#8A8A8A;'><strong>Sponsored:</strong> {sponsored_content}</p>",
                unsafe_allow_html=True,
            )

        cursor = match.end()

    tail = text[cursor:].strip()
    if tail:
        st.markdown(normalize_markdown_headings(tail))


def parse_context(context_raw: str):
    if not context_raw or not str(context_raw).strip():
        return []

    text = str(context_raw)
    pattern = re.compile(
        r"\[User:(.*?)\]\s*\[Response:(.*?)\]",
        flags=re.DOTALL,
    )

    exchanges = []
    for match in pattern.finditer(text):
        user_text = match.group(1).strip()
        assistant_text = match.group(2).strip()

        if user_text or assistant_text:
            exchanges.append({
                "user": user_text,
                "assistant": assistant_text,
            })

    return exchanges


def render_previous_context(context_raw: str, turn):
    try:
        turn_num = int(turn)
    except Exception:
        turn_num = 1

    if turn_num <= 1:
        return

    exchanges = parse_context(context_raw)
    if not exchanges:
        return

    with st.expander("Previous conversation context", expanded=True):
        for idx, exchange in enumerate(exchanges):
            if exchange.get("user"):
                st.markdown("**User:**")
                st.markdown(exchange["user"])

            if exchange.get("assistant"):
                st.markdown("**Assistant:**")
                render_candidate_text(exchange["assistant"])

            if idx < len(exchanges) - 1:
                st.divider()


def load_completed_task_ids(results_path):
    if not os.path.exists(results_path):
        return set()

    completed = set()
    with open(results_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            task_id = row.get("task_id", "")
            if task_id:
                completed.add(task_id)
    return completed


def get_next_unfinished_task(task_pool, results_path):
    completed = load_completed_task_ids(results_path)
    for task in task_pool:
        if task["task_id"] not in completed:
            return task, completed
    return None, completed


def prepare_display_task(task):
    """Keep the pair fixed, but randomize whether field_a or field_b appears on the left."""
    display_key = f"display_order_{task['task_id']}"
    if display_key not in st.session_state:
        st.session_state[display_key] = random.choice(["AB", "BA"])

    if st.session_state[display_key] == "AB":
        return {
            **task,
            "left_field": task["field_a"],
            "left_text": task["text_a"],
            "right_field": task["field_b"],
            "right_text": task["text_b"],
            "display_order": "AB",
        }

    return {
        **task,
        "left_field": task["field_b"],
        "left_text": task["text_b"],
        "right_field": task["field_a"],
        "right_text": task["text_a"],
        "display_order": "BA",
    }


def choice_to_machine_value(choice):
    if choice == "Version A":
        return "left"
    if choice == "Version B":
        return "right"
    if choice == "Tie":
        return "tie"
    return ""


def winner_field(choice, display_task):
    machine_choice = choice_to_machine_value(choice)
    if machine_choice == "left":
        return display_task["left_field"]
    if machine_choice == "right":
        return display_task["right_field"]
    if machine_choice == "tie":
        return "tie"
    return ""


def save_result(display_task, user_id, choices):
    payload = {
        "task_id": display_task["task_id"],
        "sample_id": display_task["sample_id"],
        "user_id": user_id,
        "question": display_task["question"],
        "pair_field_a": display_task["field_a"],
        "pair_field_b": display_task["field_b"],
        "left_field": display_task["left_field"],
        "right_field": display_task["right_field"],
        "display_order": display_task["display_order"],
        "timestamp": datetime.utcnow().isoformat(),
    }

    for q_key in Q_KEYS:
        raw_choice = choices.get(q_key, "")
        payload[f"{q_key}_choice"] = choice_to_machine_value(raw_choice)
        payload[f"{q_key}_winner_field"] = winner_field(raw_choice, display_task)

    fieldnames = [
        "task_id", "sample_id", "user_id", "question",
        "pair_field_a", "pair_field_b", "left_field", "right_field",
        "display_order",
        "Q1_choice", "Q1_winner_field",
        "Q2_choice", "Q2_winner_field",
        "Q3_choice", "Q3_winner_field",
        "Q4_choice", "Q4_winner_field",
        "Q5_choice", "Q5_winner_field",
        "timestamp",
    ]

    file_exists = os.path.exists(LOCAL_RESULTS_PATH)
    with open(LOCAL_RESULTS_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(payload)


def reset_choice_state(task_id):
    for q_key in Q_KEYS:
        key = f"{q_key}_{task_id}"
        if key in st.session_state:
            del st.session_state[key]


def main():
    inject_layout_css()

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

    if st.session_state.get("_last_data_source_msg") != data_source_msg:
        print(f"[Ad-Arena] {data_source_msg}")
        st.session_state["_last_data_source_msg"] = data_source_msg

    task_pool = build_task_pool(data)
    task, completed = get_next_unfinished_task(task_pool, LOCAL_RESULTS_PATH)

    st.title("Part 1 Position Survey")
    st.markdown(
        f"<div class='meta-text'>Completed tasks: {len(completed)} / {len(task_pool)}</div>",
        unsafe_allow_html=True,
    )

    if not task_pool:
        st.error("No valid candidate pairs were found. Please check whether candidate fields are present and non-empty.")
        st.stop()

    if task is None:
        st.success("All candidate-pair tasks have been completed.")
        st.stop()

    display_task = prepare_display_task(task)

    user_id = st.text_input("User ID", placeholder="e.g. user_001")

    render_previous_context(display_task.get("context", ""), display_task.get("turn", 1))

    st.markdown(f"### Question\n{display_task['question']}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Version A")
        with st.container(border=True):
            render_candidate_text(display_task["left_text"])

    with col2:
        st.subheader("Version B")
        with st.container(border=True):
            render_candidate_text(display_task["right_text"])

    choices = {}
    for q_key, label in zip(Q_KEYS, Q_LABELS):
        st.markdown(
            f"<p style='font-size:18px; font-weight:600; margin: 0.5rem 0 0.2rem 0;'>{label}</p>",
            unsafe_allow_html=True,
        )
        choices[q_key] = st.radio(
            label,
            Q_OPTIONS,
            index=None,
            key=f"{q_key}_{display_task['task_id']}",
            label_visibility="collapsed",
            horizontal=True,
        )

    if st.button("Submit"):
        if not user_id.strip():
            st.warning("Please enter your User ID before submitting.")
            st.stop()

        if not all(choices.values()):
            st.warning("Please answer all 5 questions before submitting.")
            st.stop()

        save_result(display_task, user_id.strip(), choices)
        reset_choice_state(display_task["task_id"])

        order_key = f"display_order_{display_task['task_id']}"
        if order_key in st.session_state:
            del st.session_state[order_key]

        st.success("Saved!")
        st.rerun()


if __name__ == "__main__":
    main()
