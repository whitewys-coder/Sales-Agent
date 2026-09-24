import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "data/sales_agent.sqlite3")
APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
app = FastAPI(title="Sales Agent for Feishu", version="0.1.0")


@contextmanager
def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            signal TEXT NOT NULL,
            source_name TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            score REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            feedback TEXT
        )""")


init_db()


class LeadIn(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    signal: str = Field(min_length=1, max_length=1000)
    source_name: str = Field(default="", max_length=200)
    source_url: str = Field(default="", max_length=2000)
    score: float = Field(default=0, ge=0, le=100)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/leads")
def add_lead(lead: LeadIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO leads(company,signal,source_name,source_url,score,updated_at) VALUES(?,?,?,?,?,?)",
            (lead.company, lead.signal, lead.source_name, lead.source_url, lead.score, lead.updated_at),
        )
        return {"id": cur.lastrowid, "status": "created"}


def get_leads(limit: int = 10):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM leads ORDER BY score DESC, updated_at DESC LIMIT ?", (limit,)
        ).fetchall()


def render_lead(row: Any) -> str:
    parts = [f"#{row['id']} {row['company']}（{row['score']:.0f}分）", row["signal"]]
    if row["source_name"]:
        parts.append(f"来源：{row['source_name']}")
    if row["source_url"]:
        parts.append(f"证据：{row['source_url']}")
    parts.append(f"更新时间：{row['updated_at']}")
    return "\n".join(parts)


def answer(command: str) -> str:
    command = command.strip()
    if command in ("/help", "帮助", "菜单"):
        return "销售 Agent 命令：\n/today 今日优先线索\n/company 企业名 查询企业\n/valid 线索ID 标记有效\n/invalid 线索ID 标记无效"
    if command in ("/today", "今日线索"):
        rows = get_leads()
        return "今日优先线索（按当前分数排序）:\n\n" + (
            "\n\n".join(render_lead(r) for r in rows) if rows else "暂无已录入线索。"
        )
    if command.startswith("/company "):
        name = command[len("/company "):].strip()
        if not name:
            return "用法：/company 企业名"
        with db() as conn:
            rows = conn.execute(
                "SELECT * FROM leads WHERE company LIKE ? ORDER BY score DESC LIMIT 10",
                (f"%{name}%",),
            ).fetchall()
        return "\n\n".join(render_lead(r) for r in rows) if rows else f"没有找到“{name}”的线索。"
    for prefix, value in (("/valid ", "valid"), ("/invalid ", "invalid")):
        if command.startswith(prefix):
            try:
                lead_id = int(command[len(prefix):].strip())
            except ValueError:
                return f"用法：{prefix}线索ID"
            with db() as conn:
                cur = conn.execute("UPDATE leads SET feedback=? WHERE id=?", (value, lead_id))
            return f"已记录 #{lead_id} 判断：{'有效' if value == 'valid' else '无效'}。" if cur.rowcount else "未找到该线索编号。"
    return "暂不支持该指令。发送 /help 查看用法。"


def tenant_access_token() -> str:
    if not APP_ID or not APP_SECRET:
        raise RuntimeError("FEISHU_APP_ID / FEISHU_APP_SECRET 未配置")
    response = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"获取飞书 tenant token 失败：{payload}")
    return payload["tenant_access_token"]


def reply_to_message(message_id: str, text: str):
    token = tenant_access_token()
    response = requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"msg_type": "text", "content": json.dumps({"text": text}, ensure_ascii=False)},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"飞书回复失败：{payload}")


@app.post("/feishu/events")
async def feishu_events(request: Request):
    body = await request.json()
    # URL verification handshake required by Feishu event subscription.
    if "challenge" in body:
        if VERIFICATION_TOKEN and body.get("token") != VERIFICATION_TOKEN:
            raise HTTPException(status_code=403, detail="invalid verification token")
        return {"challenge": body["challenge"]}

    header = body.get("header", {})
    event = body.get("event", {})
    token = header.get("token") or body.get("token")
    if VERIFICATION_TOKEN and token != VERIFICATION_TOKEN:
        raise HTTPException(status_code=403, detail="invalid verification token")

    # Ignore non-message events and events without a message identifier.
    if header.get("event_type") not in (None, "im.message.receive_v1"):
        return {"code": 0}
    message = event.get("message", {})
    message_id = message.get("message_id")
    if not message_id:
        return {"code": 0}
    try:
        content = json.loads(message.get("content", "{}"))
        command = content.get("text", "").strip()
        # Remove bot mention placeholders if Feishu included them.
        for mention in message.get("mentions", []):
            if mention.get("key"):
                command = command.replace(mention["key"], "").strip()
        reply_to_message(message_id, answer(command))
    except Exception as exc:
        # Avoid returning sensitive internals to the user; deployment logs should capture the exception.
        print(f"Feishu event handling failed: {type(exc).__name__}: {exc}")
    return {"code": 0}
