from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {
            "role": "user",
            "content": "Hello, introduce yourself in one sentence."
        }
    ]
)

print(response.choices[0].message.content)