from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Discord bot ok"

def run():
    port = int(os.environ.get("PORT", 8080))  # Render uses dynamic port sometimes
    app.run(host='0.0.0.0', port=port, debug=False)  # Explicitly turn off debug

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
