"""临时脚本：最新对话+内部状态全查。用完即删。"""
import sqlite3

SINCE = "2026-07-31T21:53"

out = open("_convo_dump.txt", "w", encoding="utf-8")
conn = sqlite3.connect("data/qi.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute(f"SELECT * FROM messages WHERE timestamp > '{SINCE}' ORDER BY id")
out.write("=== 新消息 ===\n")
rows = cur.fetchall()
for r in rows:
    d = dict(r)
    out.write(f"[{d.get('timestamp')}] {d.get('role')}: {(d.get('content') or '').replace(chr(10),' ')[:340]}\n")
if not rows:
    out.write("(无)\n")

out.write("\n=== 新意识流 ===\n")
cur.execute(f"SELECT * FROM consciousness_stream WHERE timestamp > '{SINCE}' ORDER BY id")
rows = cur.fetchall()
for r in rows:
    d = dict(r)
    out.write(f"[{d['timestamp']}] {d['type']}/{d['trigger']}: {(d['content'] or '').replace(chr(10),' ')}\n")
if not rows:
    out.write("(无)\n")

out.write("\n=== 新叙事 ===\n")
cur.execute(f"SELECT id, content, created_at, tags FROM narrative_memories WHERE created_at > '{SINCE}' ORDER BY id")
rows = cur.fetchall()
for r in rows:
    d = dict(r)
    out.write(f"id={d['id']} [{d['created_at']}] tags={d.get('tags')} {(d['content'] or '').replace(chr(10),' ')[:280]}\n")
if not rows:
    out.write("(无)\n")

out.write("\n=== 梦 ===\n")
cur.execute("SELECT * FROM dreams ORDER BY id DESC LIMIT 3")
rows = cur.fetchall()
for r in rows:
    d = dict(r)
    if d.get("content"):
        d["content"] = d["content"].replace("\n", " ")[:400]
    out.write(str(d) + "\n")
if not rows:
    out.write("(仍 0)\n")

out.write("\n=== user_facts / first_times / scars ===\n")
cur.execute("SELECT id, fact_type, content FROM user_facts WHERE superseded_by IS NULL ORDER BY id")
for r in cur.fetchall():
    out.write("FACT: " + str(dict(r)) + "\n")
cur.execute("SELECT id, event_type, timestamp, recall_count FROM first_times ORDER BY id")
for r in cur.fetchall():
    out.write("FT: " + str(dict(r)) + "\n")
cur.execute("SELECT COUNT(*) AS n FROM scars")
out.write(f"scars: {dict(cur.fetchone())}\n")

out.write("\n=== 未编织 / 心跳 / 关系 / shared_culture ===\n")
cur.execute("SELECT COUNT(*) AS n FROM raw_events WHERE processed = 0")
out.write(f"unprocessed: {dict(cur.fetchone())}\n")
cur.execute("SELECT value, updated_at FROM body_memory WHERE key='last_heartbeat_trace'")
r = cur.fetchone()
if r:
    out.write(f"最后心跳: {dict(r)['updated_at']}\n")
cur.execute("SELECT stage, depth, temperature, trust, season FROM relationship ORDER BY id DESC LIMIT 1")
out.write(str(dict(cur.fetchone())) + "\n")
cur.execute("SELECT shared_culture FROM relationship ORDER BY id DESC LIMIT 1")
r = cur.fetchone()
if r:
    out.write("culture: " + (r["shared_culture"] or "")[:300] + "\n")

out.write("\n=== 情绪轨迹（每 8 条取 1）===\n")
cur.execute(f"SELECT * FROM emotion_states WHERE timestamp > '{SINCE}' ORDER BY id")
emo = cur.fetchall()
out.write(f"共 {len(emo)} 条\n")
for i, r in enumerate(emo):
    if i % 8 == 0 or i == len(emo) - 1:
        d = dict(r)
        out.write(
            f"[{d['timestamp']}] v={d['valence']:.2f} e={d['energy']:.2f} "
            f"a={d['arousal']:.2f} sec={d['security']:.2f} cur={d['curiosity']:.2f} "
            f"att={d['attachment']:.2f} {d['mode']}\n"
        )

conn.close()
out.close()
print("done")
