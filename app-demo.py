import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import numpy as np
import io
import base64
import openai
import os
import json
import re

# Setup OpenAI key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(layout="wide")
st.title("Ulysses")
if "clear_canvas" not in st.session_state:
    st.session_state.clear_canvas = False

# 🎯 Difficulty dropdown
st.sidebar.title("Choose Difficulty")
difficulty = st.sidebar.selectbox("Select level:", ["Easy 🟢", "Medium 🟡", "Hard 🔴"], index=1)
difficulty_map = {"Easy 🟢": "easy", "Medium 🟡": "medium", "Hard 🔴": "hard"}

# Format LaTeX nicely
def clean_latex_response(text):
    text = re.sub(r'\\\((.*?)\\\)', r'$\1$', text)
    text = re.sub(r'\\\[([\s\S]*?)\\\]', r'$$\1$$', text)
    return text

# Generate question
def generate_problem(difficulty_level):
    system = st.secrets["PROMPT_SYSTEM_PROBLEM"].format(difficulty_level=difficulty_level)
    user = "Return as JSON with keys: question, choices (list), solution_method1, solution_method2, correct_answer."

    res = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    )

    content = res.choices[0].message.content.strip()
    try:
        data = json.loads(content)
    except:
        try:
            json_str = content[content.find('{'):content.rfind('}') + 1]
            data = json.loads(json_str)
        except:
            data = {
                "question": "What is 2 + 2?",
                "choices": ["A. 3", "B. 4", "C. 5", "D. 6"],
                "solution_method1": "Add the numbers directly.",
                "solution_method2": "Use a number line.",
                "correct_answer": "B"
            }
    return data

# 🔄 State logic
if "problem" not in st.session_state or st.session_state.get("current_difficulty") != difficulty_map[difficulty]:
    st.session_state.problem = generate_problem(difficulty_map[difficulty])
    st.session_state.current_difficulty = difficulty_map[difficulty]
    st.session_state.feedback = None
    st.session_state.correct = False

q = st.session_state.problem

# Display question
st.subheader("🔢 Question:")
st.markdown(f"**{q['question']}**")

choice_labels = ["A", "B", "C", "D", "E"]
for i, opt in enumerate(q["choices"]):
    label = choice_labels[i] if i < len(choice_labels) else f"Option {i+1}"
    st.markdown(f"**{label})** {opt}")

# Canvas for working
st.subheader("📝 Show your working:")
# 🧼 Determine whether to clear the canvas or reuse the last drawing
initial_image = None if st.session_state.get("clear_canvas", False) else st.session_state.get("last_drawing", None)

canvas_result = st_canvas(
    stroke_width=3,
    stroke_color="#000000",
    background_color="#ffffff",
    update_streamlit=True,
    height=600,
    width=800,
    drawing_mode="freedraw",
    key="canvas",
    initial_drawing=initial_image
)

# 🧠 Save current drawing for possible reuse
if canvas_result.image_data is not None:
    st.session_state.last_drawing = canvas_result.image_data

# 🔁 Reset the flag after using it
st.session_state.clear_canvas = False 

# Process submission
if canvas_result.image_data is not None:
    img = Image.fromarray((canvas_result.image_data[:, :, :3]).astype(np.uint8))
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    img_url = f"data:image/png;base64,{img_base64}"

    if st.button("📤 Submit Your Solution"):
        with st.spinner("Evaluating..."):
            prompt = (
                f"You are a math tutor reviewing a student's handwritten solution.\n\n"
                f"Question: {q['question']}\n"
                f"Options: {', '.join(str(choice) for choice in q['choices'])}\n"
                f"Correct Answer: {q['correct_answer']}\n\n"
                f"Method 1: {q['solution_method1']}\n"
                f"Method 2: {q['solution_method2']}\n\n"
                f"Your task:\n"
                f"- Speak directly to the student as 'you'.\n"
                f"- If their answer is correct: praise them, explain why it works, and suggest trying another method (don't show answer).\n"
                f"- If wrong: DO NOT show the correct answer. Instead, identify their error and offer helpful hints to retry.\n"
                f"- Format with LaTeX where appropriate."
            )

            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": st.secrets["PROMPT_FEEDBACK_SYSTEM"]},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": img_url}}
                    ]}
                ],
                temperature=0.3
            )

            reply = response.choices[0].message.content
            st.session_state.feedback = clean_latex_response(reply)
            st.session_state.correct = "another method" in reply.lower()
            st.rerun()

# 🎯 Show feedback
if st.session_state.feedback:
    st.subheader("📣 Feedback")
    st.markdown(st.session_state.feedback)

    if st.session_state.correct:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔁 Try Again (Another Method)"):
                st.session_state.feedback = None
                st.session_state.clear_canvas = True  # 🧽 Clear canvas
                st.rerun()
        with col2:
            if st.button("➡️ Next Question"):
                st.session_state.problem = generate_problem(difficulty_map[difficulty])
                st.session_state.feedback = None
                st.session_state.correct = False
                st.session_state.clear_canvas = True  # 🧽 Clear canvas
                st.rerun()
    else:
        if st.button("🔄 Retry Your Answer"):
            st.session_state.feedback = None
            st.session_state.clear_canvas = False  # 🛑 Keep existing drawing
            st.rerun()
