#!/usr/bin/env python3
import os
import struct
import sqlite3
import unicodedata
from pathlib import Path
from flask import Flask, jsonify, request, g, send_from_directory
import numpy as np

DB_PATH = Path(__file__).parent / "settlements.db"
AGE_ORDER = ["0-14", "15-29", "30-44", "45-59", "60-74", "75+"]
AGE5_ORDER = ["0-4", "5-9", "10 -14", "15-19", "20-24", "25-29", "30-34", "35-39",
              "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75+"]
GENDER_LABELS = ["Άρρενες", "Θήλεις"]
EMP_CATS = ["Απασχολούμενοι", "Άνεργοι", "Μαθητές-σπουδαστές",
            "Συνταξιούχοι", "Λοιποί μη ενεργοί"]
CAR_CATS = ["0 αυτοκίνητα", "1 αυτοκίνητο", "2 αυτοκίνητα", "3+ αυτοκίνητα"]

# Order of dimensions as stored in the joint4d blob, and the order the
# drill-down UI walks through them.
JOINT4D_LEVELS = [
    {"name": "Φύλο", "labels": GENDER_LABELS},
    {"name": "Απασχόληση", "labels": EMP_CATS},
    {"name": "Ηλικιακή ομάδα", "labels": AGE_ORDER},
    {"name": "Επίπεδο εκπαίδευσης", "labels": None},  # filled in from edu_levels table
]
JOINT4D_SHAPE = (2, 5, 6, 7)

app = Flask(__name__, static_folder="static", static_url_path="/static")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def strip_accents(s):
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def normalize(s):
    s = strip_accents(s).lower()
    s = s.replace("ς", "σ")
    return " ".join(s.split())


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/search")
def search():
    q = request.args.get("q", "").strip()
    if len(q) < 1:
        return jsonify([])
    key = normalize(q)
    db = get_db()
    # Rank: exact match, then "starts with", then "contains", then by population desc
    rows = db.execute(
        """
        SELECT code, display_name, clean_name, municipality_code, population,
          CASE
            WHEN search_key = ? THEN 0
            WHEN search_key LIKE ? THEN 1
            ELSE 2
          END AS rank
        FROM settlements
        WHERE search_key LIKE ?
        ORDER BY rank ASC, population DESC
        LIMIT 15
        """,
        (key, f"{key}%", f"%{key}%"),
    ).fetchall()
    muni_codes = {r["municipality_code"] for r in rows}
    munis = {}
    if muni_codes:
        qmarks = ",".join("?" * len(muni_codes))
        for m in db.execute(
            f"SELECT code, name FROM municipalities WHERE code IN ({qmarks})",
            tuple(muni_codes),
        ):
            munis[m["code"]] = m["name"]
    results = [
        {
            "code": r["code"],
            "name": r["display_name"],
            "population": r["population"],
            "municipality": munis.get(r["municipality_code"], ""),
        }
        for r in rows
    ]
    return jsonify(results)


def add_total_row(columns, rows, label="Σύνολο"):
    """Append a real 'Σύνολο' row summing every numeric column -- used so the
    bold last-row styling always lands on an actual total, not on whichever
    category happens to be listed last."""
    n = len(columns) - 1
    totals = [0] * n
    for r in rows:
        for i in range(n):
            totals[i] += r[i + 1]
    return rows + [[label] + [round(t) for t in totals]]


