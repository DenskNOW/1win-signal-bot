from fastapi import FastAPI, Request
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

@app.get("/postback")
async def postback(request: Request):
    params = dict(request.query_params)
    sub1 = params.get("sub1")
    status = params.get("status")

    if not sub1 or not status:
        return {"error": "missing sub1 or status"}

    try:
        os.makedirs("db", exist_ok=True)
        conn = sqlite3.connect("db/database.db")
        cursor = conn.cursor()

        if status == "reg":
            cursor.execute("UPDATE users SET registered = 1 WHERE user_id = ?", (sub1,))
        elif status == "dep":
            cursor.execute("UPDATE users SET deposited = 1 WHERE user_id = ?", (sub1,))
        conn.commit()
        conn.close()
        return {"success": True, "sub1": sub1, "status": status}
    except Exception as e:
        return {"error": str(e)}
