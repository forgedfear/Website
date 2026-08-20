import os
import secrets
import hashlib
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL")
DEV_PASSWORD = os.environ.get("DEV_PASSWORD")
API_SECRET = os.environ.get("API_SECRET")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

if not DEV_PASSWORD:
    raise RuntimeError("DEV_PASSWORD is not configured")

if not API_SECRET:
    raise RuntimeError("API_SECRET is not configured")


# --------------------------------------------------
# CORS
# --------------------------------------------------

# You can replace "*" with your actual GitHub Pages
# domain later for stricter security.
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*"
        }
    }
)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def get_db():
    return psycopg2.connect(DATABASE_URL)


def init_database():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS deletion_requests (
            id SERIAL PRIMARY KEY,
            playfab_id VARCHAR(255) NOT NULL,
            username VARCHAR(255) NOT NULL,
            additional_info TEXT,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    conn.commit()

    cur.close()
    conn.close()


# --------------------------------------------------
# DEVELOPER AUTH
# --------------------------------------------------

active_tokens = set()


def create_token():
    token = secrets.token_urlsafe(48)
    active_tokens.add(token)
    return token


def is_dev_authenticated():

    auth = request.headers.get("Authorization", "")

    if not auth.startswith("Bearer "):
        return False

    token = auth[7:]

    return token in active_tokens


def require_dev():

    if not is_dev_authenticated():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    return None


# --------------------------------------------------
# BASIC ROUTES
# --------------------------------------------------

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


# --------------------------------------------------
# DEVELOPER LOGIN
# --------------------------------------------------

@app.route("/api/dev/login", methods=["POST"])
def dev_login():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "error": "Invalid request"
        }), 400

    password = data.get("password", "")

    if not secrets.compare_digest(
        password,
        DEV_PASSWORD
    ):
        return jsonify({
            "success": False,
            "error": "Invalid password"
        }), 401

    token = create_token()

    return jsonify({
        "success": True,
        "token": token
    })


# --------------------------------------------------
# DEVELOPER LOGOUT
# --------------------------------------------------

@app.route("/api/dev/logout", methods=["POST"])
def dev_logout():

    auth = request.headers.get("Authorization", "")

    if auth.startswith("Bearer "):

        token = auth[7:]

        active_tokens.discard(token)

    return jsonify({
        "success": True
    })


# --------------------------------------------------
# CREATE DELETION REQUEST
# --------------------------------------------------

@app.route("/api/deletion-request", methods=["POST"])
def create_deletion_request():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "error": "Invalid request"
        }), 400

    playfab_id = str(
        data.get("playfab_id", "")
    ).strip()

    username = str(
        data.get("username", "")
    ).strip()

    additional_info = str(
        data.get("additional_info", "")
    ).strip()

    # Basic validation

    if not playfab_id:
        return jsonify({
            "success": False,
            "error": "PlayFab ID is required"
        }), 400

    if not username:
        return jsonify({
            "success": False,
            "error": "Username is required"
        }), 400

    if len(playfab_id) > 255:
        return jsonify({
            "success": False,
            "error": "PlayFab ID is too long"
        }), 400

    if len(username) > 255:
        return jsonify({
            "success": False,
            "error": "Username is too long"
        }), 400

    if len(additional_info) > 5000:
        return jsonify({
            "success": False,
            "error": "Additional information is too long"
        }), 400

    try:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO deletion_requests
            (
                playfab_id,
                username,
                additional_info
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """, (
            playfab_id,
            username,
            additional_info
        ))

        request_id = cur.fetchone()[0]

        conn.commit()

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "request_id": request_id
        }), 201

    except Exception as e:

        return jsonify({
            "success": False,
            "error": "Could not create deletion request"
        }), 500


# --------------------------------------------------
# GET ALL DELETION REQUESTS
# --------------------------------------------------

@app.route("/api/dev/deletion-requests", methods=["GET"])
def get_deletion_requests():

    auth_error = require_dev()

    if auth_error:
        return auth_error

    try:

        conn = get_db()

        cur = conn.cursor(
            cursor_factory=RealDictCursor
        )

        search = request.args.get(
            "search",
            ""
        ).strip()

        if search:

            cur.execute("""
                SELECT
                    id,
                    playfab_id,
                    username,
                    additional_info,
                    status,
                    created_at,
                    updated_at
                FROM deletion_requests
                WHERE
                    playfab_id ILIKE %s
                    OR username ILIKE %s
                ORDER BY created_at DESC
            """, (
                f"%{search}%",
                f"%{search}%"
            ))

        else:

            cur.execute("""
                SELECT
                    id,
                    playfab_id,
                    username,
                    additional_info,
                    status,
                    created_at,
                    updated_at
                FROM deletion_requests
                ORDER BY created_at DESC
            """)

        rows = cur.fetchall()

        cur.close()
        conn.close()

        requests_list = []

        for row in rows:

            item = dict(row)

            if item.get("created_at"):
                item["created_at"] = item[
                    "created_at"
                ].isoformat()

            if item.get("updated_at"):
                item["updated_at"] = item[
                    "updated_at"
                ].isoformat()

            requests_list.append(item)

        return jsonify({
            "success": True,
            "requests": requests_list
        })

    except Exception:

        return jsonify({
            "success": False,
            "error": "Could not load requests"
        }), 500


# --------------------------------------------------
# UPDATE REQUEST STATUS
# --------------------------------------------------

@app.route(
    "/api/dev/deletion-requests/<int:request_id>",
    methods=["PATCH"]
)
def update_deletion_request(request_id):

    auth_error = require_dev()

    if auth_error:
        return auth_error

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "error": "Invalid request"
        }), 400

    status = str(
        data.get("status", "")
    ).lower().strip()

    allowed_statuses = {
        "pending",
        "completed",
        "rejected"
    }

    if status not in allowed_statuses:

        return jsonify({
            "success": False,
            "error": "Invalid status"
        }), 400

    try:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            UPDATE deletion_requests
            SET
                status = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id
        """, (
            status,
            request_id
        ))

        result = cur.fetchone()

        if not result:

            conn.rollback()

            cur.close()
            conn.close()

            return jsonify({
                "success": False,
                "error": "Request not found"
            }), 404

        conn.commit()

        cur.close()
        conn.close()

        return jsonify({
            "success": True
        })

    except Exception:

        return jsonify({
            "success": False,
            "error": "Could not update request"
        }), 500


# --------------------------------------------------
# DELETE REQUEST RECORD
# --------------------------------------------------

@app.route(
    "/api/dev/deletion-requests/<int:request_id>",
    methods=["DELETE"]
)
def delete_deletion_request(request_id):

    auth_error = require_dev()

    if auth_error:
        return auth_error

    try:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM deletion_requests
            WHERE id = %s
            RETURNING id
        """, (
            request_id,
        ))

        result = cur.fetchone()

        if not result:

            conn.rollback()

            cur.close()
            conn.close()

            return jsonify({
                "success": False,
                "error": "Request not found"
            }), 404

        conn.commit()

        cur.close()
        conn.close()

        return jsonify({
            "success": True
        })

    except Exception:

        return jsonify({
            "success": False,
            "error": "Could not delete request"
        }), 500


# --------------------------------------------------
# STARTUP
# --------------------------------------------------

init_database()


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
            )