@app.route("/api/settlement/<code>")
def settlement(code):
    db = get_db()
    s = db.execute(
        "SELECT s.*, m.name AS municipality_name FROM settlements s "
        "LEFT JOIN municipalities m ON s.municipality_code = m.code "
        "WHERE s.code = ?",
        (code,),
    ).fetchone()
    if not s:
        return jsonify({"error": "not found"}), 404

    edu_labels = _edu_labels(db)

    # Table 1: sex x age (5-year bins)
    sex_age_rows = db.execute(
        "SELECT sex, age_bin, population FROM sex_age WHERE settlement_code=?",
        (code,),
    ).fetchall()
    sex_age = {"Άρρενες": {}, "Θήλεις": {}, "Σύνολο": {}}
    for r in sex_age_rows:
        sex_age[r["sex"]][r["age_bin"]] = r["population"]
    table_sex_age = {
        "columns": ["Ηλικιακή ομάδα", "Άρρενες", "Θήλεις", "Σύνολο"],
        "rows": add_total_row(["_", "Άρρενες", "Θήλεις", "Σύνολο"], [
            [b, sex_age["Άρρενες"].get(b, 0), sex_age["Θήλεις"].get(b, 0),
             sex_age["Σύνολο"].get(b, 0)]
            for b in AGE5_ORDER
        ]),
    }

    # Table 2: sex x education
    sex_edu_rows = db.execute(
        "SELECT sex, edu_level, population FROM sex_edu WHERE settlement_code=?",
        (code,),
    ).fetchall()
    sex_edu = {"Άρρενες": {}, "Θήλεις": {}, "Σύνολο": {}}
    for r in sex_edu_rows:
        sex_edu[r["sex"]][r["edu_level"]] = r["population"]
    table_sex_edu = {
        "columns": ["Επίπεδο εκπαίδευσης", "Άρρενες", "Θήλεις", "Σύνολο"],
        "rows": add_total_row(["_", "Άρρενες", "Θήλεις", "Σύνολο"], [
            [e, sex_edu["Άρρενες"].get(e, 0), sex_edu["Θήλεις"].get(e, 0),
             sex_edu["Σύνολο"].get(e, 0)]
            for e in edu_labels
        ]),
    }

    # Table 3: age x education (double-constrained IPF)
    age_edu_rows = db.execute(
        "SELECT age_group, edu_level, population FROM age_edu WHERE settlement_code=?",
        (code,),
    ).fetchall()
    age_edu = {a: {} for a in AGE_ORDER}
    for r in age_edu_rows:
        age_edu[r["age_group"]][r["edu_level"]] = r["population"]
    table_age_edu = {
        "columns": ["Ηλικιακή ομάδα"] + edu_labels + ["Σύνολο"],
        "rows": add_total_row(["_"] + edu_labels + ["Σύνολο"], [
            [a] + [round(age_edu[a].get(e, 0)) for e in edu_labels]
            + [round(sum(age_edu[a].get(e, 0) for e in edu_labels))]
            for a in AGE_ORDER
        ]),
        "is_estimated": True,
    }

    # Table 4: gender x employment (single-margin IPF)
    table_gender_emp = _build_emp_table(
        db, "gender_emp", "gender", code, GENDER_LABELS, "Φύλο")
    # Table 5: age group x employment (single-margin IPF)
    table_age_emp = _build_emp_table(
        db, "age_emp", "age_group", code, AGE_ORDER, "Ηλικιακή ομάδα")
    # Table 6: education x employment (single-margin IPF)
    table_edu_emp = _build_emp_table(
        db, "edu_emp", "edu_level", code, edu_labels, "Επίπεδο εκπαίδευσης")

    # Table 7 (plot): cars per household -- real data, inherited from the
    # settlement's parent Δημοτική Κοινότητα (ELSTAT doesn't publish this
    # below that level).
    car_row = db.execute(
        "SELECT * FROM car_household WHERE settlement_code=?", (code,)
    ).fetchone()
    car_chart = None
    if car_row:
        car_chart = {
            "categories": CAR_CATS,
            "values": [car_row["no_car"], car_row["one_car"],
                       car_row["two_cars"], car_row["three_plus_cars"]],
            "total_households": car_row["total_households"],
            "dk_name": car_row["dk_name"],
        }

    has_joint4d = db.execute(
        "SELECT 1 FROM joint4d WHERE settlement_code=?", (code,)
    ).fetchone() is not None

    return jsonify({
        "code": s["code"],
        "name": s["display_name"],
        "clean_name": s["clean_name"],
        "article": s["article"],
        "municipality": s["municipality_name"],
        "population": s["population"],
        "table_sex_age": table_sex_age,
        "table_sex_edu": table_sex_edu,
        "table_age_edu": table_age_edu,
        "table_gender_emp": table_gender_emp,
        "table_age_emp": table_age_emp,
        "table_edu_emp": table_edu_emp,
        "car_chart": car_chart,
        "has_joint4d": has_joint4d,
    })


def _build_emp_table(db, table_name, group_col, code, group_order, group_label):
    rows_raw = db.execute(
        f"SELECT {group_col} AS grp, emp_cat, population FROM {table_name} "
        f"WHERE settlement_code=?",
        (code,),
    ).fetchall()
    if not rows_raw:
        return None
    by_group = {g: {} for g in group_order}
    for r in rows_raw:
        if r["grp"] in by_group:
            by_group[r["grp"]][r["emp_cat"]] = r["population"]
    rows = [
        [g] + [round(by_group[g].get(cat, 0)) for cat in EMP_CATS]
        + [round(sum(by_group[g].get(cat, 0) for cat in EMP_CATS))]
        for g in group_order
    ]
    columns = [group_label] + EMP_CATS + ["Σύνολο"]
    return {
        "columns": columns,
        "rows": add_total_row(columns, rows),
        "is_estimated": True,
    }


def _edu_labels(db):
    return [r["short_label"] for r in db.execute(
        "SELECT short_label FROM edu_levels ORDER BY idx")]


@app.route("/api/settlement/<code>/joint4d")
def joint4d(code):
    """
    Drill-down endpoint for the 4D joint distribution (gender x employment x
    age x education). `path` is a comma-separated list of chosen indices so
    far (e.g. path=0 means "gender=Άρρενες already chosen"); the response
    gives the breakdown of the NEXT dimension given that path, or the exact
    population if all 4 dimensions are already fixed.
    """
    db = get_db()
    row = db.execute(
        "SELECT blob, total FROM joint4d WHERE settlement_code=?", (code,)
    ).fetchone()
    if not row:
        return jsonify({"error": "no 4D estimate for this settlement"}), 404

    levels = JOINT4D_LEVELS
    if levels[3]["labels"] is None:
        levels[3]["labels"] = _edu_labels(db)

    path_param = request.args.get("path", "").strip()
    path = [int(x) for x in path_param.split(",") if x != ""] if path_param else []
    if len(path) > 4:
        return jsonify({"error": "path too long"}), 400

    arr = np.frombuffer(row["blob"], dtype=np.float32).reshape(JOINT4D_SHAPE)
    sub = arr[tuple(path)] if path else arr

    if sub.ndim == 0:
        return jsonify({"level": 4, "value": round(float(sub))})

    values = sub if sub.ndim == 1 else sub.sum(axis=tuple(range(1, sub.ndim)))
    level_idx = len(path)
    return jsonify({
        "level": level_idx,
        "name": levels[level_idx]["name"],
        "labels": levels[level_idx]["labels"],
        "values": [round(float(v)) for v in values],
        "path_labels": [levels[i]["labels"][p] for i, p in enumerate(path)],
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
