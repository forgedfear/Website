from flask import Flask
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Forged Fear API"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
