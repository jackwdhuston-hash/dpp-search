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

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DPP Search</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    background: #f4f3ef;
    color: #1a1a1a;
    min-height: 100vh;
  }

  header {
    background: white;
    border-bottom: 0.5px solid rgba(0,0,0,0.1);
    padding: 1.25rem 2rem;
    display: flex;
    align-items: baseline;
    gap: 1rem;
  }
  header h1 { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; }
  header span { font-size: 13px; color: #aaa; }

  main { max-width: 800px; margin: 0 auto; padding: 2rem; }

  .search-card {
    background: white;
    border-radius: 12px;
    border: 0.5px solid rgba(0,0,0,0.1);
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
  }

  .search-row {
    display: flex;
    gap: 10px;
  }

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

  #status {
    font-size: 13px;
    color: #888;
    margin-bottom: 1rem;
    min-height: 20px;
  }

  .result {
    background: white;
    border-radius: 10px;
    border: 0.5px solid rgba(0,0,0,0.1);
    padding: 1rem 1.25rem;
    margin-bottom: 10px;
  }
  .result:hover { border-color: rgba(0,0,0,0.2); }

  .result-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 3px;
  }

  .result-title {
    font-size: 15px;
    font-weight: 600;
    line-height: 1.3;
  }

  .result-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
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
  .count-badge.has-mentions {
    background: #fff8e1;
    color: #a67c00;
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

  .result-meta {
    font-size: 12px;
    color: #aaa;
    margin-bottom: 8px;
  }
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
  .snippet mark {
    background: #fff3a3;
    color: inherit;
    border-radius: 2px;
    padding: 0 1px;
  }

  .no-results {
    text-align: center;
    color: #bbb;
    padding: 3rem 0;
    font-size: 14px;
  }

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

<main>
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
</main>

<script>
document.getElementById('query').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});

function setStatus(html) { document.getElementById('status').innerHTML = html; }
function setResults(html) { document.getElementById('results').innerHTML = html; }

function escapeRe(s) { return s.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'); }

function highlightText(text, terms) {
  terms.forEach(term => {
    if (!term || term.length < 2) return;
    const re = new RegExp(escapeRe(term), 'gi');
    text = text.replace(re, m => `<mark>${m}</mark>`);
  });
  return text;
}

async function doSearch() {
  const q = document.getElementById('query').value.trim();
  if (!q) return;

  document.getElementById('searchBtn').disabled = true;
  setStatus('<span class="spinner"></span>Searching...');
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

    if (!data.results || data.results.length === 0) {
      setStatus('');
      setResults('<div class="no-results">No results found.</div>');
      return;
    }

    const terms = q.split(/\\s+/)
      .map(t => t.replace(/^"|"$/g, ''))
      .filter(t => !['AND','OR','NOT'].includes(t) && t.length > 1);

    setStatus(`<strong>${data.results.length}</strong> paper${data.results.length !== 1 ? 's' : ''} found`);

    const html = data.results.map(r => {
      const snippetHtml = highlightText(r.snippet, terms);
      const badgeClass  = r.count > 0 ? 'count-badge has-mentions' : 'count-badge';
      const badgeLabel  = r.count === 1 ? '1 mention' : `${r.count} mentions`;

      return `<div class="result">
        <div class="result-header">
          <div class="result-title">${r.title}</div>
          <div class="result-actions">
            <span class="${badgeClass}">${badgeLabel}</span>
            <a class="open-btn" href="${r.pdf_url}" target="_blank">Open PDF ↗</a>
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
</script>
</body>
</html>
"""


def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


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

        # Get best matching chunks via FTS
        cur.execute("""
            SELECT p.title, p.author, p.volume, p.theme, c.text, p.stem, p.id
            FROM chunks_fts
            JOIN chunks c ON chunks_fts.rowid = c.id
            JOIN papers p ON c.paper_id = p.id
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT 60
        """, (query,))
        rows = cur.fetchall()

        # Deduplicate by paper, keep best chunk
        seen = {}
        for row in rows:
            title = row["title"]
            if title not in seen:
                seen[title] = row

        top = list(seen.values())[:10]

        # For each matched paper, count total mentions across all chunks
        terms = [t.strip('"') for t in query.split() if t not in ('AND','OR','NOT')]
        results = []

        for row in top:
            # Get full text of this paper
            cur.execute("""
                SELECT GROUP_CONCAT(text, ' ') as full_text
                FROM chunks WHERE paper_id = ?
            """, (row["id"],))
            full = cur.fetchone()["full_text"] or ""

            # Count mentions of each term, use the first/primary term
            primary_term = terms[0] if terms else query
            mentions = count_mentions(primary_term, full)

            results.append({
                "title":   row["title"],
                "author":  row["author"],
                "volume":  row["volume"],
                "theme":   row["theme"],
                "snippet": get_snippet(row["text"], terms),
                "pdf_url": stem_to_url(row["stem"]),
                "count":   mentions,
            })

        con.close()
        return jsonify({"results": results})

    except Exception as e:
        return jsonify({"error": f"Search error: {str(e)} — try wrapping phrases in quotes"})


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run dpp_build_db.py first.")
    else:
        print("DPP Search running at http://localhost:5000")
        print("Press Ctrl+C to stop.")
       port = int(os.environ.get("PORT", 5000))
app.run(debug=False, host="0.0.0.0", port=port)
```

Save the file, then run:
```
git add dpp_web.py requirements.txt Procfile
git commit -m "add railway config"
git push
