
(function () {
    const script = document.currentScript;
    const apiKey = script.getAttribute('data-api-key') || '';
  
    const iframe = document.createElement('iframe');
    iframe.style.width = '400px';
    iframe.style.height = '420px';
    iframe.style.border = 'none';
    iframe.style.position = 'fixed';
    iframe.style.bottom = '20px';
    iframe.style.right = '20px';
    iframe.style.zIndex = '9999';
    iframe.style.borderRadius = '12px';
    iframe.setAttribute('title', 'Travel Planner Bot');
  
    document.body.appendChild(iframe);
  
    const doc = iframe.contentDocument || iframe.contentWindow.document;
  
    fetch('http://localhost:5000/static/widgetbody.html')
      .then(res => res.text())
      .then(html => {
        doc.open();
        doc.write(html.replace('{{API_KEY}}', apiKey));
        doc.close();
      });
  })();
  