import streamlit as st
import csv
from datetime import datetime
import os
import re
import json
import ast

st.set_page_config(
    page_title="Part 2 Survey",
    layout="wide",
)

DATA_PATH = "stage4_reorganized_top4_thr0_65_with_id.csv"
LOCAL_RESULTS_PATH = os.path.join("preview_results_part2.csv")
VALID_CONDITIONS = ["C1", "C2", "C3", "C4", "C5"]


def split_numbered_list(text):
    pattern = r"(\d+\.)\s+"
    marked = re.sub(pattern, r"|||\1 ", text)
    parts = [l.strip() for l in marked.split("|||") if l.strip()]
    numbered = [p for p in parts if re.match(r"^\d+\. ", p)]
    if len(numbered) < 2:
        return text
    intro = [
        p
        for p in parts
        if not re.match(r"^\d+\. ", p) and parts.index(p) < parts.index(numbered[0])
    ]
    result = "\n".join(numbered)
    if intro:
        result = " ".join(intro) + "\n\n" + result
    return result


def render_candidate_text(text: str):
    if not text:
        st.write("")
        return

    def normalize_markdown_headings(raw: str) -> str:
        raw = re.sub(r"(?<!\n)\s+(#{1,6})\s+", r"\n\1 ", raw)
        raw = split_numbered_list(raw)
        def _shift_heading(match):
            hashes = match.group(1)
            level = min(len(hashes) + 3, 6)
            return "#" * level + " "
        return re.sub(r"(?m)^(#{1,6})\s+", _shift_heading, raw)

    pattern = re.compile(r"\[(?i:sponsor(?:ed)?)\s+(.*?)\]", flags=re.DOTALL)
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


def first_nonempty(row, names):
    for name in names:
        value = row.get(name, "")
        if value is not None and str(value).strip():
            return value
    return ""


def extract_sponsored_candidates(*texts):
    candidates = []
    pattern = re.compile(r"\[(?i:sponsor(?:ed)?)\s+(.*?)\]", flags=re.DOTALL)
    for text in texts:
        if not text:
            continue
        for match in pattern.finditer(str(text)):
            item = re.sub(r"\s+", " ", match.group(1)).strip()
            if item and item not in candidates:
                candidates.append(item)
    return candidates


@st.cache_data
def load_data(path):
    samples = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            original_response = first_nonempty(row, ["original_response", "Original_response"])
            candidate_4 = first_nonempty(row, ["candidate_4", "candidate4", "Candidate_4", "Candidate4"])
            candidate_4_prime = first_nonempty(row, ["candidate4'", "candidate_4_prime", "candidate4_prime", "Candidate4'"])
            entities_raw = first_nonempty(
                row,
                [
                    "entities_json",
                    "entity_json",
                    "entitie_json",
                    "entity",
                    "entities",
                    "ad_entities",
                    "ads",
                ],
            )
            if not entities_raw:
                sponsored_candidates = extract_sponsored_candidates(candidate_4_prime, candidate_4)
                if sponsored_candidates:
                    entities_raw = json.dumps(sponsored_candidates, ensure_ascii=False)

            if original_response and (candidate_4 or candidate_4_prime):
                samples.append({
                    "id": row.get("id") or row.get("conversation_id", ""),
                    "turn": row.get("turn", ""),
                    "context": row.get("context", ""),
                    "question": row.get("question", ""),
                    "original_response": original_response,
                    "candidate_4": candidate_4,
                    "candidate4'": candidate_4_prime,
                    "entities_json": entities_raw,
                })
    return samples


# ================== Condition helpers ==================
def get_condition():
    query_params = st.query_params
    cond = str(query_params.get("cond", "")).upper().strip()
    if cond not in VALID_CONDITIONS:
        return None
    return cond


CONDITION_CONFIG = {
    "C1": {"ad_present": 0, "disclosure_type": "none", "show_global_notice": False, "show_local_label": False},
    "C2": {"ad_present": 1, "disclosure_type": "none", "show_global_notice": False, "show_local_label": False},
    "C3": {"ad_present": 1, "disclosure_type": "local", "show_global_notice": False, "show_local_label": True},
    "C4": {"ad_present": 1, "disclosure_type": "global", "show_global_notice": True, "show_local_label": False},
    "C5": {"ad_present": 0, "disclosure_type": "global", "show_global_notice": True, "show_local_label": False},
}


