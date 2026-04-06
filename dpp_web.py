"""
DPP Search — Web UI
--------------------
Run with: python3 dpp_web.py
Then open: http://localhost:5000
"""

import sqlite3
import os
from flask import Flask, request, jsonify, render_template_string

DB_PATH  = "dpp.db"
BASE_URL = "https://www.thestudioattheedgeoftheworld.com/uploads/4/7/4/0/47403357/"

app = Flask(__name__)


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_annotations_db():
    con = get_db()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS annotations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id      INTEGER NOT NULL,
            selected_text TEXT NOT NULL,
            comment       TEXT NOT NULL,
            author_name   TEXT NOT NULL DEFAULT 'Anonymous',
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS replies (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            annotation_id INTEGER NOT NULL,
            comment       TEXT NOT NULL,
            author_name   TEXT NOT NULL DEFAULT 'Anonymous',
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_annotations_paper ON annotations(paper_id);
        CREATE INDEX IF NOT EXISTS idx_replies_annotation ON replies(annotation_id);
    """)
    con.commit()
    con.close()


def stem_to_url(stem):
    return BASE_URL + stem + ".pdf"


def get_snippet(text, query_terms, context=40):
    text_lower = text.lower()
    best_pos = len(text)
    for term in query_terms:
        pos = text_lower.find(term.lower())
        if pos != -1 and pos < best_pos:
            best_pos = pos
    if best_pos == len(text):
        return " ".join(text.split()[:context * 2]) + "..."
    words = text.split()
    char_count = 0
    match_word = 0
    for i, word in enumerate(words):
        char_count += len(word) + 1
        if char_count >= best_pos:
            match_word = i
            break
    start = max(0, match_word - context)
    end   = min(len(words), match_word + context)
    snippet = " ".join(words[start:end])
    if start > 0: snippet = "..." + snippet
    if end < len(words): snippet = snippet + "..."
    return snippet


def count_mentions(term, full_text):
    return full_text.lower().count(term.lower())


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    con = get_db()
    paper_count = con.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    chunk_count = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    con.close()
    return render_template_string(HTML, paper_count=paper_count, chunk_count=chunk_count)


@app.route("/search", methods=["POST"])
def search():
    data  = request.get_json()
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "No query provided"})

    try:
        con = get_db()
        cur = con.cursor()

        # Best matching chunks via FTS
        cur.execute("""
            SELECT p.title, p.author, p.volume, p.theme, c.text, p.stem, p.id
            FROM chunks_fts
            JOIN chunks c ON chunks_fts.rowid = c.id
            JOIN papers p ON c.paper_id = p.id
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT 150
        """, (query,))
        rows = cur.fetchall()

        # Deduplicate by paper, keep best chunk
        seen = {}
        for row in rows:
            if row["title"] not in seen:
                seen[row["title"]] = row
        top = list(seen.values())[:25]

        terms = [t.strip('"') for t in query.split() if t not in ('AND', 'OR', 'NOT')]

        # Annotation counts for matched papers
        paper_ids = [row["id"] for row in top]
        annotation_counts = {}
        if paper_ids:
            placeholders = ','.join(['?'] * len(paper_ids))
            annot_rows = cur.execute(
                f"SELECT paper_id, COUNT(*) as cnt FROM annotations "
                f"WHERE paper_id IN ({placeholders}) GROUP BY paper_id",
                paper_ids
            ).fetchall()
            annotation_counts = {r["paper_id"]: r["cnt"] for r in annot_rows}

        results = []
        for row in top:
            cur.execute("""
                SELECT GROUP_CONCAT(text, ' ') as full_text
                FROM chunks WHERE paper_id = ?
            """, (row["id"],))
            full = cur.fetchone()["full_text"] or ""
            primary_term = terms[0] if terms else query
            mentions = count_mentions(primary_term, full)

            results.append({
                "paper_id":        row["id"],
                "title":           row["title"],
                "author":          row["author"],
                "volume":          row["volume"],
                "theme":           row["theme"],
                "snippet":         get_snippet(row["text"], terms),
                "pdf_url":         stem_to_url(row["stem"]),
                "count":           mentions,
                "annotation_count": annotation_counts.get(row["id"], 0),
            })

        con.close()
        return jsonify({"results": results})

    except Exception as e:
        return jsonify({"error": f"Search error: {str(e)} — try wrapping phrases in quotes"})


@app.route("/paper/<int:paper_id>/text")
def paper_text(paper_id):
    con = get_db()
    paper = con.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not paper:
        con.close()
        return jsonify({"error": "Paper not found"}), 404
    chunks = con.execute(
        "SELECT text FROM chunks WHERE paper_id = ? ORDER BY chunk_index",
        (paper_id,)
    ).fetchall()
    con.close()
    full_text = "\n\n".join(c["text"] for c in chunks)
    return jsonify({
        "id":     paper_id,
        "title":  paper["title"],
        "author": paper["author"],
        "text":   full_text,
    })


@app.route("/annotations/<int:paper_id>")
def get_annotations(paper_id):
    con = get_db()
    annotations = con.execute(
        "SELECT * FROM annotations WHERE paper_id = ? ORDER BY created_at",
        (paper_id,)
    ).fetchall()
    result = []
    for a in annotations:
        replies = con.execute(
            "SELECT * FROM replies WHERE annotation_id = ? ORDER BY created_at",
            (a["id"],)
        ).fetchall()
        result.append({
            "id":            a["id"],
            "selected_text": a["selected_text"],
            "comment":       a["comment"],
            "author_name":   a["author_name"],
            "created_at":    a["created_at"],
            "replies":       [dict(r) for r in replies],
        })
    con.close()
    return jsonify({"annotations": result})


@app.route("/annotations", methods=["POST"])
def create_annotation():
    data          = request.get_json()
    paper_id      = data.get("paper_id")
    selected_text = (data.get("selected_text") or "").strip()
    comment       = (data.get("comment") or "").strip()
    author_name   = (data.get("author_name") or "").strip() or "Anonymous"

    if not paper_id or not selected_text or not comment:
        return jsonify({"error": "Missing required fields"}), 400

    con = get_db()
    cur = con.execute(
        "INSERT INTO annotations (paper_id, selected_text, comment, author_name) VALUES (?, ?, ?, ?)",
        (paper_id, selected_text, comment, author_name)
    )
    ann_id = cur.lastrowid
    con.commit()
    ann = con.execute("SELECT * FROM annotations WHERE id = ?", (ann_id,)).fetchone()
    con.close()
    return jsonify({
        "id":            ann["id"],
        "selected_text": ann["selected_text"],
        "comment":       ann["comment"],
        "author_name":   ann["author_name"],
        "created_at":    ann["created_at"],
        "replies":       [],
    })


@app.route("/annotations/<int:annotation_id>/replies", methods=["POST"])
def create_reply(annotation_id):
    data        = request.get_json()
    comment     = (data.get("comment") or "").strip()
    author_name = (data.get("author_name") or "").strip() or "Anonymous"

    if not comment:
        return jsonify({"error": "Comment is required"}), 400

    con = get_db()
    exists = con.execute(
        "SELECT id FROM annotations WHERE id = ?", (annotation_id,)
    ).fetchone()
    if not exists:
        con.close()
        return jsonify({"error": "Annotation not found"}), 404

    cur = con.execute(
        "INSERT INTO replies (annotation_id, comment, author_name) VALUES (?, ?, ?)",
        (annotation_id, comment, author_name)
    )
    reply_id = cur.lastrowid
    con.commit()
    reply = con.execute("SELECT * FROM replies WHERE id = ?", (reply_id,)).fetchone()
    con.close()
    return jsonify(dict(reply))


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DPP Search</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  html, body {
    height: 100%;
    overflow: hidden;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    background: #f4f3ef;
    color: #1a1a1a;
  }

  /* ── Header ── */
  header {
    height: 52px;
    background: white;
    border-bottom: 0.5px solid rgba(0,0,0,0.1);
    padding: 0 2rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-shrink: 0;
    position: relative;
    z-index: 10;
  }
  header h1 { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; }
  header span { font-size: 13px; color: #aaa; }

  /* ── Layout ── */
  #app-layout {
    display: flex;
    height: calc(100vh - 52px);
  }

  /* ── Search pane ── */
  #search-pane {
    flex: 1;
    overflow-y: auto;
    padding: 2rem;
    transition: flex 0.35s ease, min-width 0.35s ease;
    min-width: 0;
  }

  .reader-open #search-pane {
    flex: 0 0 380px;
    min-width: 0;
  }

  .search-inner {
    max-width: 760px;
    margin: 0 auto;
  }
  .reader-open .search-inner { max-width: none; }

  /* ── Search card ── */
  .search-card {
    background: white;
    border-radius: 12px;
    border: 0.5px solid rgba(0,0,0,0.1);
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
  }

  .reader-open .hints { display: none; }

  .search-row { display: flex; gap: 10px; }

  #query {
    flex: 1;
    padding: 9px 14px;
    border: 0.5px solid rgba(0,0,0,0.2);
    border-radius: 8px;
    font-size: 15px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.15s;
  }
  #query:focus { border-color: rgba(0,0,0,0.5); }

  #searchBtn {
    padding: 9px 22px;
    background: #1a1a1a;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-family: inherit;
    cursor: pointer;
    transition: background 0.1s;
  }
  #searchBtn:hover { background: #333; }
  #searchBtn:disabled { opacity: 0.4; cursor: not-allowed; }

  .hints {
    margin-top: 9px;
    font-size: 12px;
    color: #bbb;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }
  .hints code {
    background: #f4f3ef;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 11px;
    color: #888;
  }

  #status { font-size: 13px; color: #888; margin-bottom: 1rem; min-height: 20px; }

  /* ── Result cards ── */
  .result {
    background: white;
    border-radius: 10px;
    border: 0.5px solid rgba(0,0,0,0.1);
    padding: 1rem 1.25rem;
    margin-bottom: 10px;
  }
  .result:hover { border-color: rgba(0,0,0,0.2); }
  .result.active { border-color: #1a1a1a; }

  .result-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 3px;
  }

  .result-title { font-size: 15px; font-weight: 600; line-height: 1.3; }

  .result-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .count-badge {
    font-size: 12px;
    font-weight: 500;
    padding: 3px 9px;
    border-radius: 20px;
    background: #f4f3ef;
    color: #666;
    white-space: nowrap;
  }
  .count-badge.has-mentions { background: #fff8e1; color: #a67c00; }

  .annot-badge {
    font-size: 11.5px;
    font-weight: 500;
    padding: 3px 9px;
    border-radius: 20px;
    background: #e8f4ff;
    color: #1565c0;
    white-space: nowrap;
  }

  .open-btn {
    padding: 4px 11px;
    border: 0.5px solid rgba(0,0,0,0.18);
    border-radius: 6px;
    background: white;
    font-size: 12px;
    color: #444;
    text-decoration: none;
    white-space: nowrap;
    transition: background 0.1s;
  }
  .open-btn:hover { background: #f4f3ef; }

  .read-btn {
    padding: 4px 13px;
    border: 0.5px solid rgba(0,0,0,0.18);
    border-radius: 6px;
    background: white;
    font-size: 12px;
    color: #444;
    cursor: pointer;
    white-space: nowrap;
    font-family: inherit;
    transition: background 0.1s, color 0.1s;
  }
  .read-btn:hover { background: #f4f3ef; }
  .read-btn.active { background: #1a1a1a; color: white; border-color: #1a1a1a; }

  .result-meta { font-size: 12px; color: #aaa; margin-bottom: 8px; }
  .result-meta .author { color: #666; font-weight: 500; }

  .snippet {
    font-size: 13px;
    color: #555;
    line-height: 1.65;
    background: #fafaf8;
    border-left: 3px solid #e8e5de;
    padding: 6px 10px;
    border-radius: 0 6px 6px 0;
  }
  .snippet mark { background: #fff3a3; color: inherit; border-radius: 2px; padding: 0 1px; }

  .no-results { text-align: center; color: #bbb; padding: 3rem 0; font-size: 14px; }

  /* ── Reader pane ── */
  #reader-pane {
    width: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: white;
    border-left: 0.5px solid rgba(0,0,0,0.1);
    transition: width 0.35s ease;
  }

  .reader-open #reader-pane {
    width: calc(100vw - 380px);
    flex-shrink: 0;
  }

  #reader-header {
    padding: 12px 20px;
    border-bottom: 0.5px solid rgba(0,0,0,0.1);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-shrink: 0;
    min-width: 0;
  }

  #reader-paper-info { min-width: 0; overflow: hidden; }
  #reader-title {
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  #reader-author { font-size: 12px; color: #888; margin-top: 1px; }

  #reader-header-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

  #annot-count-badge {
    font-size: 12px;
    background: #e8f4ff;
    color: #1565c0;
    padding: 3px 10px;
    border-radius: 20px;
    font-weight: 500;
    white-space: nowrap;
  }

  #close-reader-btn {
    width: 28px; height: 28px;
    border: 0.5px solid rgba(0,0,0,0.18);
    border-radius: 6px;
    background: white;
    font-size: 17px;
    color: #666;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: inherit;
    line-height: 1;
  }
  #close-reader-btn:hover { background: #f4f3ef; }

  #reader-body {
    flex: 1;
    display: flex;
    min-height: 0;
    overflow: hidden;
  }

  /* ── Paper text ── */
  #reader-text-wrap {
    flex: 1;
    overflow-y: auto;
    padding: 2.5rem 3rem;
    min-width: 0;
    border-right: 0.5px solid rgba(0,0,0,0.07);
  }

  #reader-text {
    max-width: 640px;
    font-size: 14.5px;
    line-height: 1.85;
    color: #1a1a1a;
    user-select: text;
    -webkit-user-select: text;
  }
  #reader-text p { margin-bottom: 1.3em; }

  .annotated-passage {
    background: rgba(249, 168, 37, 0.2);
    border-bottom: 1.5px solid rgba(249, 168, 37, 0.7);
    cursor: pointer;
    border-radius: 2px;
    transition: background 0.15s;
  }
  .annotated-passage:hover { background: rgba(249, 168, 37, 0.35); }
  .annotated-passage.focused { background: rgba(249, 168, 37, 0.45); }

  /* ── Annotations sidebar ── */
  #annotations-pane {
    width: 300px;
    flex-shrink: 0;
    overflow-y: auto;
    background: #fafaf8;
    display: flex;
    flex-direction: column;
  }

  #annotations-header {
    padding: 14px 16px 10px;
    border-bottom: 0.5px solid rgba(0,0,0,0.08);
    font-size: 11px;
    font-weight: 600;
    color: #999;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    flex-shrink: 0;
  }

  #annotations-list {
    flex: 1;
    padding: 10px 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .annot-empty {
    text-align: center;
    color: #bbb;
    font-size: 13px;
    padding: 2rem 1rem;
    line-height: 1.7;
  }

  .annotation-card {
    background: white;
    border: 0.5px solid rgba(0,0,0,0.1);
    border-radius: 8px;
    padding: 10px 12px;
    cursor: pointer;
    transition: border-color 0.15s;
  }
  .annotation-card:hover { border-color: rgba(0,0,0,0.22); }
  .annotation-card.active { border-color: #1565c0; }

  .annot-quote-block {
    font-size: 11.5px;
    color: #999;
    border-left: 2px solid rgba(249, 168, 37, 0.8);
    padding-left: 8px;
    margin-bottom: 8px;
    line-height: 1.5;
    font-style: italic;
  }

  .annot-author-name {
    font-size: 12px;
    font-weight: 600;
    color: #1a1a1a;
  }

  .annot-comment-text {
    font-size: 12.5px;
    color: #333;
    line-height: 1.55;
    margin-top: 3px;
  }

  .annot-timestamp { font-size: 11px; color: #bbb; margin-top: 5px; }

  .replies-section { margin-top: 8px; display: flex; flex-direction: column; gap: 5px; }

  .reply-item {
    background: #f4f3ef;
    border-radius: 6px;
    padding: 7px 10px;
  }
  .reply-author { font-size: 11.5px; font-weight: 600; color: #444; }
  .reply-text { font-size: 12px; color: #555; line-height: 1.5; display: block; margin-top: 2px; }
  .reply-time { font-size: 10.5px; color: #bbb; display: block; margin-top: 2px; }

  .reply-count-hint { font-size: 11px; color: #bbb; margin-top: 6px; }

  .reply-form {
    margin-top: 10px;
    border-top: 0.5px solid rgba(0,0,0,0.08);
    padding-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .reply-form input,
  .reply-form textarea {
    border: 0.5px solid rgba(0,0,0,0.2);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
    font-family: inherit;
    outline: none;
    resize: none;
    background: white;
  }
  .reply-form input:focus,
  .reply-form textarea:focus { border-color: rgba(0,0,0,0.45); }
  .reply-form textarea { min-height: 54px; }

  .reply-submit-btn {
    align-self: flex-end;
    padding: 5px 14px;
    background: #1a1a1a;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    font-family: inherit;
    cursor: pointer;
  }
  .reply-submit-btn:hover { background: #333; }

  /* ── Annotate popover ── */
  #annotate-popover {
    position: fixed;
    z-index: 1000;
    background: white;
    border: 0.5px solid rgba(0,0,0,0.15);
    border-radius: 10px;
    box-shadow: 0 8px 28px rgba(0,0,0,0.12);
    padding: 14px 16px;
    width: 320px;
  }

  #annot-pop-quote {
    font-size: 11.5px;
    color: #999;
    font-style: italic;
    border-left: 2px solid rgba(249, 168, 37, 0.8);
    padding-left: 8px;
    margin-bottom: 10px;
    line-height: 1.5;
  }

  #annotate-popover input,
  #annotate-popover textarea {
    width: 100%;
    border: 0.5px solid rgba(0,0,0,0.2);
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
    font-family: inherit;
    outline: none;
    resize: none;
    margin-bottom: 7px;
    background: white;
  }
  #annotate-popover input:focus,
  #annotate-popover textarea:focus { border-color: rgba(0,0,0,0.45); }
  #annot-comment-ta { min-height: 72px; }

  .popover-actions { display: flex; justify-content: flex-end; gap: 8px; }

  .popover-cancel-btn {
    padding: 6px 14px;
    border: 0.5px solid rgba(0,0,0,0.18);
    border-radius: 6px;
    background: white;
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
    color: #555;
  }
  .popover-cancel-btn:hover { background: #f4f3ef; }

  .popover-submit-btn {
    padding: 6px 16px;
    background: #1a1a1a;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
  }
  .popover-submit-btn:hover { background: #333; }
  .popover-submit-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ── Spinner ── */
  .spinner {
    display: inline-block;
    width: 13px; height: 13px;
    border: 2px solid rgba(0,0,0,0.1);
    border-top-color: #1a1a1a;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 5px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>

<header>
  <h1>Design Philosophy Papers</h1>
  <span>{{ paper_count }} papers · {{ chunk_count }} chunks</span>
</header>

<div id="app-layout">

  <!-- ── Left: search ── -->
  <div id="search-pane">
    <div class="search-inner">

      <div class="search-card">
        <div class="search-row">
          <input type="text" id="query" placeholder="Search the journal..." autocomplete="off" />
          <button id="searchBtn" onclick="doSearch()">Search</button>
        </div>
        <div class="hints">
          <span>Exact phrase: <code>"ontological designing"</code></span>
          <span>Either: <code>Heidegger OR Bataille</code></span>
          <span>Exclude: <code>technology NOT digital</code></span>
        </div>
      </div>

      <div id="status"></div>
      <div id="results"></div>

    </div>
  </div>

  <!-- ── Right: reader ── -->
  <div id="reader-pane">
    <div id="reader-header">
      <div id="reader-paper-info">
        <div id="reader-title"></div>
        <div id="reader-author"></div>
      </div>
      <div id="reader-header-actions">
        <span id="annot-count-badge"></span>
        <button id="close-reader-btn" onclick="closeReader()" title="Close reader">×</button>
      </div>
    </div>
    <div id="reader-body">
      <div id="reader-text-wrap">
        <div id="reader-text"></div>
      </div>
      <div id="annotations-pane">
        <div id="annotations-header">Notes</div>
        <div id="annotations-list"></div>
      </div>
    </div>
  </div>

</div>

<!-- ── Annotate popover ── -->
<div id="annotate-popover" style="display:none">
  <div id="annot-pop-quote"></div>
  <input type="text" id="annot-author-input" placeholder="Your name (optional)" />
  <textarea id="annot-comment-ta" placeholder="Write a note…"></textarea>
  <div class="popover-actions">
    <button class="popover-cancel-btn" onclick="hideAnnotatePopover()">Cancel</button>
    <button class="popover-submit-btn" id="annot-submit-btn" onclick="submitAnnotation()">Annotate</button>
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let currentPaperId    = null;
let currentAnnotations = [];
let activeAnnotationId = null;
let pendingSelectedText = '';
let activeReadBtn      = null;

// ── Utilities ──────────────────────────────────────────────────────────────
function esc(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escapeRe(s) { return s.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'); }

function highlightTerms(text, terms) {
  terms.forEach(term => {
    if (!term || term.length < 2) return;
    const re = new RegExp(escapeRe(term), 'gi');
    text = text.replace(re, m => `<mark>${m}</mark>`);
  });
  return text;
}

function formatDate(s) {
  try {
    return new Date(s.replace(' ', 'T') + 'Z')
      .toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return s; }
}

function getSavedName() { return localStorage.getItem('dpp_author') || ''; }
function saveName(n)    { if (n && n !== 'Anonymous') localStorage.setItem('dpp_author', n); }

// ── Search ─────────────────────────────────────────────────────────────────
document.getElementById('query').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});

function setStatus(html) { document.getElementById('status').innerHTML = html; }
function setResults(html) { document.getElementById('results').innerHTML = html; }

async function doSearch() {
  const q = document.getElementById('query').value.trim();
  if (!q) return;

  document.getElementById('searchBtn').disabled = true;
  setStatus('<span class="spinner"></span>Searching…');
  setResults('');

  try {
    const resp = await fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q })
    });
    const data = await resp.json();

    if (data.error) {
      setStatus(`<span style="color:#c62828">${data.error}</span>`);
      return;
    }
    if (!data.results || !data.results.length) {
      setStatus('');
      setResults('<div class="no-results">No results found.</div>');
      return;
    }

    const terms = q.split(/\\s+/)
      .map(t => t.replace(/^"|"$/g, ''))
      .filter(t => !['AND','OR','NOT'].includes(t) && t.length > 1);

    setStatus(`<strong>${data.results.length}</strong> paper${data.results.length !== 1 ? 's' : ''} found`);

    const html = data.results.map(r => {
      const snippetHtml = highlightTerms(r.snippet, terms);
      const badgeClass  = r.count > 0 ? 'count-badge has-mentions' : 'count-badge';
      const badgeLabel  = r.count === 1 ? '1 mention' : `${r.count} mentions`;
      const annotBadge  = r.annotation_count > 0
        ? `<span class="annot-badge">${r.annotation_count} note${r.annotation_count !== 1 ? 's' : ''}</span>` : '';
      const safeTitle  = r.title.replace(/&/g,'&amp;').replace(/"/g,'&quot;');
      const safeAuthor = r.author.replace(/&/g,'&amp;').replace(/"/g,'&quot;');

      return `<div class="result" id="result-${r.paper_id}">
        <div class="result-header">
          <div class="result-title">${r.title}</div>
          <div class="result-actions">
            <span class="${badgeClass}">${badgeLabel}</span>
            ${annotBadge}
            <button class="read-btn" id="read-btn-${r.paper_id}"
              data-pid="${r.paper_id}" data-title="${safeTitle}" data-author="${safeAuthor}"
              onclick="openReaderFromBtn(this)">Read</button>
            <a class="open-btn" href="${r.pdf_url}" target="_blank">PDF ↗</a>
          </div>
        </div>
        <div class="result-meta">
          <span class="author">${r.author}</span>
          &nbsp;·&nbsp; Vol ${r.volume} &nbsp;·&nbsp; ${r.theme}
        </div>
        <div class="snippet">${snippetHtml}</div>
      </div>`;
    }).join('');

    setResults(html);

  } catch(e) {
    setStatus(`<span style="color:#c62828">Error: ${e.message}</span>`);
  } finally {
    document.getElementById('searchBtn').disabled = false;
  }
}

// ── Reader ─────────────────────────────────────────────────────────────────
function openReaderFromBtn(btn) {
  openReader(parseInt(btn.dataset.pid), btn.dataset.title, btn.dataset.author, btn);
}

async function openReader(paperId, title, author, btn) {
  currentPaperId     = paperId;
  currentAnnotations = [];
  activeAnnotationId = null;

  if (activeReadBtn) activeReadBtn.classList.remove('active');
  activeReadBtn = btn;
  if (btn) btn.classList.add('active');

  document.querySelectorAll('.result').forEach(el => el.classList.remove('active'));
  const card = document.getElementById('result-' + paperId);
  if (card) card.classList.add('active');

  document.getElementById('reader-title').textContent  = title;
  document.getElementById('reader-author').textContent = author;
  document.getElementById('reader-text').innerHTML     = '<span class="spinner"></span> Loading…';
  document.getElementById('annotations-list').innerHTML = '';
  document.getElementById('annot-count-badge').textContent = '';
  document.getElementById('app-layout').classList.add('reader-open');
  hideAnnotatePopover();

  const resp = await fetch(`/paper/${paperId}/text`);
  const data = await resp.json();

  const paragraphs = data.text
    .split(/\\n{2,}/)
    .map(p => p.trim().replace(/\\n/g, ' '))
    .filter(p => p.length > 0)
    .map(p => `<p>${esc(p)}</p>`)
    .join('');
  document.getElementById('reader-text').innerHTML = paragraphs || '<p>No text available.</p>';

  await loadAnnotations(paperId);
}

function closeReader() {
  document.getElementById('app-layout').classList.remove('reader-open');
  document.querySelectorAll('.result').forEach(el => el.classList.remove('active'));
  if (activeReadBtn) { activeReadBtn.classList.remove('active'); activeReadBtn = null; }
  currentPaperId = null;
  hideAnnotatePopover();
}

// ── Load & render annotations ──────────────────────────────────────────────
async function loadAnnotations(paperId) {
  const resp = await fetch(`/annotations/${paperId}`);
  const data = await resp.json();
  currentAnnotations = data.annotations || [];
  updateCountBadge();
  applyHighlights();
  renderSidebar();
}

function updateCountBadge() {
  const badge = document.getElementById('annot-count-badge');
  const n = currentAnnotations.length;
  badge.textContent = n > 0 ? `${n} note${n !== 1 ? 's' : ''}` : '';
}

function applyHighlights() {
  const textEl = document.getElementById('reader-text');
  // Sort longest first so longer selections don't get broken by shorter subsets
  const sorted = [...currentAnnotations].sort((a, b) => b.selected_text.length - a.selected_text.length);
  for (const ann of sorted) {
    const escaped = esc(ann.selected_text);
    if (textEl.innerHTML.includes(escaped)) {
      textEl.innerHTML = textEl.innerHTML.replace(
        escaped,
        `<span class="annotated-passage" data-aid="${ann.id}" onclick="focusAnnotation(${ann.id})">${escaped}</span>`
      );
    }
  }
}

function renderSidebar() {
  const list = document.getElementById('annotations-list');
  if (!currentAnnotations.length) {
    list.innerHTML = '<div class="annot-empty">No notes yet.<br>Select text in the reader to annotate.</div>';
    return;
  }

  list.innerHTML = currentAnnotations.map(a => {
    const isActive    = a.id === activeAnnotationId;
    const quotePreview = a.selected_text.length > 110 ? a.selected_text.slice(0, 110) + '…' : a.selected_text;

    const repliesHtml = a.replies.map(r => `
      <div class="reply-item">
        <span class="reply-author">${esc(r.author_name)}</span>
        <span class="reply-text">${esc(r.comment)}</span>
        <span class="reply-time">${formatDate(r.created_at)}</span>
      </div>`).join('');

    const replyFormHtml = isActive ? `
      <div class="reply-form">
        <input type="text" id="ra-${a.id}" placeholder="Your name" value="${esc(getSavedName())}" />
        <textarea id="rt-${a.id}" placeholder="Reply…"
          onkeydown="if(event.key==='Enter'&&(event.ctrlKey||event.metaKey))submitReply(event,${a.id})"></textarea>
        <button class="reply-submit-btn" onclick="submitReply(event,${a.id})">Reply</button>
      </div>` : '';

    const replyHint = !isActive && a.replies.length > 0
      ? `<div class="reply-count-hint">${a.replies.length} repl${a.replies.length === 1 ? 'y' : 'ies'}</div>` : '';

    return `<div class="annotation-card${isActive ? ' active' : ''}" data-sid="${a.id}"
              onclick="setActiveAnnotation(event,${a.id})">
      <div class="annot-quote-block">${esc(quotePreview)}</div>
      <div class="annot-author-name">${esc(a.author_name)}</div>
      <div class="annot-comment-text">${esc(a.comment)}</div>
      <div class="annot-timestamp">${formatDate(a.created_at)}</div>
      <div class="replies-section">${repliesHtml}</div>
      ${replyFormHtml}
      ${replyHint}
    </div>`;
  }).join('');
}

function focusAnnotation(annotationId) {
  activeAnnotationId = annotationId;
  syncPassageFocus();
  renderSidebar();
  requestAnimationFrame(() => {
    const el = document.querySelector(`[data-sid="${annotationId}"]`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
}

function setActiveAnnotation(e, annotationId) {
  e.stopPropagation();
  activeAnnotationId = activeAnnotationId === annotationId ? null : annotationId;
  syncPassageFocus();
  renderSidebar();
}

function syncPassageFocus() {
  document.querySelectorAll('.annotated-passage').forEach(el => {
    el.classList.toggle('focused', parseInt(el.dataset.aid) === activeAnnotationId);
  });
}

// ── Text selection → popover ───────────────────────────────────────────────
document.addEventListener('mouseup', function(e) {
  if (document.getElementById('annotate-popover').contains(e.target)) return;
  if (!currentPaperId) return;

  const wrap = document.getElementById('reader-text-wrap');
  if (!wrap || !wrap.contains(e.target)) {
    hideAnnotatePopover();
    return;
  }

  setTimeout(() => {
    const sel  = window.getSelection();
    const text = sel ? sel.toString().trim() : '';
    if (text.length < 5) { hideAnnotatePopover(); return; }
    try {
      const rect = sel.getRangeAt(0).getBoundingClientRect();
      showAnnotatePopover(text, rect);
    } catch {}
  }, 10);
});

function showAnnotatePopover(text, rect) {
  pendingSelectedText = text;
  const preview = text.length > 130 ? text.slice(0, 130) + '…' : text;
  document.getElementById('annot-pop-quote').textContent    = preview;
  document.getElementById('annot-author-input').value       = getSavedName();
  document.getElementById('annot-comment-ta').value         = '';
  document.getElementById('annot-submit-btn').disabled      = false;

  const pop = document.getElementById('annotate-popover');
  pop.style.display = 'block';

  const popW = 320, popH = 210;
  let top  = rect.bottom + 8;
  let left = rect.left;
  if (top + popH > window.innerHeight - 12) top = rect.top - popH - 8;
  if (left + popW > window.innerWidth - 12) left = window.innerWidth - popW - 12;
  if (left < 8) left = 8;

  pop.style.top  = top + 'px';
  pop.style.left = left + 'px';
  document.getElementById('annot-comment-ta').focus();
}

document.getElementById('annot-comment-ta').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submitAnnotation();
});

function hideAnnotatePopover() {
  document.getElementById('annotate-popover').style.display = 'none';
  pendingSelectedText = '';
}

async function submitAnnotation() {
  const comment = document.getElementById('annot-comment-ta').value.trim();
  const author  = document.getElementById('annot-author-input').value.trim() || 'Anonymous';
  if (!comment || !pendingSelectedText || !currentPaperId) return;

  saveName(author);
  const btn = document.getElementById('annot-submit-btn');
  btn.disabled = true;

  try {
    const resp = await fetch('/annotations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        paper_id:      currentPaperId,
        selected_text: pendingSelectedText,
        comment,
        author_name:   author
      })
    });
    const ann = await resp.json();
    if (ann.error) { alert(ann.error); return; }

    currentAnnotations.push(ann);
    updateCountBadge();
    hideAnnotatePopover();

    // Highlight the new passage in reader text
    const textEl = document.getElementById('reader-text');
    const escaped = esc(ann.selected_text);
    if (textEl.innerHTML.includes(escaped)) {
      textEl.innerHTML = textEl.innerHTML.replace(
        escaped,
        `<span class="annotated-passage focused" data-aid="${ann.id}" onclick="focusAnnotation(${ann.id})">${escaped}</span>`
      );
    }

    activeAnnotationId = ann.id;
    renderSidebar();
    requestAnimationFrame(() => {
      const el = document.querySelector(`[data-sid="${ann.id}"]`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  } finally {
    btn.disabled = false;
  }
}

// ── Replies ────────────────────────────────────────────────────────────────
async function submitReply(e, annotationId) {
  e.stopPropagation();
  const comment = document.getElementById(`rt-${annotationId}`).value.trim();
  const author  = document.getElementById(`ra-${annotationId}`).value.trim() || 'Anonymous';
  if (!comment) return;

  saveName(author);

  const resp = await fetch(`/annotations/${annotationId}/replies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ comment, author_name: author })
  });
  const reply = await resp.json();
  if (reply.error) { alert(reply.error); return; }

  const ann = currentAnnotations.find(a => a.id === annotationId);
  if (ann) ann.replies.push(reply);
  renderSidebar();
}
</script>
</body>
</html>
"""


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run dpp_build_db.py first.")
    else:
        init_annotations_db()
        port = int(os.environ.get("PORT", 5000))
        print(f"DPP Search running at http://localhost:{port}")
        print("Press Ctrl+C to stop.")
        app.run(debug=False, host="0.0.0.0", port=port)
