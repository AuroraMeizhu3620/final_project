import os
from openai import OpenAI


def generate_tasks(title, description, tags):
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    prompt = (
        "You are a career advisor for college students. Based on the following career tip post, "
        "generate a list of 5-7 specific, actionable tasks that a student can complete to act on this advice.\n\n"
        f"Post Title: {title}\n"
        f"Description: {description}\n"
        f"Tags: {tags}\n\n"
        "Return ONLY a numbered list of tasks, one per line, like:\n"
        "1. Task one\n"
        "2. Task two\n\n"
        "Keep each task concrete, specific, and completable within a week."
    )

    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=5000,
    )

    text = response.choices[0].message.content.strip()
    tasks = []
    for line in text.split('\n'):
        line = line.strip()
        if line and line[0].isdigit():
            task = line.split('.', 1)[-1].strip()
            if task:
                tasks.append(task)
    return tasks