CONDITION_DESC = {
    "C1": "No ad, no disclosure",
    "C2": "Ad present, no disclosure",
    "C3": "Ad present, local Sponsored label",
    "C4": "Ad present, global notice at top",
    "C5": "No ad, global notice at top",
}


def go_to_condition(cond):
    st.query_params["cond"] = cond


def show_home_page():
    st.title("Part 2 Survey Conditions")
    st.write("Choose a condition to open its survey page.")
    st.markdown("### Conditions")

    for cond in VALID_CONDITIONS:
        col1, col2 = st.columns([1, 4])
        with col1:
            st.button(cond, key=f"home_{cond}", on_click=go_to_condition, args=(cond,), use_container_width=True)
        with col2:
            st.markdown(f"**{cond}**: {CONDITION_DESC[cond]}")

    # Direct links removed as requested


def get_sample_for_condition(sample, condition):
    if condition in ["C1", "C5"]:
        return sample["original_response"], "original_response"
    if condition == "C3":
        return sample.get("candidate4'", ""), "candidate4'"
    if condition in ["C2", "C4"]:
        return sample["candidate_4"], "candidate_4"


# ================== Task helpers ==================
def build_task_pool_for_condition(samples, condition):
    task_pool = []
    for sample in samples:
        response_text, response_source = get_sample_for_condition(sample, condition)
        if response_text and str(response_text).strip():
            task_pool.append({
                "sample_id": str(sample.get("id", "")),
                "sample": sample,
                "response_text": response_text,
                "response_source": response_source,
            })
    return task_pool


def load_completed_sample_ids(results_path, condition):
    if not os.path.exists(results_path):
        return set()

    completed = set()
    with open(results_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("condition", "") != condition:
                continue
            sample_id = row.get("sample_id", "")
            if sample_id:
                completed.add(str(sample_id))
    return completed


def get_next_unfinished_task(task_pool, completed_ids):
    for task in task_pool:
        if task["sample_id"] not in completed_ids:
            return task
    return None


# ================== Main Streamlit App ==================
def scale_options():
    return [str(i) for i in range(1, 6)]


def parse_entities(entities_raw: str):
    def clean_item(item):
        if item is None:
            return ""
        if isinstance(item, dict):
            for key in ["name", "entity", "title", "brand", "product", "text", "value"]:
                value = item.get(key)
                if value is not None and str(value).strip():
                    return re.sub(r"\s+", " ", str(value)).strip()
            return re.sub(r"\s+", " ", json.dumps(item, ensure_ascii=False)).strip()
        return re.sub(r"\s+", " ", str(item)).strip()

    def normalize(parsed):
        if isinstance(parsed, str):
            stripped = parsed.strip()
            if not stripped:
                return []
            for parser in (json.loads, ast.literal_eval):
                try:
                    return normalize(parser(stripped))
                except Exception:
                    pass
            if ";" in stripped:
                return [clean_item(x) for x in stripped.split(";") if clean_item(x)]
            if "," in stripped and not stripped.startswith("http"):
                return [clean_item(x) for x in stripped.split(",") if clean_item(x)]
            return [clean_item(stripped)]
        if isinstance(parsed, list):
            return [clean_item(x) for x in parsed if clean_item(x)]
        if isinstance(parsed, dict):
            for key in ["entities", "entity", "ads", "ad_entities", "items", "matches"]:
                if key in parsed:
                    return normalize(parsed[key])
            return [clean_item(parsed)]
        return []

    seen = set()
    result = []
    for item in normalize(entities_raw):
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


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


def render_question_title(label: str):
    st.markdown(
        f"<p style='font-size:18px; font-weight:600; margin: 0.5rem 0 0.2rem 0;'>{label}</p>",
        unsafe_allow_html=True,
    )


def set_scale_value(session_key: str, value: str):
    st.session_state[session_key] = value


def safe_key_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "sample"))[:80]


