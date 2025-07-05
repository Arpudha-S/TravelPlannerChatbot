import requests
import os
import re
from google.generativeai import GenerativeModel, configure
from collections import deque

DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY") or "your_deepinfra_api_key_here"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "your_gemini_api_key_here"

recent_cache = deque(maxlen=100)
def generate_answer(message, context="", model_name="deepseek"):
    prompt = f"""You are a helpful AI assistant.

Use the following context to answer the user's question.

Context:
{context}

User Question:
{message}

Answer:"""
    try:
        if model_name == "deepseek":
            reply = call_deepseek(prompt)
            if "couldn't process" in reply:
                raise Exception("DeepSeek returned error text.")
        elif model_name == "gemini":
            reply = call_gemini(prompt)
        elif model_name == "mistral":
            reply = call_mistral(prompt)
        else:
            reply = "Model not supported."
    except Exception as e:
        print(f"[Fallback Triggered] {e}")
        try:
            reply = call_gemini(prompt)
        except:
            reply = "All model services are currently unavailable."
    recent_cache.appendleft({"question": message, "answer": reply})
    return reply

def call_deepseek(prompt):   
    url = "https://api.deepinfra.com/v1/inference/mistralai/Mistral-7B-Instruct-v0.1"
    headers = {
        "Authorization": f"Bearer {DEEPINFRA_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "input": prompt,
        "max_new_tokens": 512,
        "temperature": 0.7,
        "do_sample": True,
        "top_p": 0.9
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["results"][0]["generated_text"].strip()
    except Exception as e:
        print(f"[DeepSeek Error] {e}")
        return "Sorry, I couldn't process your query at the moment."
    
def call_mistral(prompt):
    return call_deepseek(prompt)

def call_gemini(prompt):
    try:
        configure(api_key=GEMINI_API_KEY)
        model = GenerativeModel("models/gemini-pro")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"[Gemini Error] {e}")
        return "Gemini failed to respond."

def health_check_deepseek():
    try:
        response = call_deepseek("Hello, are you alive?")
        return True if response else False
    except:
        return False

def is_in_scope(text):
    travel_keywords = {
        "travel", "trip", "vacation", "holiday", "tourism", "tourist", "destination", "journey", "itinerary", "plan", "package", "explore", "sightseeing", "experience",
        "places", "attractions", "landmarks", "monuments", "heritage", "beaches", "mountains", "valleys", "lakes", "parks", "hotels", "resort", "stay", "guesthouse", 
        "camping", "flights", "airline", "airport", "transport", "booking", "book", "reservation", "ticket", "visa", "passport", "weather", "climate", "temperature", 
        "forecast", "safety", "warning", "advisory", "emergency", "disaster", "health", "precautions", "map", "tour", "brochure", "itinerary", "cafe", "restaurant", 
        "foods", "dishes", "cuisines", "culture", "tradition", "language", "customs", "festivals", "shopping", "souvenirs", "crafts"
    }
    text_words = set(re.findall(r'\b\w+\b', text.lower()))
    matched_keywords = travel_keywords.intersection(text_words)
    return len(matched_keywords) >= 1
