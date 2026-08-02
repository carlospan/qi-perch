"""阶段二 判据#2 溯源验证脚本（只读，不写库）。

用途：从 broadcast_traces 中抽取「非 idle 自主胜出」的拍（winner_kind 不属于
respond/idle），逐条打印其因果链（候选列表 + 动机 + 最终 winner + 是否匹配 legacy），
并统计是否达到「10/10 因果链清晰可溯」。

判据口径：
  - 自主拍 = winner_kind 不在 {respond, idle}
  - 因果链清晰 = 该拍存在 >=1 个候选，且 winner 能在 candidates 中找到对应 kind，
    且其 salience/reason 可解释（非空）
  - 10/10 = 抽样的自主拍中，因果链清晰的比例 == 100% 且样本数 >= 10

运行：python tests/traceability_probe.py
"""
import json
import sqlite3
import sys

DB_PATH = "data/qi.db"


def load_traces(limit=None):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    if limit:
        cur.execute(
            "SELECT id, beat, timestamp, winner_kind, winner_salience, "
            "candidates_json, motive_json, outcome, arb_matches_legacy "
            "FROM broadcast_traces ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    else:
        cur.execute(
            "SELECT id, beat, timestamp, winner_kind, winner_salience, "
            "candidates_json, motive_json, outcome, arb_matches_legacy "
            "FROM broadcast_traces ORDER BY id"
        )
    rows = cur.fetchall()
    con.close()
    return rows


def is_autonomous(row):
    return row["winner_kind"] not in ("respond", "idle")


def candidate_clear(row):
    """判断该拍因果链是否清晰可溯。"""
    try:
        cands = json.loads(row["candidates_json"] or "[]")
    except Exception:
        cands = []
    if not cands:
        return False, "无候选列表"
    # winner 必须在候选中能找到
    wk = row["winner_kind"]
    match = [c for c in cands if c.get("kind") == wk]
    if not match:
        return False, f"winner={wk} 不在候选列表中"
    m = match[0]
    if not m.get("reason"):
        return False, "winner 候选缺 reason（无法解释为何胜出）"
    if m.get("salience") is None:
        return False, "winner 候选缺 salience"
    return True, f"winner={wk} sal={m.get('salience')} reason={m.get('reason')}"


def main():
    rows = load_traces()
    auto_rows = [r for r in rows if is_autonomous(r)]

    print(f"全量拍数: {len(rows)}")
    print(f"自主胜出拍数 (winner_kind 非 respond/idle): {len(auto_rows)}")
    print("=" * 70)

    if not auto_rows:
        print("【结果】尚无自主胜出拍，判据#2 未满足（样本=0）。")
        print("建议：让栖独处运行，积累 action/journal/close_loop 等自主拍。")
        return 1

    clear = 0
    for r in auto_rows:
        ok, detail = candidate_clear(r)
        clear += 1 if ok else 0
        flag = "OK " if ok else "FAIL"
        print(f"[{flag}] id={r['id']} kind={r['winner_kind']} "
              f"sal={r['winner_salience']} ts={r['timestamp']}")
        print(f"      {detail}")
        # 打印完整候选链（前 3 个），辅助人工核验
        try:
            cands = json.loads(r["candidates_json"] or "[]")
        except Exception:
            cands = []
        for c in cands[:3]:
            print(f"      candidate: {c.get('kind')} sal={c.get('salience')} "
                  f"reason={c.get('reason')}")
        if r["motive_json"]:
            try:
                mot = json.loads(r["motive_json"])
                if mot:
                    print(f"      motive: {str(mot)[:120]}")
            except Exception:
                pass
        print()

    print("=" * 70)
    ratio = clear / len(auto_rows)
    print(f"因果链清晰: {clear}/{len(auto_rows)} (ratio={ratio:.2f})")

    if len(auto_rows) >= 10 and ratio == 1.0:
        print("【结果】判据#2 满足：自主拍 >=10 且 10/10 因果链清晰可溯。✅")
        return 0
    elif len(auto_rows) < 10:
        print(f"【结果】样本不足（{len(auto_rows)}<10），判据#2 暂未满足。")
        print("建议：继续让栖独处运行，积累更多自主拍后重跑。")
        return 1
    else:
        print("【结果】存在因果链不清晰的自主拍，判据#2 未满足。需排查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
