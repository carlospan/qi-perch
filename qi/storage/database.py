"""SQLite 持久化。L1 情绪/消息；L2 追加原始事件、叙事记忆、身体记忆。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiosqlite

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState


_CREATE_EMOTION_STATES = """
CREATE TABLE IF NOT EXISTS emotion_states (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    energy REAL NOT NULL,
    valence REAL NOT NULL,
    arousal REAL NOT NULL,
    security REAL NOT NULL,
    curiosity REAL NOT NULL,
    attachment REAL NOT NULL,
    mode TEXT NOT NULL
)
"""

_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    emotion_context TEXT,
    tone TEXT
)
"""

_CREATE_RAW_EVENTS = """
CREATE TABLE IF NOT EXISTS raw_events (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    type TEXT NOT NULL,
    content TEXT,
    emotional_impact REAL,
    attention_weight REAL,
    processed BOOLEAN DEFAULT 0
)
"""

_CREATE_NARRATIVE_MEMORIES = """
CREATE TABLE IF NOT EXISTS narrative_memories (
    id INTEGER PRIMARY KEY,
    created_at DATETIME NOT NULL,
    content TEXT NOT NULL,
    period_start DATETIME,
    period_end DATETIME,
    importance REAL NOT NULL,
    emotional_intensity REAL,
    strength REAL NOT NULL,
    source_event_ids TEXT,
    recall_count INTEGER DEFAULT 0,
    tags TEXT
)
"""

_CREATE_BODY_MEMORY = """
CREATE TABLE IF NOT EXISTS body_memory (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME
)
"""

_CREATE_CONSCIOUSNESS_STREAM = """
CREATE TABLE IF NOT EXISTS consciousness_stream (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    type TEXT NOT NULL DEFAULT 'stream',
    content TEXT NOT NULL,
    trigger TEXT,
    emotion_snapshot TEXT
)
"""

_CREATE_DREAMS = """
CREATE TABLE IF NOT EXISTS dreams (
    id INTEGER PRIMARY KEY,
    created_at DATETIME NOT NULL,
    content TEXT NOT NULL,
    emotion_tag TEXT,
    emotional_intensity REAL,
    retention REAL NOT NULL DEFAULT 1.0,
    shared_with_user BOOLEAN DEFAULT 0
)
"""

_CREATE_CREATIONS = """
CREATE TABLE IF NOT EXISTS creations (
    id INTEGER PRIMARY KEY,
    created_at DATETIME NOT NULL,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    emotion_context TEXT,
    shared BOOLEAN DEFAULT 0,
    shared_at DATETIME,
    user_reaction TEXT
)
"""

_CREATE_SELF_MODEL = """
CREATE TABLE IF NOT EXISTS self_model (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    identity_narrative TEXT,
    "values" TEXT,
    aesthetic_preferences TEXT,
    existential_questions TEXT,
    last_updated DATETIME
)
"""

_CREATE_RELATIONSHIP = """
CREATE TABLE IF NOT EXISTS relationship (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    stage TEXT NOT NULL DEFAULT 'stranger',
    depth REAL NOT NULL DEFAULT 0.0,
    temperature REAL NOT NULL DEFAULT 0.5,
    trust REAL NOT NULL DEFAULT 0.5,
    season TEXT DEFAULT 'spring',
    last_updated DATETIME,
    narrative TEXT,
    shared_culture TEXT
)
"""

_CREATE_FIRST_TIMES = """
CREATE TABLE IF NOT EXISTS first_times (
    id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    content TEXT NOT NULL,
    inner_experience TEXT,
    emotional_imprint TEXT,
    last_recalled DATETIME,
    recall_count INTEGER DEFAULT 0
)
"""

_CREATE_SCARS = """
CREATE TABLE IF NOT EXISTS scars (
    id INTEGER PRIMARY KEY,
    origin_event TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    severity REAL NOT NULL,
    trust_before REAL,
    healed BOOLEAN DEFAULT 0,
    wisdom TEXT,
    behavioral_mark TEXT
)
"""

