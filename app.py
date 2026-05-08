import streamlit as st
import requests
import json
import os
from datetime import date

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma3:4b"          # change to gemma3:1b if your machine is slow
PROGRESS_FILE = "progress.json"

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Unpack — Survive your first 30 days abroad",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .stProgress > div > div { background-color: #c8933a; }
    .stButton > button[kind="primary"] {
        background-color: #c8933a;
        border: none;
        color: white;
        font-weight: 600;
    }
    .stButton > button[kind="primary"]:hover { background-color: #a87730; }
    .mission-done { opacity: 0.5; }
</style>
""", unsafe_allow_html=True)


# ── Ollama helper ─────────────────────────────────────────────────────────────
def chat(messages: list[dict]) -> str:
    """Send messages to Gemma 4 via Ollama and return the reply."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "messages": messages, "stream": False},
            timeout=120
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except requests.exceptions.ConnectionError:
        return (
            "⚠️ Cannot reach Ollama. "
            "Open a terminal and run: **ollama serve** — then refresh this page."
        )
    except Exception as e:
        return f"⚠️ Error: {e}"


# ── Mission generation ────────────────────────────────────────────────────────
SYSTEM_GENERATE = """You are Unpack, an offline AI survival guide for international students.
Generate a personalised mission sequence for a student's first 30 days abroad.

Return ONLY raw JSON — no markdown, no code fences, no explanation. Exact format:
{
  "missions": [
    {
      "id": 1,
      "emoji": "📋",
      "title": "Get your Tax File Number",
      "category": "Admin",
      "priority": "urgent",
      "deadline": "Within 28 days of starting work",
      "why": "Without it your employer withholds 47% of your pay automatically.",
      "how": "1. Go to ato.gov.au/individuals/tax-file-number\\n2. Click Apply online\\n3. You will need your passport and visa details\\n4. Takes 15 minutes — TFN arrives by post in ~28 days"
    }
  ]
}

Generate exactly 12 missions. Cover in order of urgency:
- Admin/legal: TFN, health cover activation, visa conditions, bank account, superannuation
- Housing: lease, bond, tenant rights, utilities
- Academic: grading system, rubrics, talking to professors, academic integrity
- Life: transport card, cheap groceries, student discounts, local emergency numbers
- Wellbeing: finding support services, recognising isolation, campus health

Make every mission specific to the student's country, visa type, and university context.
Use plain, direct language — no jargon. Write like a knowledgeable friend."""


def generate_missions(profile: dict) -> list | None:
    user_msg = (
        f"Country: {profile['country']}\n"
        f"University: {profile['university']}\n"
        f"Visa: {profile['visa']}\n"
        f"Degree: {profile['degree']}\n"
        f"Year: {profile['year']}\n"
        f"Arrival date: {profile['arrival_date']}"
    )
    raw = chat([
        {"role": "system", "content": SYSTEM_GENERATE},
        {"role": "user", "content": user_msg}
    ])
    try:
        clean = raw.strip()
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        return json.loads(clean.strip())["missions"]
    except Exception:
        return None


# ── Progress persistence ──────────────────────────────────────────────────────
def save_progress(done: set):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(list(done), f)


def load_progress() -> set:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return set(json.load(f))
    return set()


# ── Session state init ────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "profile": None,
        "missions": None,
        "completed": load_progress(),
        "chats": {},        # mission_id → list of {role, content}
        "panic": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Screens ───────────────────────────────────────────────────────────────────
def screen_setup():
    st.title("📦 Unpack")
    st.markdown("#### Your offline AI survival guide — first 30 days abroad.")
    st.caption("Powered by Gemma 4 via Ollama · Runs without internet once set up")
    st.divider()
    st.markdown("### Tell me about yourself")
    st.caption("Takes under 2 minutes. Every recommendation is personalised to your situation.")

    with st.form("setup"):
        c1, c2 = st.columns(2)
        with c1:
            country = st.selectbox("Arrival country *", [
                "Australia", "United Kingdom", "United States",
                "Canada", "Germany", "New Zealand",
                "Netherlands", "France", "Other"
            ])
            university = st.text_input("University name *", placeholder="e.g. University of Sydney")
            visa = st.selectbox("Visa type *", [
                "Student visa — Australia subclass 500",
                "Tier 4 Student visa — UK",
                "F-1 Student visa — USA",
                "Study permit — Canada",
                "Student residence permit — Germany",
                "Other student visa"
            ])
        with c2:
            degree = st.text_input("Degree / field of study", placeholder="e.g. Bachelor of Commerce")
            year = st.selectbox("Year of study", ["1st year", "2nd year", "3rd year", "4th year +"])
            arrival = st.date_input("Arrival date", value=date.today())

        go = st.form_submit_button("Generate my survival guide →", use_container_width=True, type="primary")

    if go:
        if not university.strip():
            st.error("Please enter your university name.")
            return
        st.session_state.profile = {
            "country": country, "university": university.strip(),
            "visa": visa, "degree": degree, "year": year,
            "arrival_date": str(arrival)
        }
        with st.spinner("Gemma 4 is building your personalised guide... (~20 seconds)"):
            missions = generate_missions(st.session_state.profile)
        if missions:
            st.session_state.missions = missions
            st.rerun()
        else:
            st.error("Mission generation failed. Is Ollama running? Try: **ollama serve** in your terminal.")
            st.session_state.profile = None


def screen_panic():
    incomplete = [m for m in st.session_state.missions
                  if m["id"] not in st.session_state.completed]

    st.markdown("## 🆘 One thing at a time.")
    st.divider()

    if not incomplete:
        st.success("🎉 You've completed every mission. You're all set.")
        if st.button("← Back"):
            st.session_state.panic = False
            st.rerun()
        return

    m = incomplete[0]
    st.markdown(f"### {m['emoji']}  {m['title']}")
    st.warning(f"⏰  {m['deadline']}")
    st.markdown(f"**Why this one first:** {m['why']}")
    st.divider()
    st.markdown(m["how"])
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅  Done — what's next?", type="primary", use_container_width=True):
            st.session_state.completed.add(m["id"])
            save_progress(st.session_state.completed)
            st.rerun()
    with c2:
        if st.button("← Back to full list", use_container_width=True):
            st.session_state.panic = False
            st.rerun()


def screen_dashboard():
    profile   = st.session_state.profile
    missions  = st.session_state.missions
    completed = st.session_state.completed

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("## 📦 Unpack")
        st.markdown(f"**{profile['university']}**")
        st.markdown(f"{profile['degree']} · {profile['year']}")
        st.markdown(f"📍 {profile['country']}")
        st.divider()
        pct = len(completed) / len(missions) if missions else 0
        st.progress(pct)
        st.markdown(f"**{len(completed)} / {len(missions)} missions complete**")
        st.divider()
        if st.button("🆘  PANIC BUTTON", use_container_width=True, type="primary"):
            st.session_state.panic = True
            st.rerun()
        st.divider()
        if st.button("↩️  Reset profile", use_container_width=True):
            for k in ["profile", "missions", "chats", "panic"]:
                st.session_state[k] = None if k != "chats" else {}
            st.session_state.completed = set()
            if os.path.exists(PROGRESS_FILE):
                os.remove(PROGRESS_FILE)
            st.rerun()

    # ── Header ──
    st.title("Your 30-day survival guide")
    try:
        days = (date.today() - date.fromisoformat(profile["arrival_date"])).days
        st.markdown(f"📅  Day **{max(days + 1, 1)}** of your first 30 days")
    except Exception:
        pass
    st.divider()

    # ── Missions ──
    for m in missions:
        mid   = m["id"]
        done  = mid in completed
        label = f"{'✅' if done else m['emoji']}  {m['title']}  —  {m['deadline']}"

        with st.expander(label, expanded=False):
            if done:
                st.success("Completed ✅")
                if st.button("↩️ Mark incomplete", key=f"undo_{mid}"):
                    completed.discard(mid)
                    save_progress(completed)
                    st.rerun()
                continue

            # Priority badge
            badge = "🔴 Urgent" if m["priority"] == "urgent" else "🟡 Important"
            st.markdown(f"{badge}  ·  **{m['category']}**")
            st.markdown(f"**Why it matters:** {m['why']}")
            st.divider()
            st.markdown(m["how"])
            st.divider()

            # Per-mission chat
            st.markdown("**Ask Gemma 4 a follow-up question:**")
            if mid not in st.session_state.chats:
                st.session_state.chats[mid] = []

            for msg in st.session_state.chats[mid]:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

            q = st.chat_input("Ask anything about this mission…", key=f"q_{mid}")
            if q:
                st.session_state.chats[mid].append({"role": "user", "content": q})
                sys_ctx = (
                    f"You are Unpack, a knowledgeable friend helping an international student "
                    f"at {profile['university']} in {profile['country']} on a {profile['visa']}. "
                    f"Current mission: {m['title']}. Context: {m['why']}. "
                    f"Be concise, specific, and practical. Never give generic advice."
                )
                history = [{"role": "system", "content": sys_ctx}] + st.session_state.chats[mid]
                with st.spinner("Thinking…"):
                    reply = chat(history)
                st.session_state.chats[mid].append({"role": "assistant", "content": reply})
                st.rerun()

            st.divider()
            if st.button("✅  Mark as complete", key=f"done_{mid}", type="primary"):
                completed.add(mid)
                save_progress(completed)
                st.rerun()


# ── Router ────────────────────────────────────────────────────────────────────
def main():
    init_state()
    if st.session_state.profile is None:
        screen_setup()
    elif st.session_state.panic:
        screen_panic()
    else:
        screen_dashboard()


if __name__ == "__main__":
    main()
