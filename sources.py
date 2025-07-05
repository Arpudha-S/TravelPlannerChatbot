from bs4 import BeautifulSoup
import requests
from urllib.parse import quote_plus

TRUSTED_SOURCES = {
    'hotels': [
        'https://www.booking.com/searchresults.html?ss=',
        'https://www.expedia.com/Hotel-Search?destination=',
        'https://www.trivago.com/en-US/srl?query=',
        'https://www.makemytrip.com/hotels/hotel-listing/?city='
    ],
    'attractions': [
        'https://www.lonelyplanet.com/search?q=',
        'https://www.booking.com/attractions/index.html?ss=',
        'https://www.airbnb.com/s/'
    ],
    'weather': [
        'https://www.accuweather.com/en/search-locations?query=',
        'https://www.weather-forecast.com/locations/'
    ],
    'safety': [
        'https://www.who.int/search?q=',
        'https://www.travelsafe-abroad.com/countries/',
        'https://www.safertravel.org/countries-around-the-world/',
        'https://www.topindianholidays.com/india-travel-advisory-safety-guide'
    ]
}

def fetch_summary(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        text = ' '.join(p.get_text() for p in paragraphs if len(p.get_text()) > 30)  # Only meaningful text
        return text.strip()[:500] + '...' if text else None
    except Exception:
        return None

def google_fallback(query, topic):
    encoded = quote_plus(f"{query} {topic}")
    return f"https://www.google.com/search?q={encoded}"