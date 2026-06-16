import streamlit as st
import streamlit.components.v1 as components
import random
import secrets
import os
import re
import html
import pandas as pd

st.set_page_config(
    page_title="Part 1 Position Survey",
    layout="wide",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.getenv(
    "DATA_PATH",
    os.path.join(BASE_DIR, "selected_samples_4_candidates.csv")
)

SUPABASE_TABLE = "part1_results"
SURVEY_PREFIX = "sponsored"

# All groups use the full dataset.
# The group choice only determines which candidate-prime pair is compared.
HOME_BATCHES = {
    "1": {
        "batch_id": "sponsored_home_1_candidate1prime_vs_candidate2prime",
        "field_a": "candidate_1_prime",
        "field_b": "candidate_2_prime",
    },
    "2": {
        "batch_id": "sponsored_home_2_candidate2prime_vs_candidate3prime",
        "field_a": "candidate_2_prime",
        "field_b": "candidate_3_prime",
    },
    "3": {
        "batch_id": "sponsored_home_3_candidate2prime_vs_candidate4prime",
        "field_a": "candidate_2_prime",
        "field_b": "candidate_4_prime",
    },
    "4": {
        "batch_id": "sponsored_home_4_candidate1prime_vs_candidate4prime",
        "field_a": "candidate_1_prime",
        "field_b": "candidate_4_prime",
    },
    "5": {
        "batch_id": "sponsored_home_5_candidate1prime_vs_candidate3prime",
        "field_a": "candidate_1_prime",
        "field_b": "candidate_3_prime",
    },
    "6": {
        "batch_id": "sponsored_home_6_candidate3prime_vs_candidate4prime",
        "field_a": "candidate_3_prime",
        "field_b": "candidate_4_prime",
    },
}

CANDIDATE_FIELD_SPECS = {
    "candidate_1_prime": [
        "candidate1'",
        "candidate_1'",
        "candidate1_prime",
        "candidate_1_prime",
        "Candidate1'",
        "Candidate_1_prime",
    ],
    "candidate_2_prime": [
        "candidate2'",
        "candidate_2'",
        "candidate2_prime",
        "candidate_2_prime",
        "Candidate2'",
        "Candidate_2_prime",
    ],
    "candidate_3_prime": [
        "candidate3'",
        "candidate_3'",
        "candidate3_prime",
        "candidate_3_prime",
        "Candidate3'",
        "Candidate_3_prime",
    ],
    "candidate_4_prime": [
        "candidate4'",
        "candidate_4'",
        "candidate4_prime",
        "candidate_4_prime",
        "Candidate4'",
        "Candidate_4_prime",
    ],
}

ATTENTION_AD_FIELD_SPECS = {
    "candidate_1_prime": [
        "candidate1_ad_llm",
        "candidate_1_ad_llm",
        "candidate1_prime_ad_llm",
        "candidate_1_prime_ad_llm",
        "Candidate1_ad_llm",
        "Candidate_1_ad_llm",
        "Candidate1_prime_ad_llm",
        "Candidate_1_prime_ad_llm",
    ],
    "candidate_2_prime": [
        "candidate2_ad_llm",
        "candidate_2_ad_llm",
        "candidate2_prime_ad_llm",
        "candidate_2_prime_ad_llm",
        "Candidate2_ad_llm",
        "Candidate_2_ad_llm",
        "Candidate2_prime_ad_llm",
        "Candidate_2_prime_ad_llm",
    ],
    "candidate_3_prime": [
        "candidate3_ad_llm",
        "candidate_3_ad_llm",
        "candidate3_prime_ad_llm",
        "candidate_3_prime_ad_llm",
        "Candidate3_ad_llm",
        "Candidate_3_ad_llm",
        "Candidate3_prime_ad_llm",
        "Candidate_3_prime_ad_llm",
    ],
    "candidate_4_prime": [
        "candidate4_ad_llm",
        "candidate_4_ad_llm",
        "candidate4_prime_ad_llm",
        "candidate_4_prime_ad_llm",
        "Candidate4_ad_llm",
        "Candidate_4_ad_llm",
        "Candidate4_prime_ad_llm",
        "Candidate_4_prime_ad_llm",
    ],
}

Q_LABELS = {
    "Q1": "Naturalness of flow — Which version reads more smoothly and feels less disruptive?",
    "Q2": "Ad visibility — In which version is the advertisement more visible?",
    "Q3": "Content helpfulness — Which version better preserves the usefulness of the non-ad content in answering the user's question?",
    "Q4": "Click likelihood — If you had to click on one advertisement, which version would make you more likely to click?",
    "Q5": "Appropriateness — Which version feels more trustworthy and less manipulative?",
    "Q6": "Overall preference — All things considered, which version is preferred?",
    "Q7": "Placement — Which version presents the advertisement earlier in the response?",
}

FIXED_Q_KEYS = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
PLACEMENT_Q_KEY = "Q7"
Q_KEYS = FIXED_Q_KEYS + [PLACEMENT_Q_KEY]
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


def format_pair_text(field_a: str, field_b: str) -> str:
    left = field_a.replace("_prime", "").replace("_", "")
    right = field_b.replace("_prime", "").replace("_", "")
    return f"{left} vs {right}"


def scroll_to_top_if_needed():
    if st.session_state.get("scroll_to_top", False):
        st.session_state.scroll_to_top = False
        components.html(
            """
            <script>
            window.parent.scrollTo({top: 0, behavior: 'smooth'});
            </script>
            """,
            height=0,
        )


def first_nonempty(row, names):
    for name in names:
        value = row.get(name, "")
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def get_secret_value(*keys):
    for key in keys:
        try:
            value = st.secrets[key]
            if value:
                return str(value)
        except Exception:
            pass
    return ""


@st.cache_resource
def get_supabase_client():
    try:
        from supabase import create_client
    except ImportError:
        st.error("The `supabase` package is not installed. Run: pip install supabase")
        st.stop()

    url = get_secret_value("SUPABASE_URL", "supabase_url")
    key = get_secret_value("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "supabase_key")

    try:
        if not url:
            url = str(st.secrets["supabase"]["url"])
        if not key:
            key = str(st.secrets["supabase"]["key"])
    except Exception:
        pass

    if not url or not key:
        st.error(
            "Missing Supabase secrets. Add SUPABASE_URL and SUPABASE_KEY, "
            "or [supabase].url and [supabase].key, to Streamlit secrets."
        )
        st.stop()

    return create_client(url, key)


def make_assignment(user_id, home_choice):
    batch = HOME_BATCHES[str(home_choice)]

    return {
        "user_id": str(user_id).strip(),
        "part": "part1",
        "condition": "",
        "home_choice": str(home_choice),
        "batch_id": batch["batch_id"],
        "field_a": batch["field_a"],
        "field_b": batch["field_b"],
    }


@st.cache_data
def load_data(path):
    samples = []

    def clean_value(value):
        if pd.isna(value):
            return ""
        return str(value)

    def normalize_row(row):
        return {str(k).strip(): clean_value(v) for k, v in row.items()}

    def to_sample(row, row_idx):
        sample_id = row.get("id") or row.get("conversation_id") or f"row_{row_idx}"
        sample = {
            "id": str(sample_id),
            "question": row.get("question", ""),
            "context": row.get("context", ""),
            "turn": row.get("turn", ""),
            "matched_ad": row.get("matched_ad", ""),
            "introduction": row.get("introduction", ""),
        }

        for canonical_field, possible_names in CANDIDATE_FIELD_SPECS.items():
            sample[canonical_field] = first_nonempty(row, possible_names)
            sample[f"{canonical_field}_attention_ad"] = first_nonempty(
                row,
                ATTENTION_AD_FIELD_SPECS.get(canonical_field, []),
            )

        return sample

    if not os.path.exists(path):
        return samples, "none"

    try:
        if path.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(path)
        else:
            df = pd.read_csv(path)
    except Exception as e:
        st.error(f"Failed to read data file: {path}. Error: {e}")
        st.stop()

    for row_idx, row in enumerate(df.to_dict(orient="records")):
        samples.append(to_sample(normalize_row(row), row_idx))

    return samples, "local"


@st.cache_data
def build_task_pool(samples, field_a, field_b):
    task_pool = []

    for sample in samples:
        text_a = str(sample.get(field_a, "")).strip()
        text_b = str(sample.get(field_b, "")).strip()

        ad_a = (
            str(sample.get(f"{field_a}_attention_ad", "")).strip()
            or extract_sponsored_text(text_a)
            or str(sample.get("matched_ad", "")).strip()
        )
        ad_b = (
            str(sample.get(f"{field_b}_attention_ad", "")).strip()
            or extract_sponsored_text(text_b)
            or str(sample.get("matched_ad", "")).strip()
        )

        if not text_a or not text_b:
            continue

        task_id = f"{sample['id']}__{field_a}_vs_{field_b}"

        task_pool.append(
            {
                "task_id": task_id,
                "sample_id": sample["id"],
                "question": sample.get("question", ""),
                "context": sample.get("context", ""),
                "turn": sample.get("turn", ""),
                "matched_ad": sample.get("matched_ad", ""),
                "introduction": sample.get("introduction", ""),
                "field_a": field_a,
                "field_b": field_b,
                "text_a": text_a,
                "text_b": text_b,
                "ad_a": ad_a,
                "ad_b": ad_b,
            }
        )

    return task_pool


def normalize_numbered_items(raw: str) -> str:
    raw = str(raw or "")

    raw = re.sub(r"(?<!\n)\s+(#{1,6})\s+", r"\n\1 ", raw)
    raw = re.sub(r"(?<!^)(?<!\n)\s+(\d+\.\s+)", r"\n\1", raw)

    raw = re.sub(
        r"\s*(\[(?:sponsor|sponsored)\s+.*?\])\s*",
        r"\n\1\n",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )

    raw = re.sub(
        r"(?<!\n)\s+(Sponsored:\s*)",
        r"\n\1",
        raw,
        flags=re.IGNORECASE,
    )

    raw = re.sub(r"\n{2,}", "\n", raw)

    return raw.strip()


def escape_markdown_math_dollars(raw: str) -> str:
    return str(raw or "").replace("$", r"\$")


def render_candidate_text(text: str):
    if not text:
        st.write("")
        return

    def normalize_markdown_headings(raw: str) -> str:
        raw = normalize_numbered_items(raw)

        def _shift_heading(match):
            hashes = match.group(1)
            level = min(len(hashes) + 3, 6)
            return "#" * level + " "

        return re.sub(r"(?m)^(#{1,6})\s+", _shift_heading, raw)

    pattern = re.compile(r"\[(?i:sponsor(?:ed)?)\s+(.*?)\]", flags=re.DOTALL)
    cursor = 0

    for match in pattern.finditer(str(text)):
        normal_part = str(text)[cursor:match.start()].strip()
        if normal_part:
            st.markdown(escape_markdown_math_dollars(normalize_markdown_headings(normal_part)))

        sponsored_content = re.sub(r"\s+", " ", match.group(1)).strip()
        if sponsored_content:
            st.markdown(
                f"<p style='color:#8A8A8A;'><strong>Sponsored:</strong> "
                f"{html.escape(sponsored_content)}</p>",
                unsafe_allow_html=True,
            )

        cursor = match.end()

    tail = str(text)[cursor:].strip()
    if tail:
        st.markdown(escape_markdown_math_dollars(normalize_markdown_headings(tail)))


def extract_sponsored_text(text: str):
    if not text:
        return ""

    pattern = re.compile(r"\[(?i:sponsor(?:ed)?)\s+(.*?)\]", flags=re.DOTALL)
    match = pattern.search(str(text))
    if not match:
        return ""

    return re.sub(r"\s+", " ", match.group(1)).strip()


def normalize_for_match(text: str):
    return re.sub(r"[^a-zA-Z0-9]+", " ", str(text or "").lower()).strip()


def safe_key_part(value: str):
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "task"))[:120]


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
            exchanges.append(
                {
                    "user": user_text,
                    "assistant": assistant_text,
                }
            )

    return exchanges


