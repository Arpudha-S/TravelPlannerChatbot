import requests
import os

API_KEY = os.getenv("OPENWEATHERMAP_API_KEY") or "your_api_key"

def fetch_weather_data(city):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    response = requests.get(url)
    data = response.json()

    temp = data['main']['temp']
    condition = data['weather'][0]['description'].title()
    if "rain" in condition.lower():
        advice = "Carry an umbrella."
    elif temp > 35:
        advice = "Stay hydrated and avoid outdoor activities."
    elif temp < 10:
        advice = "Wear warm clothes."
    else:
        advice = "Weather is ideal for travel."

    return {
        "temp": temp,
        "condition": condition,
        "advice": advice
    }
