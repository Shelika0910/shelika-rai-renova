import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

def get_gemini_response(prompt: str, history=None) -> str:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {"Content-Type": "application/json"}

    # Initialize contents with the system prompt/instruction
    contents = [{
        "role": "user",
        "parts": [{
            "text": "You are a friendly, empathetic mental health assistant named ReNova. Your goal is to provide supportive, safe, and non-judgmental conversations. You should not give medical advice, but you can offer general wellness tips and encourage users to seek professional help when appropriate. Keep your responses concise and caring."
        }]
    }, {
        "role": "model",
        "parts": [{
            "text": "I understand. I am ReNova, a supportive mental health assistant. How can I help you today?"
        }]
    }]

    # Add historical messages
    if history:
        for message in history:
            role = "user" if message.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": message.content}]})

    # Add the latest user prompt
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 500
        }
    }
    
    params = {"key": API_KEY}

    try:
        response = requests.post(url, json=payload, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if 'candidates' in data and data['candidates']:
            candidate = data['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content'] and candidate['content']['parts']:
                return candidate['content']['parts'][0]['text']
        
        return "Sorry, I could not process the response."

    except requests.exceptions.RequestException as e:
        print(f"Gemini API error: {e}")
        if e.response:
            print(f"Response body: {e.response.text}")
        return "Sorry, I am having trouble responding right now."
    except (KeyError, IndexError) as e:
        print(f"Error parsing Gemini response: {e}")
        return "Sorry, there was an issue with the response format."