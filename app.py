import os
from dotenv import load_dotenv
import streamlit as st
from google import genai

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Initialize client
client = genai.Client(api_key=API_KEY) if API_KEY else genai.Client()

st.set_page_config(page_title="WorkPolish (Gemini)", layout="centered")
st.markdown(
    """
    <style>
    /* page background and text color */
    html, body, .stApp {
        background-color: #ffffff;
        color: #000000;
    }
    /* main container background (in case of theming) */
    .css-18e3th9 {  /* Streamlit main block */
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    /* headings and subheaders */
    h1, h2, h3, h4, h5, h6 {
        color: #000000 !important;
    }
    /* style the download button and primary button */
    button[kind="primary"] {
        background-color: #111111 !important;
        color: #ffffff !important;
    }
    /* text area text color */
    textarea, input[type="text"] {
        color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("✨ WorkPolish — AI Workplace Writing Assistant (Gemini)")
st.write("Polish your professional emails, chat messages, and slides. Choose tone/context and click 'Polish'.")

# UI components
user_text = st.text_area("Enter text to polish:", height=200)
tone = st.selectbox("Target tone", ["More formal", "More concise", "More polite", "More persuasive", "More casual"])
context = st.selectbox("Context", ["Email to manager", "Message to manager","Message to teammate", "Email to business", "PPT text", "Chat message"])
show_notes = st.checkbox("Show edit notes (2-3 bullets)", value=True)

def build_prompt(text: str, tone: str, context: str, show_notes: bool) -> str:
    prompt = (
        f"You are a professional workplace writing assistant. "
        f"Polish the text for clarity, tone, and conciseness while keeping the original meaning strictly unchanged.\n\n"
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

if st.button("Polish ✨"):
    if not user_text.strip():
        st.warning("Please enter some text to polish.")
    else:
        st.info("Calling Gemini...")
        prompt = build_prompt(user_text, tone, context, show_notes)
        try:
            # Use the SDK's models.generate_content method
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )

            # Extract polished text from the response
            polished = response.text if hasattr(response, "text") else str(response)

            st.subheader("✅ Polished result")
            st.write(polished)
            st.download_button("Download result (.txt)", data=polished, file_name="polished_text.txt", mime="text/plain")

        except Exception as e:
            st.error(f"API call failed: {e}")
            st.write("If this persists, please run `pip install --upgrade google-genai` and restart the app.")
            raise