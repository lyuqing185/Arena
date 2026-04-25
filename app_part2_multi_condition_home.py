import streamlit as st
import random
import csv
from datetime import datetime
import os
import re

DATA_PATH = os.path.join("stage4_reorganized_top4_thr0_65_with_id.csv")
LOCAL_RESULTS_PATH = os.path.join("preview_results_part2.csv")
VALID_CONDITIONS = ["C1", "C2", "C3", "C4", "C5"]


def split_numbered_list(text):
    pattern = r"(\d+\.)\s+"
    text = re.sub(pattern, r"|||\1 ", text)
    lines = [l.strip() for l in text.split("|||") if l.strip()]
    if len(lines) > 1 and all(re.match(r"^\d+\. ", l) for l in lines):
        return "\n".join(lines)
    return text


def render_candidate_text(text: str):
    if not text:
        st.write("")
        return

    def normalize_markdown_headings(raw: str) -> str:
        raw = re.sub(r"(?<!\n)\s+(#{1,6})\s+", r"\n\1 ", raw)
        def split_numbered_list(text):
            pattern = r"(\d+\.)\s+"
            text = re.sub(pattern, r"|||\1 ", text)
            lines = [l.strip() for l in text.split("|||") if l.strip()]
            if len(lines) > 1 and all(re.match(r"^\d+\. ", l) for l in lines):
                return "\n".join(lines)
            return text
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


@st.cache_data
def load_data(path):
    samples = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            original_response = row.get("original_response", "")
            candidate_4 = row.get("candidate_4") or row.get("candidate4", "")
            candidate_4_prime = row.get("candidate4'", "")
            if original_response and (candidate_4 or candidate_4_prime):
                samples.append({
                    "id": row.get("id") or row.get("conversation_id", ""),
                    "question": row.get("question", ""),
                    "original_response": original_response,
                    "candidate_4": candidate_4,
                    "candidate4'": candidate_4_prime,
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


# ================== Main Streamlit App ==================
def scale_options():
    return [str(i) for i in range(1, 8)]


data = load_data(DATA_PATH)
if not data:
    st.error(f"No data found. Please check: {DATA_PATH}")
    st.stop()

condition = get_condition()
if condition is None:
    show_home_page()
    st.stop()

config = CONDITION_CONFIG[condition]

sample_key = f"current_sample_{condition}"
if sample_key not in st.session_state:
    st.session_state[sample_key] = random.choice(data)
sample = st.session_state[sample_key]

response_text, response_source = get_sample_for_condition(sample, condition)


col_left, col_right = st.columns([3, 1])
with col_left:
    st.header(condition)
with col_right:
    def back_to_home():
        st.query_params["cond"] = ""
    if st.button("Back to home", key="back_home"):
        back_to_home()
        st.rerun()

user_id = st.text_input("User ID", placeholder="e.g. user_001")

if config["show_global_notice"]:
    st.markdown("### Notice\nThe following content may contain advertising.")

st.markdown(f"### Question\n{sample['question']}")
st.subheader("Response")



render_candidate_text(response_text)

choices = {}
core_q_labels = [
    "How helpful is this response in answering the question?",
    "How much would you trust the information in this response?",
    "How naturally does this response read?",
    "To what extent does this response feel like it's trying to influence your decisions or behavior?",
    "Overall, how would you rate the quality of this response?",
]

for i, label in enumerate(core_q_labels, start=1):
    st.markdown(
        f"<p style='font-size:18px; font-weight:600; margin: 0.5rem 0 0.2rem 0;'>{label}</p>",
        unsafe_allow_html=True,
    )
    choices[f"Q{i}"] = st.radio(
        label,
        scale_options(),
        index=None,
        key=f"{condition}_q{i}_{sample['id']}",
        label_visibility="collapsed",
    )

# Ad-level questions: only for C2/C3/C4
if config["ad_present"] == 1:
    ad_question = "Did any part of this response feel like a sponsored recommendation or advertisement? (Yes / No / Unsure; if yes, highlight which part.)"
    st.markdown(
        f"<p style='font-size:18px; font-weight:600; margin: 0.5rem 0 0.2rem 0;'>{ad_question}</p>",
        unsafe_allow_html=True,
    )
    choices["Q6"] = st.radio(
        ad_question,
        ["Yes", "No", "Unsure"],
        index=None,
        key=f"{condition}_q6_{sample['id']}",
        label_visibility="collapsed",
    )
    choices["Q6_highlight"] = st.text_area(
        "If yes, please highlight which part.",
        key=f"{condition}_q6_highlight_{sample['id']}",
    )

    ad_q_labels = {
        "Q7": "How credible is the specific product or service recommendation in this response?",
        "Q8": "How likely would you be to look into this recommendation further?",
        "Q9": "Based on this response, how likely would you be to use this AI assistant again?",
        "Q10": "How honest does this AI assistant seem to be with you?",
    }
else:
    ad_q_labels = {
        "Q9": "Based on this response, how likely would you be to use this AI assistant again?",
        "Q10": "How honest does this AI assistant seem to be with you?",
    }

for q_key, label in ad_q_labels.items():
    st.markdown(
        f"<p style='font-size:18px; font-weight:600; margin: 0.5rem 0 0.2rem 0;'>{label}</p>",
        unsafe_allow_html=True,
    )
    choices[q_key] = st.radio(
        label,
        scale_options(),
        index=None,
        key=f"{condition}_{q_key}_{sample['id']}",
        label_visibility="collapsed",
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
        "Q6_highlight": choices.get("Q6_highlight", ""),
        "Q7": choices.get("Q7", ""),
        "Q8": choices.get("Q8", ""),
        "Q9": choices.get("Q9", ""),
        "Q10": choices.get("Q10", ""),
        "timestamp": datetime.utcnow().isoformat(),
    }

    file_exists = os.path.exists(LOCAL_RESULTS_PATH)
    with open(LOCAL_RESULTS_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "sample_id", "user_id", "condition", "question", "response_source",
                "ad_present", "disclosure_type", "Q1", "Q2", "Q3", "Q4", "Q5",
                "Q6", "Q6_highlight", "Q7", "Q8", "Q9", "Q10", "timestamp"
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(payload)


if st.button("Submit"):
    required_keys = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q9", "Q10"]
    if config["ad_present"] == 1:
        required_keys.extend(["Q6", "Q7", "Q8"])

    if not user_id.strip():
        st.warning("Please enter your User ID before submitting.")
        st.stop()

    missing_required = [k for k in required_keys if not choices.get(k)]
    if missing_required:
        st.warning("Please answer all required questions before submitting.")
        st.stop()

    save_result(sample, user_id.strip(), condition, response_source, choices)
    st.success("Saved!")
    st.session_state[sample_key] = random.choice(data)
    st.rerun()