def inject_scale_css_once():
    st.html(
        """
        <style>
        .scale-endpoint {
            font-size: 18px;
            color: #4F4F4F;
            line-height: 1.25;
            padding-top: 1.15rem;
        }

        .scale-right {
            text-align: right;
        }

        div[class*="st-key-scale_btn_"] button {
            border-radius: 999px !important;
            padding: 0 !important;
            min-width: unset !important;
            min-height: unset !important;
            box-shadow: none !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }

        div[class*="st-key-scale_btn_"] {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            height: 76px !important;
        }

        div[class*="st-key-scale_btn_"] button p {
            font-size: 0 !important;
            line-height: 0 !important;
            margin: 0 !important;
            color: transparent !important;
        }

        div[class*="st-key-scale_btn_"] button:hover,
        div[class*="st-key-scale_btn_"] button:focus,
        div[class*="st-key-scale_btn_"] button:active {
            box-shadow: none !important;
            outline: none !important;
        }
        </style>
        """
    )


def inject_layout_css():
    st.html(
        """
        <style>
        .block-container {
            max-width: 1100px;
            padding-top: 3rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }

        div[role="radiogroup"] label p {
            font-size: 18px !important;
        }
        </style>
        """
    )


def render_scale_question(q_key: str, label: str, left_text: str, right_text: str, condition: str, sample_id: str):
    inject_scale_css_once()
    render_question_title(label)

    sample_key = safe_key_part(sample_id)
    session_key = f"scale_value_{condition}_{q_key}_{sample_key}"

    if session_key not in st.session_state:
        st.session_state[session_key] = None

    selected_value = st.session_state.get(session_key)

    sizes = [50, 40, 30, 40, 50]

    colors = ["#35A978", "#35A978", "#9EA3AA", "#87589A", "#87589A"]

    dynamic_css = ["<style>"]

    for idx, (size, color) in enumerate(zip(sizes, colors), start=1):
        key = f"scale_btn_{condition}_{q_key}_{sample_key}_{idx}"
        is_selected = selected_value == str(idx)

        background = color if is_selected else "#FFFFFF"
        border_width = 0 if is_selected else 4

        dynamic_css.append(
            f"""
            div[class*="st-key-{key}"] button {{
                width: {size}px !important;
                height: {size}px !important;
                border: {border_width}px solid {color} !important;
                background-color: {background} !important;
            }}

            div[class*="st-key-{key}"] button:hover,
            div[class*="st-key-{key}"] button:focus,
            div[class*="st-key-{key}"] button:active {{
                width: {size}px !important;
                height: {size}px !important;
                border: {border_width}px solid {color} !important;
                background-color: {background} !important;
            }}
            """
        )

    dynamic_css.append("</style>")
    st.html("\n".join(dynamic_css))

    cols = st.columns([2.4, 0.9, 0.75, 0.6, 0.75, 0.9, 2.4])

    with cols[0]:
        st.markdown(
            f"<div class='scale-endpoint'>{left_text}</div>",
            unsafe_allow_html=True,
        )

    for idx in range(1, 6):
        with cols[idx]:
            st.button(
                "\u200b",
                key=f"scale_btn_{condition}_{q_key}_{sample_key}_{idx}",
                on_click=set_scale_value,
                args=(session_key, str(idx)),
            )

    with cols[6]:
        st.markdown(
            f"<div class='scale-endpoint scale-right'>{right_text}</div>",
            unsafe_allow_html=True,
        )

    return st.session_state.get(session_key)


def render_radio_question(q_key: str, label: str, options: list, condition: str, sample_id: str, horizontal: bool = True):
    render_question_title(label)
    options = [str(x) for x in options if str(x).strip()]
    if not options:
        st.info("No ad options were found for this response.")
        return ""
    return st.radio(
        label,
        options,
        index=None,
        key=f"{condition}_{q_key}_{sample_id}",
        label_visibility="collapsed",
        horizontal=horizontal,
    )


inject_layout_css()

data = load_data(DATA_PATH)
if not data:
    st.error(f"No data found. Please check: {DATA_PATH}")
    st.stop()

condition = get_condition()
if condition is None:
    show_home_page()
    st.stop()

config = CONDITION_CONFIG[condition]

task_pool = build_task_pool_for_condition(data, condition)
completed_ids = load_completed_sample_ids(LOCAL_RESULTS_PATH, condition)
current_task = get_next_unfinished_task(task_pool, completed_ids)

if not task_pool:
    st.error("No valid samples were found for this condition.")
    st.stop()

if current_task is None:
    st.success("All samples for this condition have been completed.")
    st.stop()

sample = current_task["sample"]
response_text = current_task["response_text"]
response_source = current_task["response_source"]


col_left, col_right = st.columns([3, 1])
with col_left:
    st.header(condition)
