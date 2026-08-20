import os
import psycopg2
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg2.connect(DATABASE_URL)


@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "service": "Forged Fear API"
    })


@app.route("/api/test-db")
def test_db():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT NOW()")
        result = cur.fetchone()

        cur.close()
        conn.close()

        return jsonify({
            "database": "connected",
            "time": str(result[0])
        })

    except Exception as e:
        return jsonify({
            "database": "error",
            "message": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