def render_previous_context(context_raw: str, turn, introduction: str = ""):
    try:
        turn_num = int(turn)
    except Exception:
        turn_num = 1

    if turn_num <= 1:
        return

    exchanges = parse_context(context_raw)
    if not exchanges:
        return

    intro = str(introduction or "").strip()
    if intro:
        intro = intro.rstrip(".?!") + "."
        st.markdown(f"{intro} The following is the previous conversation for your reference.")
    else:
        st.markdown("The following is the previous conversation for your reference.")

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


def is_skipped_value(value) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "t"}


def load_completed_task_ids(user_id, include_skipped: bool = False):
    supabase = get_supabase_client()

    try:
        response = (
            supabase.table(SUPABASE_TABLE)
            .select("task_id, skipped")
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as e:
        st.error(f"Failed to load completed tasks from Supabase: {e}")
        st.stop()

    completed = set()

    for row in response.data or []:
        if not include_skipped and is_skipped_value(row.get("skipped", "")):
            continue
        task_id = row.get("task_id", "")
        if task_id:
            completed.add(str(task_id))

    return completed


def get_next_unfinished_task(task_pool, completed_ids):
    for task in task_pool:
        if task["task_id"] not in completed_ids:
            return task
    return None


def get_task_by_id(task_pool, task_id):
    for task in task_pool:
        if task["task_id"] == task_id:
            return task
    return None


def get_task_position(task_pool, current_task):
    current_id = current_task["task_id"]
    for idx, task in enumerate(task_pool, start=1):
        if task["task_id"] == current_id:
            return idx
    return 1


def init_display_orders(task_pool, user_id, batch_id):
    task_ids = [task["task_id"] for task in task_pool]
    map_key = (
        f"display_order_map_{safe_key_part(user_id)}_"
        f"{safe_key_part(batch_id)}_{len(task_ids)}"
    )

    current_map = st.session_state.get(map_key)
    if isinstance(current_map, dict) and set(current_map.keys()) == set(task_ids):
        st.session_state["display_order_map_key"] = map_key
        return

    orders = ["AB", "BA"] * (len(task_ids) // 2)

    if len(task_ids) % 2:
        orders.append(secrets.choice(["AB", "BA"]))

    random.shuffle(orders)

    st.session_state[map_key] = dict(zip(task_ids, orders))
    st.session_state["display_order_map_key"] = map_key


def prepare_display_task(task):
    map_key = st.session_state.get("display_order_map_key")
    order_map = st.session_state.get(map_key, {}) if map_key else {}
    display_order = order_map.get(task["task_id"], secrets.choice(["AB", "BA"]))

    if display_order == "AB":
        return {
            **task,
            "left_field": task["field_a"],
            "left_text": task["text_a"],
            "left_attention_ad": task.get("ad_a", ""),
            "right_field": task["field_b"],
            "right_text": task["text_b"],
            "right_attention_ad": task.get("ad_b", ""),
            "display_order": display_order,
        }

    return {
        **task,
        "left_field": task["field_b"],
        "left_text": task["text_b"],
        "left_attention_ad": task.get("ad_b", ""),
        "right_field": task["field_a"],
        "right_text": task["text_a"],
        "right_attention_ad": task.get("ad_a", ""),
        "display_order": display_order,
    }


def choice_to_machine_value(choice):
    if choice == "Version A":
        return "left"
    if choice == "Version B":
        return "right"
    if choice == "Tie":
        return "tie"
    return ""


def get_ad_start_position(text: str, matched_ad: str = ""):
    text = str(text or "")
    match = re.search(r"\[(?i:sponsor(?:ed)?)\s+.*?\]", text, flags=re.DOTALL)

    if match:
        return match.start()

    normalized_text = normalize_for_match(text)
    normalized_ad = normalize_for_match(matched_ad)

    if normalized_text and normalized_ad:
        pos = normalized_text.find(normalized_ad)
        if pos >= 0:
            return pos

    return None


def get_ad_position_answer(display_task):
    left_pos = get_ad_start_position(
        display_task.get("left_text", ""),
        display_task.get("left_attention_ad", "") or display_task.get("matched_ad", ""),
    )
    right_pos = get_ad_start_position(
        display_task.get("right_text", ""),
        display_task.get("right_attention_ad", "") or display_task.get("matched_ad", ""),
    )

    if left_pos is None and right_pos is None:
        return "tie"
    if left_pos is None:
        return "right"
    if right_pos is None:
        return "left"
    if left_pos == right_pos:
        return "tie"
    return "left" if left_pos < right_pos else "right"


def get_question_display_order(task_id: str):
    key = f"question_display_order_{safe_key_part(task_id)}"
    all_keys = Q_KEYS

    current_order = st.session_state.get(key)

    if isinstance(current_order, list) and set(current_order) == set(all_keys):
        return current_order

    display_order = FIXED_Q_KEYS.copy()
    insert_position = secrets.randbelow(len(display_order) + 1)
    display_order.insert(insert_position, PLACEMENT_Q_KEY)

    st.session_state[key] = display_order

    return display_order


def get_attention_copy_target(task_id: str):
    key = f"attention_copy_target_{safe_key_part(task_id)}"

    if key not in st.session_state:
        st.session_state[key] = secrets.choice(["A", "B"])

    return st.session_state[key]


def get_attention_target_metadata(display_task, target_version: str):
    if target_version == "A":
        return {
            "attention_target_version": "A",
            "attention_target_field": display_task.get("left_field", ""),
            "attention_target_ad": display_task.get("left_attention_ad", ""),
        }

    return {
        "attention_target_version": "B",
        "attention_target_field": display_task.get("right_field", ""),
        "attention_target_ad": display_task.get("right_attention_ad", ""),
    }


def save_result(
    display_task,
    user_id,
    batch_id,
    choices,
    attention_target_version="",
    attention_target_field="",
    attention_target_ad="",
    attention_text_input="",
    feedback_text="",
    skipped: bool = False,
):
    payload = {
        "user_id": user_id,
        "batch_id": batch_id,
        "task_id": display_task["task_id"],
        "sample_id": display_task["sample_id"],
        "left_field": display_task["left_field"],
        "right_field": display_task["right_field"],
        "display_order": display_task.get("display_order", ""),
        "Q1_choice": "" if skipped else choice_to_machine_value(choices.get("Q1", "")),
        "Q2_choice": "" if skipped else choice_to_machine_value(choices.get("Q2", "")),
        "Q3_choice": "" if skipped else choice_to_machine_value(choices.get("Q3", "")),
        "Q4_choice": "" if skipped else choice_to_machine_value(choices.get("Q4", "")),
        "Q5_choice": "" if skipped else choice_to_machine_value(choices.get("Q5", "")),
        "Q6_choice": "" if skipped else choice_to_machine_value(choices.get("Q6", "")),
        "Q7_choice": "" if skipped else choice_to_machine_value(choices.get("Q7", "")),
        "Q7_correct_answer": "" if skipped else get_ad_position_answer(display_task),
        "Q7_is_correct": None
        if skipped
        else (
            choice_to_machine_value(choices.get("Q7", ""))
            == get_ad_position_answer(display_task)
        ),
        "attention_target_version": "" if skipped else attention_target_version,
        "attention_target_field": "" if skipped else attention_target_field,
        "attention_target_ad": "" if skipped else attention_target_ad,
        "attention_text_input": "" if skipped else attention_text_input,
        "feedback": str(feedback_text or "").strip(),
        "skipped": skipped,
    }

    supabase = get_supabase_client()

    try:
        (
            supabase.table(SUPABASE_TABLE)
            .upsert(payload, on_conflict="user_id,task_id")
            .execute()
        )
    except Exception as e:
        st.error(
            "Failed to save result to Supabase. "
            "Make sure part1_results has a unique constraint on (user_id, task_id), "
            "and make sure the feedback column exists. "
            f"Error: {e}"
        )
        st.stop()


def reset_choice_state(task_id):
    for q_key in Q_KEYS:
        key = f"{q_key}_{task_id}"
        if key in st.session_state:
            del st.session_state[key]

    feedback_key = f"feedback_{safe_key_part(task_id)}"
    if feedback_key in st.session_state:
        del st.session_state[feedback_key]


def init_session():
    if "page" not in st.session_state:
        st.session_state.page = "user_id"
    if "user_id" not in st.session_state:
        st.session_state.user_id = ""
    if "assignment" not in st.session_state:
        st.session_state.assignment = None
    if "home_choice" not in st.session_state:
        st.session_state.home_choice = ""
    if "task_history" not in st.session_state:
        st.session_state.task_history = []
    if "override_task_id" not in st.session_state:
        st.session_state.override_task_id = None


def show_user_id_page():
    st.title("Part 1 Position Survey")

    st.markdown("Please choose a dataset group.")

    home_choice = st.radio(
        "Dataset group",
        ["1", "2", "3", "4", "5", "6"],
        index=None,
        horizontal=True,
    )

    if home_choice:
        batch = HOME_BATCHES[str(home_choice)]
        pair_text = format_pair_text(batch["field_a"], batch["field_b"])

        st.markdown(
            f"<div class='meta-text'>Group {home_choice}: all rows, {pair_text}</div>",
            unsafe_allow_html=True,
        )

    required_prefix = SURVEY_PREFIX + "_"
    st.markdown(f"Please enter your User ID. It must start with `{required_prefix}`.")

    user_id = st.text_input("User ID")

    if st.button("Continue", use_container_width=True):
        raw_user_id = user_id.strip()

        if not home_choice:
            st.warning("Please choose a dataset group.")
            st.stop()

        if not raw_user_id:
            st.warning("Please enter your User ID.")
            st.stop()

        if not raw_user_id.startswith(required_prefix):
            st.warning(f"Please enter a valid User ID starting with {required_prefix}")
            st.stop()

        assignment = make_assignment(raw_user_id, str(home_choice))

        st.session_state.user_id = raw_user_id
        st.session_state.home_choice = str(home_choice)
        st.session_state.assignment = assignment
        st.session_state.task_history = []
        st.session_state.override_task_id = None
        st.session_state.page = "calibration"
        st.rerun()


def show_calibration_page():
    st.title("Response Comparison Guide")

    st.markdown(
        """
You will compare two versions of the same AI response. The two versions may differ in where an advertisement appears. For each question, choose **Version A**, **Version B**, or **Tie**.

**Naturalness of flow**  
Choose the version that reads more smoothly and feels less disruptive. A natural version should fit the surrounding response and not feel abruptly inserted.

**Ad visibility**  
Choose the version where the advertisement is more visible. **This does not mean the version is better or worse; it only asks which advertisement is easier to notice.**

**Content helpfulness**  
Choose the version that better preserves the usefulness of the non-ad content in answering the user's question. Focus on whether the main response remains useful, not on whether the advertisement itself is useful.

**Click likelihood**  
If you had to click on one advertisement, choose the version that would make you more likely to click.

**Appropriateness**  
Choose the version that feels more trustworthy and less manipulative. Consider whether the advertisement feels suitable, transparent, and not overly pushy.

**Overall preference**  
Choose the version you prefer all things considered.

**Placement**  
Choose the version that presents the advertisement earlier in the response. This question may appear in a random position.

**Your answers are checked for consistency and quality. The final reward depends on careful reading and agreement with the main response pattern. Too many inconsistent or careless answers will reduce the reward according to the study rules.**

If the two versions are about equally good on a dimension, choose **Tie**.
"""
    )

    if st.button("Start Survey", use_container_width=True):
        st.session_state.page = "survey"
        st.rerun()


def go_back_to_previous_task():
    history = st.session_state.get("task_history", [])

    if not history:
        return

    previous_task_id = history.pop()
    st.session_state.task_history = history
    st.session_state.override_task_id = previous_task_id
    reset_choice_state(previous_task_id)
    st.rerun()


def main():
    inject_layout_css()
    scroll_to_top_if_needed()
    init_session()

    if st.session_state.page == "user_id":
        show_user_id_page()
        st.stop()

    if st.session_state.page == "calibration":
        show_calibration_page()
        st.stop()

    assignment = st.session_state.get("assignment")

    if assignment is None:
        st.session_state.page = "user_id"
        st.rerun()

    data, data_source = load_data(DATA_PATH)

    if not data:
        st.error(f"No data found. Please check: {DATA_PATH}")
        st.stop()

    if data_source == "local":
        data_source_msg = f"Data source: Local file ({DATA_PATH})"
    else:
        data_source_msg = "Data source: Unknown"

    if st.session_state.get("_last_data_source_msg") != data_source_msg:
        print(f"[Ad-Arena] {data_source_msg}")
        st.session_state["_last_data_source_msg"] = data_source_msg

    user_id = st.session_state.user_id
    batch_id = assignment.get("batch_id", "")
    home_choice = assignment.get("home_choice", "")

    field_a = assignment.get("field_a", "candidate_1_prime")
    field_b = assignment.get("field_b", "candidate_2_prime")
    pair_text = format_pair_text(field_a, field_b)

    task_pool = build_task_pool(data, field_a, field_b)
    init_display_orders(task_pool, user_id, batch_id)

    handled = load_completed_task_ids(user_id, include_skipped=True)

    override_task_id = st.session_state.get("override_task_id")

    if override_task_id:
        task = get_task_by_id(task_pool, override_task_id)

        if task is None:
            st.session_state.override_task_id = None
            task = get_next_unfinished_task(task_pool, handled)
    else:
        task = get_next_unfinished_task(task_pool, handled)

    st.title("Part 1 Position Survey")

    if not task_pool:
        st.error(
            f"No valid candidate pairs were found for {field_a} vs {field_b}. "
            "Please check whether the selected candidate-prime columns are present and non-empty."
        )
        st.stop()

    if task is not None:
        current_position = get_task_position(task_pool, task)
        st.markdown(
            f"<div class='meta-text'>Group {home_choice}: all rows, {pair_text} "
            f"({current_position}/{len(task_pool)})</div>",
            unsafe_allow_html=True,
        )

    if task is None:
        st.success("All candidate-pair tasks have been completed.")
        st.stop()

    if st.button(
        "Back to previous task",
        use_container_width=True,
        disabled=not bool(st.session_state.get("task_history", [])),
    ):
        go_back_to_previous_task()

    display_task = prepare_display_task(task)

    render_previous_context(
        display_task.get("context", ""),
        display_task.get("turn", 1),
        display_task.get("introduction", ""),
    )

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

    attention_target_version = get_attention_copy_target(display_task["task_id"])
    attention_metadata = get_attention_target_metadata(display_task, attention_target_version)
    attention_text_input = attention_metadata["attention_target_ad"]

    choices = {}
    question_display_order = get_question_display_order(display_task["task_id"])

    for q_key in question_display_order:
        label = Q_LABELS[q_key]
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

    st.markdown(
        "<p style='font-size:18px; font-weight:600; margin: 0.8rem 0 0.2rem 0;'>"
        "</p>",
        unsafe_allow_html=True,
    )

    feedback_text = st.text_area(
        "Optional feedback",
        key=f"feedback_{safe_key_part(display_task['task_id'])}",
        height=100,
        label_visibility="collapsed",
    )

    col_submit, col_spacer, col_skip = st.columns([1, 0.5, 1])

    with col_submit:
        submit_clicked = st.button("Submit", use_container_width=True)

    with col_skip:
        skip_clicked = st.button("Skip", use_container_width=True)

    if submit_clicked:
        if not all(choices.values()):
            st.warning("Please answer all questions before submitting.")
            st.stop()

        save_result(
            display_task,
            user_id.strip(),
            batch_id,
            choices,
            attention_target_version=attention_metadata["attention_target_version"],
            attention_target_field=attention_metadata["attention_target_field"],
            attention_target_ad=attention_metadata["attention_target_ad"],
            attention_text_input=attention_text_input,
            feedback_text=feedback_text,
        )

        if not st.session_state.get("override_task_id"):
            history = st.session_state.get("task_history", [])

            if not history or history[-1] != display_task["task_id"]:
                history.append(display_task["task_id"])

            st.session_state.task_history = history

        st.session_state.override_task_id = None
        reset_choice_state(display_task["task_id"])

        st.success("Saved!")
        st.session_state.scroll_to_top = True
        st.rerun()

    if skip_clicked:
        save_result(
            display_task,
            user_id.strip(),
            batch_id,
            choices,
            attention_target_version=attention_metadata["attention_target_version"],
            attention_target_field=attention_metadata["attention_target_field"],
            attention_target_ad=attention_metadata["attention_target_ad"],
            attention_text_input=attention_text_input,
            feedback_text=feedback_text,
            skipped=True,
        )

        if not st.session_state.get("override_task_id"):
            history = st.session_state.get("task_history", [])

            if not history or history[-1] != display_task["task_id"]:
                history.append(display_task["task_id"])

            st.session_state.task_history = history

        st.session_state.override_task_id = None
        reset_choice_state(display_task["task_id"])

        st.info("Skipped.")
        st.session_state.scroll_to_top = True
        st.rerun()


if __name__ == "__main__":
    main()
