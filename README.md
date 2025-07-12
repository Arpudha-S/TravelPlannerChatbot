# TravelPlannerChatbot
## Use Case
   This project implements an AI-driven Travel Planner Chatbot that assists users in planning trips by answering queries related to weather, safety, attractions, and accommodations. Users can upload travel brochures, which are processed using OCR. The system scrapes trusted travel websites and summarizes the information in an admin dashboard. Disaster warnings and advisories are highlighted. Admins can monitor data, view persistent chat histories by session ID, and export reports. Weather data is auto-refreshed hourly. Out-of-scope queries are handled with polite, predefined messages
## Prerequisite
  Python Flask\
  Vector DB - pip install chromadb , pip install sentence-transformers\
  LLM - pip install google-generativeai\
  SQL DB - pip install pysqlite3\
  Securely store API keys secretly in .env file
## Front End
User ask question about travel to Chatbot Screen.\
![](Screenshots/chatbotquery.png)

Scrapes URL from Attractions weather safety hotel web sites.\
![](Screenshots/scrapedurl.png)

Displays weather forecast for cities.\
![](Screenshots/weathforecast.png)

Admin Login Page.\
![](Screenshots/adminlogin.png)

API keys for security and authentication.\
![](Screenshots/apikeys.png)

Chat History for entire session.\
![](Screenshots/chathistory.png)

LLM settings and bot configuration.\
![](Screenshots/llmsettings.png)

Recent cache.\
![](Screenshots/recentcache.png)

> [!NOTE]  
> The vector database changes depending on Python version. For Python 3.12+ use Qdrant instead of ChromaDB.
