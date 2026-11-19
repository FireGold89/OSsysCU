import os
import sys

os.environ["DATA_DIR"] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "_data",
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db


def test_get_project_summary_q525():
    db.init_db()
    conn = db.get_conn()
    row = conn.execute(
        "SELECT id FROM projects WHERE project_code LIKE '%Q525%'"
    ).fetchone()
    conn.close()
    assert row is not None
    summary = db.get_project_summary(row[0])
    assert summary is not None
    assert summary.get("contract_calc") is not None