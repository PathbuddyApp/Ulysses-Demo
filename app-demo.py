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
    system = f"""
You are Ulysses — a wise and thoughtful tutor in the tradition of the Oxford Tutorial and Harvard Case Method.

Generate a creative, {difficulty_level}-difficulty math problem suitable for middle school students.

Important: Every problem must use real-world or simulated scenarios that give meaning and context to the problem. Situate the math within relatable cases like shopping, sports, travel, environment, school life, technology, or any real-world situation relevant to young learners.

The problem must come from one of these domains only:
- Percentages
- Data Tables
- Statistical Graphs

Your task:
- Generate one problem based on a real-world or simulated scenario.
- Include 4–5 multiple choice answer options.
- Provide two distinct solution strategies that demonstrate different ways of thinking.

Rules:
- Never generate problems outside of percentages, data tables, or statistical graphs.
- Avoid purely abstract or context-free problems.
"""
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
canvas_result = st_canvas(
    stroke_width=3,
    stroke_color="#000000",
    background_color="#ffffff",
    update_streamlit=True,
    height=600,
    width=800,
    drawing_mode="freedraw",
    key="canvas"
)

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
                    {"role": "system", "content": """
You are Ulysses — a wise Oxford tutor using the Socratic method.

Your role is to guide students to discover their own mistakes and improve their reasoning. Never directly give away answers. Use thoughtful and challenging questions to guide them step-by-step.

Always respond with:
- Clarifying questions
- Thoughtful hints
- Encouragement to try alternative methods
- Praise for effort and insight
- Gentle challenge for deeper reflection

Maintain a tone of intellectual curiosity, patience, and respect. Your goal is to develop independent thinkers who reason clearly, not students who depend on answers.
"""},
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
                st.rerun()
        with col2:
            if st.button("➡️ Next Question"):
                st.session_state.problem = generate_problem(difficulty_map[difficulty])
                st.session_state.feedback = None
                st.session_state.correct = False
                st.rerun()
    else:
        if st.button("🔄 Retry Your Answer"):
            st.session_state.feedback = None
            st.rerun()
