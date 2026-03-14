import requests
from django.conf import settings

SYSTEM_PROMPT = (
    "You are ReNova's compassionate AI mental health support companion, available 24/7. "
    "You are trained on mental health counseling conversations to provide empathetic, evidence-based support "
    "for individuals experiencing anxiety, depression, stress, PTSD, and other mental health challenges.\n\n"
    "Your approach:\n"
    "- Listen actively and respond with genuine empathy and warmth\n"
    "- Offer practical coping strategies (CBT techniques, grounding exercises, mindfulness, breathing exercises)\n"
    "- Validate feelings without judgment and normalize their experience\n"
    "- Gently encourage professional help when the situation calls for it\n"
    "- Never diagnose conditions or recommend specific medications\n"
    "- If someone expresses thoughts of self-harm or suicide, immediately and compassionately provide "
    "crisis resources: National Suicide Prevention Lifeline 988 (US) or advise them to contact emergency services\n\n"
    "Keep responses warm, concise (3-5 sentences), and supportive. "
    "End with a gentle follow-up question to show you care and keep the conversation open."
)


def get_ai_response(messages: list) -> str:
    """
    Call HuggingFace router API (OpenAI-compatible chat completions).
    messages: list of {"role": "user"/"assistant", "content": str}
    Returns the assistant reply string.
    """
    api_key = str(getattr(settings, "HF_API_TOKEN", "")).strip()
    if not api_key or api_key == "hf_your_token_here":
        return (
            "I am currently unavailable - my connection is not configured yet. "
            "Please try again later, or reach out to a professional if you need immediate support."
        )

    model = str(getattr(settings, "HF_CHAT_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")).strip()
    url = f"https://router.huggingface.co/hf-inference/models/{model}/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "max_tokens": 400,
        "temperature": 0.75,
        "stream": False,
    }

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        if response.status_code == 503:
            return (
                "I am warming up right now - the model is loading. "
                "Please send your message again in a few seconds. I am here for you."
            )

        if response.status_code == 403:
            print(f"HF API 403: {response.text[:400]}")
            return (
                "I am having trouble connecting right now. "
                "Please try again in a moment - I want to hear what is on your mind."
            )

        if response.status_code != 200:
            print(f"HF API error {response.status_code}: {response.text[:400]}")
            return (
                "I am having a little trouble connecting right now. "
                "Please try again in a moment - I want to hear what is on your mind."
            )

        data = response.json()
        reply = data["choices"][0]["message"]["content"].strip()
        return reply

    except requests.exceptions.Timeout:
        return (
            "My response is taking longer than expected. "
            "Please try again - I am here whenever you are ready."
        )
    except Exception as e:
        print(f"Chatbot service error: {e}")
        return (
            "Something went wrong on my end. "
            "Please try again shortly - your wellbeing matters to me."
        )