with col_right:
    def back_to_home():
        st.query_params["cond"] = ""
    if st.button("Back to home", key="back_home"):
        back_to_home()
        st.rerun()

st.markdown(
    f"<div style='color:#666; font-size:0.95rem;'>Completed tasks: {len(completed_ids)} / {len(task_pool)}</div>",
    unsafe_allow_html=True,
)

user_id = st.text_input("User ID", placeholder="e.g. user_001")

render_previous_context(sample.get("context", ""), sample.get("turn", 1))

st.markdown(f"### Current Question\n{sample['question']}")
st.subheader("Current Response")

if config["show_global_notice"]:
    st.markdown(
        """
        <div style="
            background: #F7E9B6;
            border: 1px solid #E2C76E;
            color: #4B3B0A;
            padding: 0.75rem 1rem;
            border-radius: 8px;
            font-weight: 600;
            margin-bottom: 0.75rem;
        ">
            Notice: This response may contain sponsored content.
        </div>
        """,
        unsafe_allow_html=True,
    )

render_candidate_text(response_text)

choices = {}


scale_questions_before_ad = [
    ("Q1", "How much would you trust the information in this response?", "Not at all trustworthy", "Very trustworthy"),
    ("Q2", "How naturally does this response read?", "Very unnatural", "Very natural"),
]

for q_key, label, left_text, right_text in scale_questions_before_ad:
    choices[q_key] = render_scale_question(
        q_key,
        label,
        left_text,
        right_text,
        condition,
        sample["id"],
    )

ad_question = "Do you think it contains ad?"
choices["Q4"] = render_radio_question(
    "q4",
    ad_question,
    ["Yes", "No"],
    condition,
    sample["id"],
    horizontal=True,
)

entities_list = parse_entities(sample.get("entities_json", ""))
if choices.get("Q4") == "Yes":
    ad_entity_question = "Which ad do you think it contains?"
    choices["Q5"] = render_radio_question(
        "q5",
        ad_entity_question,
        entities_list,
        condition,
        sample["id"],
        horizontal=False,
    )
else:
    choices["Q5"] = ""

scale_questions_after_ad = [
    ("Q3", "To what extent does this response feel like it's trying to influence your decisions or behavior?", "Not at all", "Very much"),
    ("Q6", "How helpful is this response in answering the question?", "Not at all helpful", "Extremely helpful"),
    ("Q7", "Overall, how would you rate the quality of this response?", "Very poor", "Excellent"),
]

for q_key, label, left_text, right_text in scale_questions_after_ad:
    choices[q_key] = render_scale_question(
        q_key,
        label,
        left_text,
        right_text,
        condition,
        sample["id"],
    )


def save_result(sample, user_id, condition, response_source, choices):
    payload = {
        "sample_id": sample["id"],
        "user_id": user_id,
        "condition": condition,
        "question": sample["question"],
        "response_source": response_source,
        "ad_present": CONDITION_CONFIG[condition]["ad_present"],
        "disclosure_type": CONDITION_CONFIG[condition]["disclosure_type"],
        "Q1": choices.get("Q1", ""),
        "Q2": choices.get("Q2", ""),
        "Q3": choices.get("Q3", ""),
        "Q4": choices.get("Q4", ""),
        "Q5": choices.get("Q5", ""),
        "Q6": choices.get("Q6", ""),
        "Q7": choices.get("Q7", ""),
        "timestamp": datetime.utcnow().isoformat(),
    }

    file_exists = os.path.exists(LOCAL_RESULTS_PATH)
    with open(LOCAL_RESULTS_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "sample_id", "user_id", "condition", "question", "response_source",
                "ad_present", "disclosure_type", "Q1", "Q2", "Q3", "Q4", "Q5",
                "Q6", "Q7", "timestamp"
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(payload)


if st.button("Submit"):
    required_keys = ["Q1", "Q2", "Q3", "Q4", "Q6", "Q7"]
    if choices.get("Q4") == "Yes":
        required_keys.append("Q5")

    if not user_id.strip():
        st.warning("Please enter your User ID before submitting.")
        st.stop()

    missing_required = [k for k in required_keys if not choices.get(k)]
    if missing_required:
        st.warning("Please answer all required questions before submitting.")
        st.stop()

    save_result(sample, user_id.strip(), condition, response_source, choices)
    st.success("Saved!")
    st.rerun()