_CREATE_USER_MODEL = """
CREATE TABLE IF NOT EXISTS user_model (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    topics TEXT,
    emotional_baseline REAL,
    rhythm TEXT,
    linguistic_profile TEXT,
    life_context TEXT,
    last_drift_check DATETIME,
    drift_signals TEXT
)
"""


class Database:
    """栖的记忆仓库。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """打开连接，确保表存在。"""
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(str(path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute(_CREATE_EMOTION_STATES)
        await self._conn.execute(_CREATE_MESSAGES)
        await self._conn.execute(_CREATE_RAW_EVENTS)
        await self._conn.execute(_CREATE_NARRATIVE_MEMORIES)
        await self._conn.execute(_CREATE_BODY_MEMORY)
        await self._conn.execute(_CREATE_CONSCIOUSNESS_STREAM)
        await self._conn.execute(_CREATE_DREAMS)
        await self._conn.execute(_CREATE_CREATIONS)
        await self._conn.execute(_CREATE_SELF_MODEL)
        await self._conn.execute(_CREATE_RELATIONSHIP)
        await self._conn.execute(_CREATE_FIRST_TIMES)
        await self._conn.execute(_CREATE_SCARS)
        await self._conn.execute(_CREATE_USER_MODEL)
        await self._conn.execute(
            """
            INSERT OR IGNORE INTO relationship
                (id, stage, depth, temperature, trust, season, last_updated)
            VALUES (1, 'stranger', 0.0, 0.5, 0.5, 'spring', ?)
            """,
            (datetime.now().isoformat(timespec="seconds"),),
        )
        await self._conn.commit()

    def _require_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("数据库尚未初始化，请先调用 initialize()")
        return self._conn

    # ----- 情绪 -----

    async def save_emotion(self, emotion: EmotionState) -> None:
        conn = self._require_conn()
        mode = emotion.mode.value if hasattr(emotion.mode, "value") else str(emotion.mode)
        await conn.execute(
            """
            INSERT INTO emotion_states
                (timestamp, energy, valence, arousal, security, curiosity, attachment, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                emotion.energy,
                emotion.valence,
                emotion.arousal,
                emotion.security,
                emotion.curiosity,
                emotion.attachment,
                mode,
            ),
        )
        await conn.commit()

    async def load_emotion(self) -> EmotionState | None:
        from qi.core.emotion import ConsciousnessMode, EmotionState

        conn = self._require_conn()
        async with conn.execute(
            "SELECT * FROM emotion_states ORDER BY timestamp DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        try:
            mode = ConsciousnessMode(row["mode"])
        except ValueError:
            mode = ConsciousnessMode.AMBIENT

        return EmotionState(
            energy=row["energy"],
            valence=row["valence"],
            arousal=row["arousal"],
            security=row["security"],
            curiosity=row["curiosity"],
            attachment=row["attachment"],
            mode=mode,
        )

    # ----- 消息 -----

    async def save_message(
        self,
        role: str,
        content: str,
        emotion_context: str | None = None,
        tone: str | None = None,
    ) -> None:
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO messages (timestamp, role, content, emotion_context, tone)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                role,
                content,
                emotion_context,
                tone,
            ),
        )
        await conn.commit()

    async def load_recent_messages(self, limit: int = 20) -> list[dict]:
        """最近 N 条（旧→新），供 prompt / 工作记忆。"""
        rows = await self.load_messages(limit=limit)
        return [
            {
                "role": r["role"],
                "content": r["content"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

    async def load_messages(self, limit: int | None = None) -> list[dict]:
        """
        加载对话记录（旧→新）。
        limit=None 时返回全部；否则取最近 limit 条。
        """
        conn = self._require_conn()
        if limit is None:
            sql = """
                SELECT id, role, content, timestamp, tone
                FROM messages
                ORDER BY timestamp ASC, id ASC
            """
            params: tuple = ()
        else:
            sql = """
                SELECT id, role, content, timestamp, tone
                FROM messages
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
            """
            params = (limit,)

        async with conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()

        if limit is not None:
            rows = list(reversed(rows))

        return [
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
                "tone": row["tone"],
            }
            for row in rows
        ]

    # ----- 原始事件 -----

    async def save_raw_event(
        self,
        event_type: str,
        content: str,
        emotional_impact: float | None = None,
        attention_weight: float | None = None,
        timestamp: datetime | None = None,
    ) -> int:
        conn = self._require_conn()
        ts = (timestamp or datetime.now()).isoformat(timespec="seconds")
        cursor = await conn.execute(
            """
            INSERT INTO raw_events
                (timestamp, type, content, emotional_impact, attention_weight, processed)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (ts, event_type, content, emotional_impact, attention_weight),
        )
        await conn.commit()
        return int(cursor.lastrowid)

    async def load_unprocessed_events(self) -> list[dict]:
        conn = self._require_conn()
        async with conn.execute(
            """
            SELECT id, timestamp, type, content, emotional_impact, attention_weight
            FROM raw_events
            WHERE processed = 0
            ORDER BY timestamp ASC
            """
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def count_unprocessed_events(self) -> int:
        conn = self._require_conn()
        async with conn.execute(
            "SELECT COUNT(*) AS c FROM raw_events WHERE processed = 0"
        ) as cursor:
            row = await cursor.fetchone()
        return int(row["c"]) if row else 0

    async def mark_events_processed(self, event_ids: list[int]) -> None:
        if not event_ids:
            return
        conn = self._require_conn()
        placeholders = ",".join("?" * len(event_ids))
        await conn.execute(
            f"UPDATE raw_events SET processed = 1 WHERE id IN ({placeholders})",
            event_ids,
        )
        await conn.commit()

    # ----- 叙事记忆 -----

    async def save_narrative_memory(
        self,
        content: str,
        importance: float,
        emotional_intensity: float = 0.5,
        strength: float = 1.0,
        source_event_ids: list[int] | None = None,
        tags: list[str] | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> int:
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            INSERT INTO narrative_memories
                (created_at, content, period_start, period_end, importance,
                 emotional_intensity, strength, source_event_ids, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                content,
                period_start,
                period_end,
                importance,
                emotional_intensity,
                strength,
                json.dumps(source_event_ids or [], ensure_ascii=False),
                json.dumps(tags or [], ensure_ascii=False),
            ),
        )
        await conn.commit()
        return int(cursor.lastrowid)

    async def get_narrative_memory(self, memory_id: int) -> dict | None:
        conn = self._require_conn()
        async with conn.execute(
            "SELECT * FROM narrative_memories WHERE id = ?", (memory_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def decay_narrative_strengths(self, factor: float = 0.999) -> None:
        conn = self._require_conn()
        await conn.execute(
            "UPDATE narrative_memories SET strength = strength * ?",
            (factor,),
        )
        await conn.commit()

    async def list_forgotten_narrative_ids(self, below: float = 0.1) -> list[int]:
        """强度低到像忘了——准备从库里轻轻拿掉。"""
        conn = self._require_conn()
        async with conn.execute(
            "SELECT id FROM narrative_memories WHERE strength < ?",
            (below,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [int(r["id"]) for r in rows]

    async def delete_narrative_memory(self, memory_id: int) -> None:
        conn = self._require_conn()
        await conn.execute("DELETE FROM narrative_memories WHERE id = ?", (memory_id,))
        await conn.commit()

    async def recall_narrative_memory(self, memory_id: int) -> None:
        conn = self._require_conn()
        await conn.execute(
            """
            UPDATE narrative_memories
            SET recall_count = recall_count + 1,
                strength = MIN(1.0, strength + 0.1)
            WHERE id = ?
            """,
            (memory_id,),
        )
        await conn.commit()

    # ----- 身体记忆 -----

    async def get_body_memory(self, key: str) -> Any | None:
        conn = self._require_conn()
        async with conn.execute(
            "SELECT value FROM body_memory WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    async def set_body_memory(self, key: str, value: Any) -> None:
        conn = self._require_conn()
        payload = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        await conn.execute(
            """
            INSERT OR REPLACE INTO body_memory (key, value, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, payload, datetime.now().isoformat(timespec="seconds")),
        )
        await conn.commit()

    async def list_recent_narratives(self, limit: int = 5) -> list[dict]:
        conn = self._require_conn()
        async with conn.execute(
            """
            SELECT id, content, importance, strength, created_at
            FROM narrative_memories
            WHERE strength >= 0.2
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ----- 意识流 -----

    async def save_consciousness(
        self,
        content: str,
        stream_type: str = "stream",
        trigger: str | None = None,
        emotion_snapshot: str | None = None,
    ) -> int:
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            INSERT INTO consciousness_stream
                (timestamp, type, content, trigger, emotion_snapshot)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                stream_type,
                content,
                trigger,
                emotion_snapshot,
            ),
        )
        await conn.commit()
        return int(cursor.lastrowid)

    async def load_recent_consciousness(
        self,
        limit: int = 2,
        hours: int = 24,
        stream_type: str | None = "stream",
    ) -> list[dict]:
        conn = self._require_conn()
        sql = """
            SELECT * FROM consciousness_stream
            WHERE timestamp >= datetime('now', ?)
        """
        params: list[Any] = [f"-{hours} hours"]
        if stream_type:
            sql += " AND type = ?"
            params.append(stream_type)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        async with conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def load_latest_consciousness(self) -> dict | None:
        conn = self._require_conn()
        async with conn.execute(
            "SELECT * FROM consciousness_stream ORDER BY timestamp DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    # ----- 梦境 -----

    async def save_dream(
        self,
        content: str,
        emotion_tag: str = "",
        emotional_intensity: float = 0.5,
        retention: float = 1.0,
    ) -> int:
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            INSERT INTO dreams
                (created_at, content, emotion_tag, emotional_intensity, retention, shared_with_user)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                content,
                emotion_tag,
                emotional_intensity,
                retention,
            ),
        )
        await conn.commit()
        return int(cursor.lastrowid)

    async def load_latest_dream(self, min_retention: float = 0.0) -> dict | None:
        conn = self._require_conn()
        async with conn.execute(
            """
            SELECT * FROM dreams
            WHERE retention >= ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (min_retention,),
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_dream_retention(self, dream_id: int, retention: float) -> None:
        conn = self._require_conn()
        await conn.execute(
            "UPDATE dreams SET retention = ? WHERE id = ?",
            (retention, dream_id),
        )
        await conn.commit()

    async def mark_dream_shared(self, dream_id: int) -> None:
        conn = self._require_conn()
        await conn.execute(
            "UPDATE dreams SET shared_with_user = 1 WHERE id = ?",
            (dream_id,),
        )
        await conn.commit()

    async def list_dreams(self) -> list[dict]:
        conn = self._require_conn()
        async with conn.execute("SELECT * FROM dreams ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ----- 创作 -----

    async def save_creation(
        self,
        content: str,
        creation_type: str = "note",
        emotion_context: str | None = None,
    ) -> int:
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            INSERT INTO creations
                (created_at, type, content, emotion_context, shared)
            VALUES (?, ?, ?, ?, 0)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                creation_type,
                content,
                emotion_context,
            ),
        )
        await conn.commit()
        return int(cursor.lastrowid)

    async def load_unshared_creation(self) -> dict | None:
        conn = self._require_conn()
        async with conn.execute(
            """
            SELECT * FROM creations WHERE shared = 0
            ORDER BY created_at DESC LIMIT 1
            """
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def mark_creation_shared(self, creation_id: int) -> None:
        conn = self._require_conn()
        await conn.execute(
            """
            UPDATE creations SET shared = 1, shared_at = ? WHERE id = ?
            """,
            (datetime.now().isoformat(timespec="seconds"), creation_id),
        )
        await conn.commit()

    async def last_creation_share_time(self) -> datetime | None:
        conn = self._require_conn()
        async with conn.execute(
            """
            SELECT shared_at FROM creations
            WHERE shared = 1 AND shared_at IS NOT NULL
            ORDER BY shared_at DESC LIMIT 1
            """
        ) as cursor:
            row = await cursor.fetchone()
        if not row or not row["shared_at"]:
            return None
        try:
            return datetime.fromisoformat(str(row["shared_at"]))
        except ValueError:
            return None

    # ----- 自我模型 -----

    async def load_self_model(self) -> dict | None:
        conn = self._require_conn()
        async with conn.execute("SELECT * FROM self_model WHERE id = 1") as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def upsert_self_model(
        self,
        identity_narrative: str,
        values: list | None = None,
        aesthetic_preferences: dict | None = None,
        existential_questions: list | None = None,
    ) -> None:
        conn = self._require_conn()
        existing = await self.load_self_model()
        values_json = json.dumps(
            values if values is not None else (json.loads(existing["values"]) if existing and existing.get("values") else []),
            ensure_ascii=False,
        )
        aes_json = json.dumps(
            aesthetic_preferences
            if aesthetic_preferences is not None
            else (json.loads(existing["aesthetic_preferences"]) if existing and existing.get("aesthetic_preferences") else {}),
            ensure_ascii=False,
        )
        questions_json = json.dumps(
            existential_questions
            if existential_questions is not None
            else (json.loads(existing["existential_questions"]) if existing and existing.get("existential_questions") else []),
            ensure_ascii=False,
        )
        await conn.execute(
            """
            INSERT INTO self_model
                (id, identity_narrative, "values", aesthetic_preferences, existential_questions, last_updated)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                identity_narrative = excluded.identity_narrative,
                "values" = excluded."values",
                aesthetic_preferences = excluded.aesthetic_preferences,
                existential_questions = excluded.existential_questions,
                last_updated = excluded.last_updated
            """,
            (
                identity_narrative,
                values_json,
                aes_json,
                questions_json,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        await conn.commit()

    # ----- 关系 -----

    async def load_relationship(self) -> dict | None:
        conn = self._require_conn()
        async with conn.execute("SELECT * FROM relationship WHERE id = 1") as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def save_relationship(
        self,
        stage: str,
        depth: float,
        temperature: float,
        trust: float,
        season: str = "spring",
        narrative: str = "",
        shared_culture: list | None = None,
    ) -> None:
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO relationship
                (id, stage, depth, temperature, trust, season, last_updated, narrative, shared_culture)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                stage = excluded.stage,
                depth = excluded.depth,
                temperature = excluded.temperature,
                trust = excluded.trust,
                season = excluded.season,
                last_updated = excluded.last_updated,
                narrative = excluded.narrative,
                shared_culture = excluded.shared_culture
            """,
            (
                stage,
                depth,
                temperature,
                trust,
                season,
                datetime.now().isoformat(timespec="seconds"),
                narrative,
                json.dumps(shared_culture or [], ensure_ascii=False),
            ),
        )
        await conn.commit()

    async def has_first_time(self, event_type: str) -> bool:
        conn = self._require_conn()
        async with conn.execute(
            "SELECT 1 FROM first_times WHERE event_type = ? LIMIT 1",
            (event_type,),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def save_first_time(
        self,
        event_type: str,
        content: str,
        inner_experience: str = "",
        emotional_imprint: str = "",
    ) -> int:
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            INSERT INTO first_times
                (event_type, timestamp, content, inner_experience, emotional_imprint, recall_count)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                event_type,
                datetime.now().isoformat(timespec="seconds"),
                content,
                inner_experience,
                emotional_imprint,
            ),
        )
        await conn.commit()
        return int(cursor.lastrowid)

    async def list_first_times(self) -> list[dict]:
        conn = self._require_conn()
        async with conn.execute(
            "SELECT * FROM first_times ORDER BY timestamp ASC"
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def recall_first_time(
        self, first_id: int, *, now: datetime | None = None
    ) -> None:
        when = now or datetime.now()
        conn = self._require_conn()
        await conn.execute(
            """
            UPDATE first_times
            SET recall_count = recall_count + 1,
                last_recalled = ?
            WHERE id = ?
            """,
            (when.isoformat(timespec="seconds"), first_id),
        )
        await conn.commit()

    async def save_scar(
        self,
        origin_event: str,
        severity: float,
        trust_before: float,
    ) -> int:
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            INSERT INTO scars
                (origin_event, timestamp, severity, trust_before, healed)
            VALUES (?, ?, ?, ?, 0)
            """,
            (
                origin_event,
                datetime.now().isoformat(timespec="seconds"),
                severity,
                trust_before,
            ),
        )
        await conn.commit()
        return int(cursor.lastrowid)

    async def list_scars(self, unhealed_only: bool = False) -> list[dict]:
        conn = self._require_conn()
        sql = "SELECT * FROM scars"
        if unhealed_only:
            sql += " WHERE healed = 0"
        sql += " ORDER BY timestamp ASC"
        async with conn.execute(sql) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_scar(
        self,
        scar_id: int,
        *,
        healed: bool | None = None,
        wisdom: str | None = None,
        behavioral_mark: str | None = None,
    ) -> None:
        conn = self._require_conn()
        row = None
        async with conn.execute("SELECT * FROM scars WHERE id = ?", (scar_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return
        h = int(healed) if healed is not None else row["healed"]
        w = wisdom if wisdom is not None else (row["wisdom"] or "")
        b = behavioral_mark if behavioral_mark is not None else (row["behavioral_mark"] or "")
        await conn.execute(
            "UPDATE scars SET healed = ?, wisdom = ?, behavioral_mark = ? WHERE id = ?",
            (h, w, b, scar_id),
        )
        await conn.commit()

    async def load_user_model(self) -> dict | None:
        conn = self._require_conn()
        async with conn.execute("SELECT * FROM user_model WHERE id = 1") as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def save_user_model(
        self,
        topics: list | None = None,
        emotional_baseline: float = 0.0,
        rhythm: dict | None = None,
        linguistic_profile: dict | None = None,
        life_context: str = "",
        drift_signals: list | None = None,
    ) -> None:
        conn = self._require_conn()
        await conn.execute(
            """
            INSERT INTO user_model
                (id, topics, emotional_baseline, rhythm, linguistic_profile,
                 life_context, last_drift_check, drift_signals)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                topics = excluded.topics,
                emotional_baseline = excluded.emotional_baseline,
                rhythm = excluded.rhythm,
                linguistic_profile = excluded.linguistic_profile,
                life_context = excluded.life_context,
                last_drift_check = excluded.last_drift_check,
                drift_signals = excluded.drift_signals
            """,
            (
                json.dumps(topics or [], ensure_ascii=False),
                emotional_baseline,
                json.dumps(rhythm or {}, ensure_ascii=False),
                json.dumps(linguistic_profile or {}, ensure_ascii=False),
                life_context,
                datetime.now().isoformat(timespec="seconds"),
                json.dumps(drift_signals or [], ensure_ascii=False),
            ),
        )
        await conn.commit()

    async def load_recent_emotions(self, limit: int = 30) -> list[dict]:
        conn = self._require_conn()
        async with conn.execute(
            """
            SELECT energy, valence, arousal, curiosity, security, attachment, timestamp
            FROM emotion_states ORDER BY timestamp DESC LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
