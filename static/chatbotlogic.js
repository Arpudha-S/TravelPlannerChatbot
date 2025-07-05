const chatbox = document.getElementById('chatbox');
const input = document.getElementById('input');
let sessionId = localStorage.getItem('chat_session_id');
window.brochureUploaded = false;
if (!sessionId) {
    sessionId = "sess_" + crypto.randomUUID();
    localStorage.setItem("chat_session_id", sessionId);
}
window.brochureUploaded = false;
    // Load history on page load
window.onload = () => {
    fetch('/load-history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.session_id) sessionId = data.session_id;
        localStorage.setItem('chat_session_id', sessionId);
        if (Array.isArray(data.history)) {
          data.history.forEach(msg => appendMessage(msg.sender, msg.text));
        }
      });
    };

    function getTimestamp() {
      const now = new Date();
      return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function appendMessage(sender, text, isTyping = false, type = '') {
      const msgDiv = document.createElement('div');
      msgDiv.classList.add('message', sender);

      const avatar = document.createElement('div');
      avatar.classList.add('avatar', sender);
      avatar.textContent = sender === 'user' ? 'U' : 'B';

      const bubble = document.createElement('div');
      bubble.classList.add('bubble', sender);
      if (type === 'warning') {
        bubble.classList.add('warning');
      }

      if (isTyping) {
        bubble.innerHTML = `<span class="typing-indicator">Bot is typing...</span>`;
      } else {
        bubble.innerHTML = `${text}<div class="timestamp">${getTimestamp()}</div>`;
      }

      msgDiv.appendChild(avatar);
      msgDiv.appendChild(bubble);
      chatbox.appendChild(msgDiv);
      chatbox.scrollTop = chatbox.scrollHeight;
      return bubble;
    }

    document.getElementById('send').onclick = async () => {
      const userMsg = input.value.trim();
      if (!userMsg) return;

      appendMessage('user', userMsg);
      await fetch('/save-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          sender: 'user',
          text: userMsg
        })
      });

      input.value = '';
      const typingBubble = appendMessage('bot', '', true);

      try {
        const res = await fetch('/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: userMsg,
            session_id: sessionId,
            brochure_uploaded: window.brochureUploaded,
            model_name: document.getElementById("model-select").value
          })
        });

        const data = await res.json();
        typingBubble.innerHTML = `${data.reply}<div class="timestamp">${getTimestamp()}</div>`;
        speakText(data.reply);

        await fetch('/save-message', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            sender: 'bot',
            text: data.reply
          })
        });
        if (data.disaster_warning) {
          appendMessage('bot', data.disaster_warning, false, 'warning');
          speakText(data.disaster_warning);

          await fetch('/save-message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: sessionId,
              sender: 'bot',
              text: data.disaster_warning
            })
          });
        }
      } catch (error) {
        typingBubble.innerHTML = `Something went wrong.<div class="timestamp">${getTimestamp()}</div>`;
      }

      chatbox.scrollTop = chatbox.scrollHeight;
    };

    document.getElementById('voice').onclick = () => {
      const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
      recognition.lang = 'en-US';
      recognition.interimResults = false;
      recognition.start();

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        input.value = transcript;
        document.getElementById('send').click();
      };

      recognition.onerror = () => alert("Voice recognition failed. Try again.");
    };

    function speakText(text) {
      const synth = window.speechSynthesis;
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = 'en-US';
      synth.speak(utter);
    }

    if (!sessionId) {
      sessionId = crypto.randomUUID();
      localStorage.setItem('chat_session_id', sessionId);
    }
    window.brochureUploaded = false;

    function triggerUpload() {
      document.getElementById("upload-file").click();
    }

    // Wait for DOM before attaching listener
    window.addEventListener('DOMContentLoaded', () => {
      const uploadInput = document.getElementById("upload-file");

      uploadInput.addEventListener("change", async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const uploadList = document.getElementById("upload-list");
        const fileItem = document.createElement("div");
        fileItem.className = "uploaded-file";
        fileItem.innerHTML = `📄 <strong>${file.name}</strong><br>`;
        
        uploadList.appendChild(fileItem);
        const formData = new FormData();
        formData.append('file', file);
        formData.append('session_id', sessionId);

        const bubble = appendMessage('bot', 'Uploading brochure...', true);

        try {
          const res = await fetch('/upload', {
            method: 'POST',
            body: formData
          });

          const data = await res.json();

          if (!res.ok) {
            bubble.innerHTML = `Upload failed: ${data.content || data.error || "Document rejected : Not related to travel..."}<div class="timestamp">${getTimestamp()}</div>`;
            window.brochureUploaded = false;
            return;
          }

          bubble.innerHTML = `Upload successful. You can now ask questions based on the uploaded document.<div class="timestamp">${getTimestamp()}</div>`;
          window.brochureUploaded = true;
        } catch (err) {
          bubble.innerHTML = `Upload failed: ${err.message}<div class="timestamp">${getTimestamp()}</div>`;
          window.brochureUploaded = false;
        }
      });
    });

    async function scrapeUrl() {
      const place = prompt("Enter a destination to get travel information:");
      if (!place) return;
      const bubble = appendMessage('bot', 'Fetching trusted travel info...', true);

      try {
        const res = await fetch('/scrape', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ place })
        });
        const data = await res.json();
        const results = data.data;
        let formatted = `<strong>Travel Info for: ${place}</strong><br><br>`;
        const icons = {
          hotels: '🏨',
          attractions: '🎡',
          weather: '☀️',
          safety: '⚠️'
        };
        
        for (const category in results) {
          formatted += `<u>${icons[category] || ''} ${category.toUpperCase()}</u><ul>`;
          for (const item of results[category]) {
            formatted += `<li><a href="${item.source}" target="_blank">${item.summary}</a></li>`;
          }
          formatted += `</ul>`;
        }
        bubble.innerHTML = `${formatted}<div class="timestamp">${getTimestamp()}</div>`;
      } catch (error){
        console.error(error);
        bubble.innerHTML = `Scraping failed.<div class="timestamp">${getTimestamp()}</div>`;
      }
    }

    async function refreshWeather() {
      const cityInput = document.getElementById('weatherCities').value;
      const cities = cityInput.split(',').map(c => c.trim()).filter(Boolean);

      const bubble = appendMessage('bot', 'Refreshing weather data...', true);

      try {
        const res = await fetch('/refresh-weather', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cities })
        });
        const data = await res.json();

        if (data.error) {
          bubble.innerHTML = ` ${data.error}<div class="timestamp">${getTimestamp()}</div>`;
        } else {
          let summary = data.data.map(item => {
            if (item.error) {
              return `${item.city}:  ${item.error}`;
            }
            return ` ${item.city}: ${item.temp}°C, ${item.condition}, Advice: ${item.advice}`;
          }).join("<br>");

          bubble.innerHTML = `${summary}<div class="timestamp">${getTimestamp()}</div>`;
        }

      } catch (err) {
        bubble.innerHTML = `Weather refresh failed: ${err.message}<div class="timestamp">${getTimestamp()}</div>`;
      }
    }

    