import os
from dotenv import load_dotenv
import streamlit as st
from google import genai
import re

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Initialize client
client = genai.Client(api_key=API_KEY) if API_KEY else genai.Client()

st.set_page_config(page_title="WorkPolish (Gemini)", layout="centered")
st.markdown("""
<style>
body, .stApp {
    background-color: #ffffff !important;
    color: #000000 !important;
}

/* Text area styling */
textarea, .stTextArea textarea {
    background-color: #f8f8f8 !important;
    color: #000000 !important;
    border-radius: 8px !important;
    border: 1px solid #cccccc !important;
    font-size: 16px !important;
}

/* General text */
div[data-testid="stMarkdownContainer"] p {
    color: #000000 !important;
}

/* Buttons (Polish + Download) */
div.stButton button, div[data-testid="stDownloadButton"] button {
    background-color: #007bff !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 0.6em 1.2em !important;
    font-weight: 600 !important;
    font-size: 16px !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15) !important;
    transition: all 0.2s ease-in-out;
}

div.stButton button:hover, div[data-testid="stDownloadButton"] button:hover {
    background-color: #0056b3 !important;
    transform: translateY(-1px);
}

/* Make buttons look distinct but aligned */
div[data-testid="stDownloadButton"] button::before {
    content: "⬇️ ";
}
</style>
""", unsafe_allow_html=True)

# ---- header ----
st.title("✨ WorkPolish — AI Workplace Writing Assistant (Gemini)")
st.write("Polish your professional emails, chat messages, and slides. Choose tone/context and click 'Polish'.")

# ---- UI components ----
user_text = st.text_area("Enter text to polish:", height=200)
tone = st.selectbox("Target tone", ["More formal", "More concise", "More polite", "More persuasive", "More casual"])
context = st.selectbox("Context", ["Email to manager", "Message to teammate", "Email to client", "PPT text", "Chat message"])
show_notes = st.checkbox("Show edit notes (2-3 bullets)", value=True)

def build_prompt(text: str, tone: str, context: str, show_notes: bool) -> str:
    prompt = (
        "You are a professional workplace writing assistant. "
        "Polish the text for clarity, tone, and conciseness while keeping the original meaning strictly unchanged.\n\n"
        f"- Target tone: {tone}\n"
        f"- Context: {context}\n"
        f"- Do not invent new facts or add content not present in the original text.\n\n"
        f"Original:\n\"\"\"\n{text}\n\"\"\"\n\n"
    )
    if show_notes:
        prompt += "Output format:\n1) Polished text\n2) 2-3 short bullet points describing key edits\n"
    else:
        prompt += "Output format: Polished text only.\n"
    return prompt

def parse_polished_and_notes(raw: str):
    """
    Try to split model output into polished_text and edit_notes.
    Looks for markers like '1)' and '2)' or '1.' and '2.' or headings.
    Returns (polished_text, edit_notes_list)
    If unable to parse, returns (raw, []).
    """
    text = raw.strip()

    # Try common "1) ... 2) ..." pattern (including newlines)
    m = re.search(r"(?:\n|^)\s*1[\)\.]([\s\S]*?)(?:\n\s*2[\)\.])([\s\S]*)", "\n" + text)
    if m:
        polished = m.group(1).strip()
        notes_raw = m.group(2).strip()
        # split notes into lines; remove numeric bullets if present
        notes = [re.sub(r"^\s*[-\d\.\)]+\s*", "", s).strip() for s in re.split(r"\n+", notes_raw) if s.strip()]
        return polished, notes

    # Try "Polished text:" heading then "Edit notes" heading
    m2 = re.search(r"Polished text[:\-]?\s*(.*?)\s*(?:\n+Edit notes[:\-]?|\n+Key edits[:\-]?|\n+2[\)\.])([\s\S]*)", text, flags=re.I|re.S)
    if m2:
        polished = m2.group(1).strip()
        notes_raw = m2.group(2).strip()
        notes = [s.strip() for s in re.split(r"[\n\r]+", notes_raw) if s.strip()]
        return polished, notes

    # Fallback: try to split by "2)" only
    parts = re.split(r"\n\s*2[\)\.]\s*", text, maxsplit=1)
    if len(parts) == 2:
        # remove any leading "1)" markers from first part
        first = re.sub(r"^\s*1[\)\.]\s*", "", parts[0]).strip()
        notes_raw = parts[1].strip()
        notes = [s.strip() for s in re.split(r"[\n\r]+", notes_raw) if s.strip()]
        return first, notes

    # If nothing matched, return raw as polished and no notes
    return text, []

# ---- action ----
if st.button("Polish ✨"):
    if not user_text.strip():
        st.warning("Please enter some text to polish.")
    else:
        st.info("Calling Gemini...")
        prompt = build_prompt(user_text, tone, context, show_notes)
        try:
            # Use the SDK's models.generate_content method (as in official examples)
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )

            # response.text is preferred; fallback to string of response
            raw_output = response.text if hasattr(response, "text") else str(response)

            # parse into polished and notes
            polished_text, notes = parse_polished_and_notes(raw_output if raw_output else "")

            # show polished result clearly
            st.subheader("✅ Polished result")
            st.markdown(polished_text.replace("\n", "  \n"))

            # show edit notes if requested and parsed
            if show_notes:
                st.subheader("✏️ Edit notes")
                if notes:
                    for n in notes:
                        st.markdown(f"- {n}")
                else:
                    # if no structured notes, show the tail of raw_output (best effort)
                    # attempt to display lines after polished_text in raw_output
                    # fallback: show entire raw_output under Notes
                    st.write("No structured notes parsed. Raw output:")
                    st.write(raw_output)

            # download button
            st.download_button("Download result (.txt)", data=polished_text, file_name="polished_text.txt", mime="text/plain")

        except Exception as e:
            st.error(f"API call failed: {e}")
            st.write("If this persists, please run `pip install --upgrade google-genai` and restart the app.")
            raise