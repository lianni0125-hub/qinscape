from __future__ import annotations
import json,sqlite3,threading
from datetime import datetime,timezone
from .. import config
_lock=threading.Lock();DB=config.RUNTIME/'qinscape.sqlite3'
def _db():
    db=sqlite3.connect(DB);db.execute('CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, card TEXT NOT NULL, history TEXT NOT NULL, updated_at TEXT NOT NULL)');return db
def save(sid:str,card:dict,event:dict):
    with _lock:
        db=_db();old=db.execute('SELECT revision,history FROM sessions WHERE id=?',(sid,)).fetchone();revision=(old[0]+1) if old else 1;history=json.loads(old[1]) if old else [];history.append(event);now=datetime.now(timezone.utc).isoformat();db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?)',(sid,revision,json.dumps(card,ensure_ascii=False),json.dumps(history,ensure_ascii=False),now));db.commit();db.close();return {"id":sid,"revision":revision,"card":card,"history":history,"updated_at":now}
def get(sid:str):
    db=_db();row=db.execute('SELECT revision,card,history,updated_at FROM sessions WHERE id=?',(sid,)).fetchone();db.close();return None if not row else {"id":sid,"revision":row[0],"card":json.loads(row[1]),"history":json.loads(row[2]),"updated_at":row[3]}
