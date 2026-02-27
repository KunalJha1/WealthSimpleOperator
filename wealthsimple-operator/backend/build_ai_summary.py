from __future__ import annotations

import json
import os
import random
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from scripts.utils import now_utc
from build_symbol_snapshot import load_enabled_symbols
from pull_and_generate_price_ibkr import DB_PATH_OVERALL, TICKERS_PATH
from scripts.utils import parse_json_safely, ny_asof_date_str
from db_utils import get_db_connection, commit_with_retry
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)
MAX_WORKERS = 3

DB_PATH = Path(DB_PATH_OVERALL)
TICKERS_PATH = Path(TICKERS_PATH)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LOOKBACK_HOURS = 24
MIN_CONFIDENCE = 0.72
MAX_ARTICLES_PER_SYMBOL = 8
MODEL_ARTICLE = "gemini-2.5-flash-lite"
MODEL_ROLLUP = "gemini-2.5-flash-lite"
BATCH_SIZE = 5
BATCH_MAX_TEXT_CHARS = 1500
NY_TZ = ZoneInfo("America/New_York")
MAX_HOLDINGS_FOR_ROLLUP = 6
MAX_ITEMS_FOR_ROLLUP = 14
ETF_HOLDINGS_JSON_PATH = (Path(__file__).resolve().parent / "data" / "etfs.json")


UPSERT_AI_SUMMARY_SQL = """
INSERT INTO article_ai_summary (
article_id, symbol, model_name, input_source,
article_summary, key_points_json, is_relevant, created_at_utc
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(article_id) DO UPDATE SET
is_relevant=excluded.is_relevant,
article_summary=excluded.article_summary,
key_points_json=excluded.key_points_json,
created_at_utc=excluded.created_at_utc
"""

UPSERT_DAILY_SNAPSHOT_SQL = """
INSERT INTO symbol_daily_snapshot (symbol, asof_date, updated_at_utc, daily_summary)
VALUES (?, ?, ?, ?)
ON CONFLICT(symbol, asof_date) DO UPDATE SET
daily_summary=excluded.daily_summary,
updated_at_utc=excluded.updated_at_utc
"""

UPDATE_NLP_SENTIMENT_SQL = """
UPDATE article_nlp SET
sentiment_score=?,
sentiment_label=?,
model_name=?,
classified_at_utc=?
WHERE article_id=?
"""

@dataclass
class CandidateArticle:
    article_id: str
    symbol: str
    headline: str
    finnhub_summary: str
    url: str
    source: str
    published_at_utc: int
    confidence: float
    sentiment_score_0_100: int
    extracted_text: str
    extracted_status: str


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def generate_with_retry(call_fn, max_retries=8):
    delay = 8.0
    for _attempt in range(max_retries):
        try:
            return call_fn()
        except genai_errors.ClientError as e:
            msg = str(e)
            print(msg)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                print(f"   [AI] Rate limited. Retrying in {delay:.1f}s...")
                time.sleep(delay + random.random())
                delay = min(delay * 2, 20)
                continue
            raise

def fetch_candidate_articles(cur, symbol, limit):
    cur.execute(
        """
    SELECT
        n.id AS article_id,
        n.symbol AS symbol,
        COALESCE(n.headline,'') AS headline,
        COALESCE(n.summary,'') AS finnhub_summary,
        COALESCE(n.url,'') AS url,
        COALESCE(n.source,'') AS source,
        COALESCE(n.published_at_utc,0) AS published_at_utc,

        COALESCE(a.confidence,0.0) AS confidence,
        COALESCE(a.sentiment_score,50) AS sentiment_score,

        COALESCE(c.content_excerpt,'') AS extracted_text,
        COALESCE(c.status,'') AS extracted_status

    FROM news_articles n
    JOIN article_nlp a ON a.article_id = n.id
    LEFT JOIN article_content c ON c.article_id = n.id
    LEFT JOIN article_ai_summary s ON s.article_id = n.id
    WHERE n.symbol = ?
        AND a.confidence >= ?
        AND s.article_id IS NULL
    ORDER BY n.published_at_utc DESC
    LIMIT ?
    """,
        (symbol, float(MIN_CONFIDENCE), int(limit)),
    )

    rows = cur.fetchall()
    if not rows:
        return []

    cols = [d[0] for d in cur.description]
    out: List[CandidateArticle] = []
    for r in rows:
        d = dict(zip(cols, r))
        out.append(
            CandidateArticle(
                article_id=str(d["article_id"]),
                symbol=str(d["symbol"]),
                headline=str(d["headline"] or ""),
                finnhub_summary=str(d["finnhub_summary"] or ""),
                url=str(d["url"] or ""),
                source=str(d["source"] or ""),
                published_at_utc=int(d["published_at_utc"] or 0),
                confidence=float(d["confidence"] or 0.0),
                sentiment_score_0_100=int(round(float(d["sentiment_score"] or 50))),
                extracted_text=str(d["extracted_text"] or ""),
                extracted_status=str(d["extracted_status"] or ""),
            )
        )
    return out


def _strip_code_fences(text):
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def _truncate(s, max_chars):
    s = s or ""
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "…"


def build_article_input(a):
    if a.extracted_status == "ok" and a.extracted_text:
        return {
            "input_source": "summary+article_text",
            "text": (
                f"HEADLINE: {a.headline}\n"
                f"SOURCE: {a.source}\n"
                f"URL: {a.url}\n\n"
                f"FINNHUB SUMMARY:\n{a.finnhub_summary}\n\n"
                f"ARTICLE TEXT (supporting details):\n{a.extracted_text}"
            ),
        }

    return {
        "input_source": "finnhub_summary_only",
        "text": (
            f"HEADLINE: {a.headline}\n"
            f"SOURCE: {a.source}\n"
            f"URL: {a.url}\n\n"
            f"FINNHUB SUMMARY:\n{a.finnhub_summary}"
        ),
    }


def summarize_articles_batch(client, symbol, cands, max_items,):
    if not cands:
        return {}

    batch = []
    for a in cands[:max_items]:
        payload = build_article_input(a)
        batch.append(
            {
                "article_id": a.article_id,
                "symbol": a.symbol,
                "headline": _truncate(a.headline, 220),
                "source": _truncate(a.source, 60),
                "url": _truncate(a.url, 300),
                "input_source": payload["input_source"],
                "text": _truncate(payload["text"], BATCH_MAX_TEXT_CHARS),
                "sentiment_score": a.sentiment_score_0_100,
            }
        )

    prompt = f"""
    You are writing trader-facing briefs for {symbol}. Return ONLY valid JSON (no markdown, no code fences).

    Each input article includes a "sentiment_score" (0-100), where:
    - 0-35: Very Negative
    - 35-45: Somewhat Negative
    - 45-55: Neutral
    - 55-65: Somewhat Positive
    - 65-100: Very Positive

    Schema:
    [
    {{
        "article_id": "string",
        "is_relevant": true | false,
        "sentiment_score": 0-100,
        "article_summary": "3-6 sentence summary, factual, no hype, trader-facing (what changed, why it matters, what to watch)",
        "key_points": ["bullet 1", "bullet 2", "bullet 3"],
        "watchlist": ["watch item 1", "watch item 2"]
    }},
    ...
    ]

    - STRICT RELEVANCE GATE (NON-NEGOTIABLE):
      * Set is_relevant=true ONLY if the provided text clearly references {symbol} directly (ticker appears as a standalone token) OR the article is unmistakably about {symbol}.
      * If the article_summary says or implies "doesn't mention {symbol}", "not about {symbol}", "no mention", "unrelated", or similar, you MUST set is_relevant=false.
      * If the article is mainly about sector/macro/competitors and {symbol} is not explicitly mentioned in the provided text, set is_relevant=false.
      * Do not guess relevance from vibes; require explicit evidence in the text.
      
    Rules:
    - You MUST return exactly one object per input item (same count).
    - article_id must match the input article_id.
    - sentiment_score: Examine the text provided. If the input "sentiment_score" roughly aligns with the content's sentiment towards {symbol}, return the input score. If it is significantly misaligned (e.g., missed the main point or direction by a drastic notion), return a new refined score (0-100) pick non-round numbers.
    - key_points must be exactly 3 short, concrete items (strings). Don't mention "the X article discusses"—just provide a direct summary.
    - watchlist must be exactly 2 short, concrete forward-looking items (strings), focused on what a trader should monitor next (e.g., guidance, catalysts, risks, data points, upcoming events).
    - The summary must support the sentiment of the article. Do not mention that the stock went up or down X%; instead focus on drivers, implications, and decision-relevant details.
    - Mark is_relevant=false when you are confident the article is not about {symbol}.
    - Mark is_relevant=false if the article reference Yahoo Finance video.
    - If is_relevant=false: keep article_summary to 1 sentence max, keep key_points generic and short, watchlist should still be present with 2 items (e.g., "No actionable catalyst identified", "Await relevant {symbol} coverage").
    - No emojis. No extra keys.
    - Vary sentence openings and structure across articles (avoid repeating patterns like “The company…” or “The article…”), the more variety the better.
    - Rotate analytical framing styles (e.g., fundamental impact, positioning implications, risk framing, balance sheet angle, competitive dynamics, regulatory angle).
    - Use varied verbs (e.g., signals, suggests, reinforces, pressures, complicates, supports, constrains, accelerates, moderates).
    - Avoid repeating identical phrasing across summaries within the same batch.
    - Maintain precision and trader tone, but diversify expression.

    """


    if symbol in ("ECONOMY", "TRUMP"):
        prompt = f"""
    You are writing institutional-grade, high-impact macro-economic brief about {symbol}.
    Your audience is professional investors, economists, and policy analysts.
    Return ONLY valid JSON. No markdown. No code fences. No commentary outside JSON.

    Each input article includes:
    - article_id
    - sentiment_score (0–100, raw input score)

    You must evaluate relevance and rewrite the sentiment_score if needed based on macro impact.

    Output schema (STRICT):
    [
    {{
        "article_id": "string",
        "is_relevant": true | false,
        "sentiment_score": 0-100,
        "article_summary": "10–16 sentences, analytical, focused on transmission + second-order effects",
        "key_points": ["bullet 1", "bullet 2", "bullet 3"]
    }}
    ]

    RELEVANCE SCREENING (CRITICAL):
    - Mark is_relevant=true ONLY if the article discusses macro factors that affect growth, inflation, policy, markets, or geopolitical risk inside of US markets.
    - Mark is_relevant=false if:
      • The article is purely firm-specific (e.g., "Apple beats on iPhone sales") with no macro spillover.
      • The article is a fluff piece, low-quality video recap, celebrity gossip, or non-analytical content.
      • The article references Yahoo Finance video or similar low-quality sources.
    - Mark is_relevant=true even if the article is speculative, controversial, or preliminary—as long as it discusses policy, political risk, or macro drivers.
    - If is_relevant=false: keep article_summary to 1–2 sentences (explicitly state why irrelevant), keep key_points generic (3 items), mention awaiting relevant coverage.

    GENERAL RULES (ALL ARTICLES):
    - Focus on second-order effects, not headlines.
    - Explain the transmission mechanism (policy/markets → financial conditions → real economy/inflation) where applicable.
    - Separate signal vs noise: call out what is confirmed vs speculative.
    - Ignore firm-specific earnings, stock moves, or single-company news unless it clearly propagates to the macro level.
    - Do NOT summarize mechanically. Interpret it with investor relevance.
    - sentiment_score should reflect the net impact on:
    - economic stability
    - growth outlook
    - inflation trajectory
    - policy uncertainty
    - geopolitical risk
    - Lower scores = negative macro impact, higher scores = positive macro impact.
    - Avoid vague language: specify which variable is pressured (growth, inflation, term premium, risk appetite, etc.) and why.
    - Vary sentence openings and structure across articles (avoid repeating patterns like “The article…”).
    - Rotate analytical framing styles (e.g., fundamental impact, positioning implications, risk framing, balance sheet angle, competitive dynamics, regulatory angle).
    - Use varied verbs (e.g., signals, suggests, reinforces, pressures, complicates, supports, constrains, accelerates, moderates).
    - Avoid repeating identical phrasing across summaries within the same batch.
    - Maintain precision and trader tone, but diversify expression.

    --------------------------------
    ECONOMY-SPECIFIC INSTRUCTIONS:
    --------------------------------
    You are an expert macroeconomic analyst ("economic wonk" level).


    FOCUS EXCLUSIVELY ON:
    - Macro indicators: inflation (CPI, PCE, core vs headline), labor markets, wages, GDP, productivity
    - Central bank policy: Fed communication, rates, balance sheet (QT/QE), dot plots, forward guidance
    - Fiscal policy: deficits, debt, Treasury issuance, shutdown risk
    - Trade and geopolitics: tariffs, sanctions, global supply chains
    - Financial conditions: yields, curve shape, dollar strength, credit spreads, risk-on/off dynamics

    STRICTLY AVOID:
    - Individual companies
    - Sector earnings unless they clearly alter inflation, employment, or financial conditions
    - Equity-market micro commentary

    WHEN WRITING THE SUMMARY:
    - Explain *why* the data/event matters for the Fed reaction function and the growth/inflation mix
    - Describe transmission mechanisms (rates → demand → inflation, labor slack → wages, etc.)
    - Highlight whether the development shifts the medium-term macro trajectory (not just the next print)
    - Identify what would falsify the takeaway (e.g., next CPI, revisions, employment re-acceleration)
    - Use technical but clear language suitable for professionals

    KEY POINTS SHOULD:
    - Capture causal drivers
    - Reference macro linkages (policy reaction function, growth/inflation tradeoffs, term premium, financial conditions)
    - Be concise and analytical, not descriptive

    --------------------------------
    TRUMP-SPECIFIC INSTRUCTIONS:
    --------------------------------
    You are covering the Trump administration as a macro-political risk and policy driver.

    FOCUS ON:
    - Actions taken THAT DAY or announced imminently
    - Executive orders, policy directives, public statements with policy implications
    - Personnel changes (appointments, removals, resignations)
    - Trade actions, tariff threats, sanctions, diplomacy
    - Fiscal, regulatory, immigration, and national security decisions
    - Large news of global significance

    IMPORTANT:
    - Include the article even if the action is controversial, preliminary, or rhetorical
    - Interpret intent and likely follow-through
    - Assess policy credibility, constraints, and institutional friction

    WHEN WRITING THE SUMMARY:
    - Describe WHAT is being done or signaled, with clarity on status (proposed vs enacted)
    - Explain HOW it affects:
    - markets (risk premium, rates, dollar, commodities, vol)
    - trade relations (tariff pass-through, retaliation risk)
    - domestic political stability (shutdown risk, legal constraints, legislative friction)
    - global geopolitical balance (alliances, escalation, sanctions)
    - Explicitly connect actions to economic and policy uncertainty
    - Identify plausible next steps over the next 1–4 weeks

    KEY POINTS SHOULD:
    - Identify the concrete action
    - State immediate and downstream implications
    - Highlight risks, escalation paths, or policy reversals

    --------------------------------
    FINAL CHECKS:
    - JSON only
    - No emojis
    - No extra keys
    - Be analytical, not journalistic
    """


    payload = f"{prompt.strip()}\n{json.dumps(batch, ensure_ascii=False)}"
    resp = generate_with_retry(
        lambda: client.models.generate_content(
            model=MODEL_ARTICLE,
            contents=[payload],
            config=types.GenerateContentConfig(temperature=0.3, top_p=0.9),
        )
    )
    if resp is None:
        return {}

    raw = _strip_code_fences((resp.text or "").strip())
    data = parse_json_safely(raw)
    if not isinstance(data, list):
        return {}

    out_map: Dict[str, Dict[str, Any]] = {}
    for obj in data:
        if not isinstance(obj, dict):
            continue
        aid = str(obj.get("article_id", "")).strip()
        if not aid:
            continue

        article_summary = str(obj.get("article_summary", "")).strip()
        key_points = obj.get("key_points", [])
        if not article_summary or not isinstance(key_points, list):
            continue

        key_points = [str(x).strip() for x in key_points if str(x).strip()]
        if len(key_points) != 3:
            key_points = (key_points + [""] * 3)[:3]
            key_points = [kp for kp in key_points if kp][:3]
            if len(key_points) < 3:
                continue

        is_relevant = bool(obj.get("is_relevant", False))
        refined_sentiment = obj.get("sentiment_score")

        input_source = "finnhub_summary_only"
        original_sentiment = None
        for b in batch:
            if b["article_id"] == aid:
                input_source = b.get("input_source") or input_source
                original_sentiment = b.get("sentiment_score")
                break

        if refined_sentiment is None:
            refined_sentiment = original_sentiment

        out_map[aid] = {
            "is_relevant": is_relevant,
            "input_source": input_source,
            "article_summary": article_summary,
            "key_points": key_points,
            "sentiment_score": refined_sentiment,
            "original_sentiment": original_sentiment,
        }

    return out_map

def upsert_article_ai_summary(cur: sqlite3.Cursor, a: CandidateArticle, model_name: str, out: Dict[str, Any]) -> None:
    cur.execute(
        UPSERT_AI_SUMMARY_SQL,
        (
            a.article_id,
            a.symbol,
            model_name,
            out["input_source"],
            out["article_summary"],
            json.dumps(out["key_points"]),
            1 if out["is_relevant"] else 0,
            now_utc(),
        ),
    )

def _format_summary_rows(cur: sqlite3.Cursor, rows: List[tuple]) -> List[Dict[str, Any]]:
    if not rows:
        return []

    cols = [d[0] for d in cur.description]
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(zip(cols, r))
        try:
            kp = json.loads(d.get("key_points_json") or "[]")
        except Exception:
            kp = []
        out.append(
            {
                "symbol": str(d.get("symbol") or "").upper().strip(),
                "headline": str(d["headline"]),
                "source": str(d["source"]),
                "published_at_utc": int(d["published_at_utc"] or 0),
                "sentiment_score": int(round(float(d["sentiment_score"] or 50))),
                "confidence": float(d["confidence"] or 0.0),
                "article_summary": str(d["article_summary"] or ""),
                "key_points": [str(x) for x in kp if x],
            }
        )
    return out


def fetch_today_article_summaries(cur: sqlite3.Cursor, symbol: str, since_utc: int, limit: int = 40) -> List[Dict[str, Any]]:
    rows = _execute_summary_query(cur, symbol, since_utc, limit, include_time_filter=True)
    result = _format_summary_rows(cur, rows)
    if result:
        return result
    rows = _execute_summary_query(cur, symbol, since_utc, limit, include_time_filter=False)
    return _format_summary_rows(cur, rows)


def _execute_summary_query(cur, symbol, since_utc, limit, include_time_filter: bool):
    time_clause = "          AND n.published_at_utc >= ?\n" if include_time_filter else ""
    query = f"""
        SELECT
            n.id,
            n.symbol,
            n.headline,
            n.source,
            n.published_at_utc,
            a.sentiment_score,
            a.confidence,
            COALESCE(s.article_summary, '') AS article_summary,
            COALESCE(s.key_points_json, '[]') AS key_points_json,
            COALESCE(s.is_relevant, 1) AS is_relevant
        FROM news_articles n
        JOIN article_nlp a ON a.article_id = n.id
        JOIN article_ai_summary s ON s.article_id = n.id
        WHERE n.symbol = ?
{time_clause}          AND a.confidence >= ?
          AND COALESCE(s.is_relevant, 1) = 1
        ORDER BY n.published_at_utc DESC
        LIMIT ?
    """
    params = [symbol]
    if include_time_filter:
        params.append(int(since_utc))
    params.extend([float(MIN_CONFIDENCE), int(limit)])
    cur.execute(query, tuple(params))
    return cur.fetchall()


def fetch_today_article_summaries_multi(
    cur: sqlite3.Cursor,
    symbols: List[str],
    since_utc: int,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    syms = [s.upper().strip() for s in (symbols or []) if (s or "").strip()]
    if not syms:
        return []

    rows = _execute_summary_multi_query(cur, syms, since_utc, limit, include_time_filter=True)
    result = _format_summary_rows(cur, rows)
    if result:
        return result
    rows = _execute_summary_multi_query(cur, syms, since_utc, limit, include_time_filter=False)
    return _format_summary_rows(cur, rows)


def _execute_summary_multi_query(cur, symbols, since_utc, limit, include_time_filter: bool):
    placeholders = ",".join(["?"] * len(symbols))
    time_clause = "          AND n.published_at_utc >= ?\n" if include_time_filter else ""
    query = f"""
        SELECT
            n.id,
            n.symbol,
            n.headline,
            n.source,
            n.published_at_utc,
            a.sentiment_score,
            a.confidence,
            COALESCE(s.article_summary, '') AS article_summary,
            COALESCE(s.key_points_json, '[]') AS key_points_json,
            COALESCE(s.is_relevant, 1) AS is_relevant
        FROM news_articles n
        JOIN article_nlp a ON a.article_id = n.id
        JOIN article_ai_summary s ON s.article_id = n.id
        WHERE UPPER(n.symbol) IN ({placeholders})
{time_clause}          AND a.confidence >= ?
          AND COALESCE(s.is_relevant, 1) = 1
        ORDER BY n.published_at_utc DESC
        LIMIT ?
        """
    params = [*symbols]
    if include_time_filter:
        params.append(int(since_utc))
    params.extend([float(MIN_CONFIDENCE), int(limit)])
    cur.execute(query, tuple(params))
    return cur.fetchall()


def build_daily_rollup(client: genai.Client, symbol: str, items: List[Dict[str, Any]]) -> Optional[str]:
    now_ts = now_utc()
    compact = []
    for it in items[:20]:
        pub_ts = it.get("published_at_utc") or 0
        age_h = round((now_ts - pub_ts) / 3600.0, 1) if pub_ts else 999
        compact.append(
            {
                "headline": it["headline"],
                "summary": it["article_summary"],
                "key_points": it["key_points"][:3],
                "sentiment": it["sentiment_score"],
                "hours_ago": age_h,
            }
        )

    prompt = f"""
    You are writing the "What's happening today and why?" section for {symbol}.
    Input articles are provided in a JSON list, ordered from newest to oldest.

    Hard rules:
    1. Use ONLY the provided article summaries/key points (do not invent facts).
    2. PRIORITIZE RECENT DEVELOPMENTS. Articles with the lowest "hours_ago" must dominate the first half of the briefing.
    3. Write 8–10 sentences total. Trader-facing, concise, but more complete than a headline recap.
    4. If articles conflict, explicitly flag uncertainty (do not choose a side).
    5. No bullets. No mention of how much the stock price moved.
    6. Start with the most recent critical development, then connect to older context only if it improves interpretation.

    Content rules:
    7. Your job is to answer: (a) what changed, (b) why it matters for the next 1–10 trading days, (c) what to watch next.
    8. Use cause → market implication → watch item phrasing (but still as normal sentences, not bullets).
    9. Avoid filler. Every sentence must add incremental information.

    ETF rule (only if {symbol} is an ETF):
    10. Do NOT describe the ETF like a single company. Explain the sector/industry exposure and how the developments map to that basket.
    11. Be more thorough for ETFs: 10–12 sentences, and include at least 2 sentences about second-order sector implications (inputs, demand, regulation, rates, or macro sensitivity).
    """

    if symbol in ("ECONOMY", "TRUMP"):
        prompt = f"""
    You are writing the "Macro Briefing" summary for the {symbol} category.
    Input articles cover economic data, policy shifts, and political risk.

    Hard rules:
    1. Use ONLY the provided summaries/key points (do not invent facts).
    2. Write 18–24 sentences total. Comprehensive, analytical, and institutional-grade. This is a DEEP briefing for serious macro/policy watchers.
    3. No bullets. No talk of stock prices. No mechanical article-by-article recap.
    4. Lead with the most recent and most market-moving development, then integrate older context and build a compelling, layered narrative.

    Synthesis rules (ALL):
    5. Build one comprehensive narrative: what changed, why it matters, what it implies for the next few weeks, second-order effects, and what would change the view.
    6. If inputs conflict, explicitly state the uncertainty and identify the variable that resolves it (next data print, vote, court decision, agency guidance, etc.).
    7. Always include:
    - 2–3 sentences on market transmission (rates/credit/$/risk appetite → real economy or risk premium) with specific channels explained
    - 2–3 sentences on "what to watch next" with concrete milestones, timelines, and triggers (still written as normal sentences, not bullets)
    8. Include at least 1 paragraph (3–4 sentences) on longer-term implications (weeks to months out)

    TRUMP-specific:
    9. Synthesize the administration's latest policy posture and credibility with detail (proposed vs enacted, likelihood of execution, institutional constraints).
    10. Extensively connect policy direction to trade, fiscal, regulation, immigration, national security, and institutional friction. Explain how each domain affects markets.
    11. Highlight likely near-term AND medium-term market channels: tariffs → inflation pass-through → Fed reaction, uncertainty → risk premium shifts, geopolitical risk → commodities/defense, etc.
    12. Assess political viability and escalation risk. Will the policy survive court challenges, congressional friction, or congressional votes?

    ECONOMY-specific:
    13. Act as an expert economic wonk with deep macro knowledge. Focus on inflation composition (goods vs services, core vs headline), labor slack vs wages, growth momentum, and the central bank reaction function.
    14. Be specific and layered about implications: inflation trajectory (next 6 months vs 1-2 year horizon), growth outlook (near-term vs medium-term), policy path (next FOMC meeting vs next 2 quarters), and financial conditions (yields, spreads, dollar).
    15. Explain the causal chains explicitly: if inflation data is X, then the Fed reaction is Y (more dovish/hawkish), which means Z for growth and risk premiums. Avoid vague terms ("strong," "weak") unless tied to a mechanism.
    16. Include at least 1 sentence identifying the key data release or event that would falsify or confirm the narrative (e.g., "If next month's CPI shows energy/food normalizing, the disinflationary trajectory strengthens").
    """


    payload = f"{prompt.strip()}\n{json.dumps(compact, ensure_ascii=False)}"
    resp = generate_with_retry(
        lambda: client.models.generate_content(
            model=MODEL_ROLLUP,
            contents=[payload],
            config=types.GenerateContentConfig(temperature=0.3, top_p=0.9),
        )
    )
    if resp is None:
        return None

    return ((resp.text or "").strip()) or None


def build_etf_daily_rollup(client: genai.Client, etf_symbol: str, items: List[Dict[str, Any]]) -> Optional[str]:
    if not items:
        return None

    now_ts = now_utc()
    compact = []
    for it in items[:MAX_ITEMS_FOR_ROLLUP]:
        pub_ts = it.get("published_at_utc") or 0
        age_h = round((now_ts - pub_ts) / 3600.0, 1) if pub_ts else 999
        compact.append(
            {
                "symbol": it.get("symbol") or "",
                "headline": it.get("headline") or "",
                "summary": it.get("article_summary") or "",
                "key_points": (it.get("key_points") or [])[:3],
                "sentiment": it.get("sentiment_score"),
                "hours_ago": age_h,
            }
        )

    prompt = f"""
    You are writing the "What's happening today and why?" section for the ETF {etf_symbol}.
    Input articles cover the ETF and its holdings, ordered newest to oldest.

    Hard rules:
    1. Use ONLY the provided summaries/key points (do not invent facts).
    2. PRIORITIZE RECENT DEVELOPMENTS. The newest articles (lowest "hours_ago") must drive the first half of the narrative.
    3. Write 9–12 sentences total. Trader-facing, concise but layered.
    4. Mention {etf_symbol} in the first sentence, then connect major themes from key holdings (refer to holdings by ticker only).
    5. Focus on cross-holding themes (earnings trends, regulatory pressure, sector demand, macro sensitivity, input costs, capital spending).
    6. If articles conflict, explicitly acknowledge uncertainty instead of choosing a side.
    7. No bullets. No mention of how much the ETF price moved.
    8. Lead with the most recent and most material development.

    Narrative expectations:
    9. Explain what changed today, why it matters for the ETF’s sector exposure, and what that implies over the next 1–10 trading days.
    10. Avoid describing the ETF like a single company — synthesize themes across holdings.
    11. Highlight second-order effects where relevant (rates, commodities, policy shifts, supply chains, demand signals).
    12. End with a forward-looking sentence indicating what traders should monitor next (earnings from specific tickers, macro data, regulatory updates, etc.).
    """


    payload = f"{prompt.strip()}\n{json.dumps(compact, ensure_ascii=False)}"
    resp = generate_with_retry(
        lambda: client.models.generate_content(
            model=MODEL_ROLLUP,
            contents=[payload],
            config=types.GenerateContentConfig(temperature=0.3, top_p=0.9),
        )
    )
    if resp is None:
        return None

    return ((resp.text or "").strip()) or None


def _is_valid_summary(summary: Optional[str]) -> bool:
    """
    Validate that summary is legitimate content, not malformed AI meta-commentary.
    """
    if not summary or len(summary.strip()) < 50:
        return False

    lower = summary.lower()

    # Reject suspicious meta-commentary patterns
    suspicious = [
        "ready to generate",
        "please provide",
        "json list",
        "follows all the rules",
        "provide the",
        "here's the",
        "output the",
        "write a",
        "in json",
        "the summary is",
        "the briefing is",
        "the analysis is",
    ]
    for phrase in suspicious:
        if phrase in lower:
            return False

    # Reject if heavily fragmented
    lines = [l.strip() for l in summary.split('\n') if l.strip()]
    if len(lines) > 3:
        short_lines = sum(1 for l in lines if len(l) < 10)
        if short_lines / len(lines) > 0.3:
            return False

    return True


def upsert_symbol_daily_summary(cur: sqlite3.Cursor, symbol: str, asof_date: str, daily_summary: Optional[str]) -> None:
    if not _is_valid_summary(daily_summary):
        return
    cur.execute(
        """
      INSERT INTO symbol_daily_snapshot (symbol, asof_date, updated_at_utc, daily_summary)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(symbol, asof_date) DO UPDATE SET
        daily_summary=excluded.daily_summary,
        updated_at_utc=excluded.updated_at_utc
    """,
        (symbol, asof_date, now_utc(), daily_summary),
    )


def _load_tickers_json() -> Dict[str, Any]:
    try:
        return json.loads(Path(TICKERS_PATH).read_text(encoding="utf-8"))
    except Exception:
        return {"companies": []}


def is_etf_symbol(symbol: str) -> bool:
    sym = (symbol or "").upper().strip()
    if not sym:
        return False
    data = _load_tickers_json()
    for c in data.get("companies", []):
        if str(c.get("symbol", "")).upper().strip() == sym:
            sec = str(c.get("sector") or "").upper().strip()
            return sec == "ETF"
    return False

def is_macro_symbol(symbol: str) -> bool:
    return (symbol or "").upper().strip() in ("ECONOMY", "TRUMP")


def _load_etf_holdings_json(path: Path) -> List[Dict[str, Any]]:
    """
    Supports:
    - {"funds":[...]}
    - {"etfs":[...]}
    - {"data":[...]}
    - or a raw list: [...]
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(raw, list):
        return raw

    if isinstance(raw, dict):
        for key in ("funds", "etfs", "data", "items"):
            v = raw.get(key)
            if isinstance(v, list):
                return v

        if "symbol" in raw and "top_holdings" in raw:
            return [raw]

    return []


def get_top_holdings_for_etf_from_json(etf_symbol: str, limit: int = MAX_HOLDINGS_FOR_ROLLUP) -> List[str]:
    etf = (etf_symbol or "").upper().strip()
    if not etf:
        return []

    funds = _load_etf_holdings_json(ETF_HOLDINGS_JSON_PATH)
    if not funds:
        return []

    target = None
    for f in funds:
        if str(f.get("symbol", "")).upper().strip() == etf:
            target = f
            break
    if not target:
        return []

    holdings = target.get("top_holdings")
    if not isinstance(holdings, list):
        return []

    def w(h: Dict[str, Any]) -> float:
        try:
            return float(h.get("weight_pct") or 0.0)
        except Exception:
            return 0.0

    holdings_sorted = sorted(holdings, key=w, reverse=True)

    out: List[str] = []
    for h in holdings_sorted[: int(limit)]:
        hs = str(h.get("symbol", "")).upper().strip()
        if hs:
            out.append(hs)
    return out


def build_holding_to_etfs_map(path: Path, max_holdings: int = MAX_HOLDINGS_FOR_ROLLUP) -> Dict[str, List[str]]:
    """
    Maps holding_symbol -> [ETF1, ETF2, ...] using etfs.json.
    Only uses top `max_holdings` holdings per ETF (sorted by weight_pct desc).
    """
    funds = _load_etf_holdings_json(path)
    out: Dict[str, List[str]] = {}

    for f in funds:
        etf = str(f.get("symbol", "")).upper().strip()
        if not etf:
            continue

        holdings = f.get("top_holdings")
        if not isinstance(holdings, list):
            continue

        def w(h: Dict[str, Any]) -> float:
            try:
                return float(h.get("weight_pct") or 0.0)
            except Exception:
                return 0.0

        for h in sorted(holdings, key=w, reverse=True)[: int(max_holdings)]:
            hs = str(h.get("symbol", "")).upper().strip()
            if not hs:
                continue
            out.setdefault(hs, [])
            if etf not in out[hs]:
                out[hs].append(etf)

    return out



def should_generate_rollup(cur: sqlite3.Cursor, symbol: str, asof_date: str, force: bool = False) -> bool:
    """
    Generate a rollup if:
    - force is True, OR
    - there's no row for (symbol, asof_date), OR
    - daily_summary is NULL/empty string
    """
    if force:
        return True
    cur.execute(
        """
        SELECT daily_summary
        FROM symbol_daily_snapshot
        WHERE symbol = ? AND asof_date = ?
        LIMIT 1
        """,
        (symbol.upper().strip(), asof_date),
    )
    row = cur.fetchone()
    if row is None:
        return True
    val = row[0]
    return (val is None) or (str(val).strip() == "")

def fetch_symbol_daily_summaries_multi(
    cur: sqlite3.Cursor,
    symbols: List[str],
    asof_date: str,
) -> List[Dict[str, Any]]:
    syms = [s.upper().strip() for s in (symbols or []) if (s or "").strip()]
    if not syms:
        return []

    placeholders = ",".join(["?"] * len(syms))
    params = [*syms, asof_date]

    cur.execute(
        f"""
        SELECT
            UPPER(symbol) AS symbol,
            COALESCE(daily_summary, '') AS daily_summary,
            COALESCE(updated_at_utc, 0) AS updated_at_utc
        FROM symbol_daily_snapshot
        WHERE UPPER(symbol) IN ({placeholders})
          AND asof_date = ?
        """,
        params,
    )

    rows = cur.fetchall()
    if not rows:
        return []

    cols = [d[0] for d in cur.description]
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        s = str(d.get("symbol") or "").upper().strip()
        summ = str(d.get("daily_summary") or "").strip()
        if summ:
            out.append(
                {
                    "symbol": s,
                    "daily_summary": summ,
                    "updated_at_utc": int(d.get("updated_at_utc") or 0),
                }
            )
    return out

def build_etf_daily_rollup_from_symbol_rollups(
    client: genai.Client,
    etf_symbol: str,
    rollups: List[Dict[str, Any]],
) -> Optional[str]:
    if not rollups:
        return None

    now_ts = now_utc()
    compact = []
    for it in rollups[:MAX_HOLDINGS_FOR_ROLLUP + 1]:
        # Note: Rollups might have multiple articles, we use updated_at_utc as a proxy for recency
        up_ts = it.get("updated_at_utc") or 0
        age_h = round((now_ts - up_ts) / 3600.0, 1) if up_ts else 999
        compact.append(
            {
                "symbol": it["symbol"],
                "daily_summary": it["daily_summary"],
                "hours_since_update": age_h,
            }
        )

    prompt = f"""
    You are writing the "What's happening today and why?" section for the ETF {etf_symbol}.
    You will be given DAILY SUMMARIES for the ETF and/or its major holdings.

    Hard rules:
    1. Use ONLY the provided daily summaries (do not invent facts).
    2. PRIORITIZE RECENT SUMMARIES. Weight the most recently updated information (lowest "hours_since_update") more heavily in the first half of the narrative.
    3. Write 8–10 sentences total. Trader-facing, concise but analytical.
    4. Mention {etf_symbol} in the first sentence, then connect major themes from holdings (refer to holdings strictly by ticker).
    5. Synthesize across holdings — identify common sector drivers, not isolated company commentary.
    6. If items conflict, explicitly acknowledge uncertainty instead of choosing a side.
    7. No bullets. No mention of how much the ETF price moved.
    8. Lead with the most material and recent development.

    Narrative expectations:
    9. Explain what changed, why it matters for the ETF’s sector exposure, and what it implies over the next several trading sessions.
    10. Highlight second-order effects when relevant (rates, input costs, regulation, demand signals, macro sensitivity).
    11. End with one forward-looking sentence describing what traders should monitor next (specific holdings, sector catalysts, or macro drivers).
    """


    payload = f"{prompt.strip()}\n{json.dumps(compact, ensure_ascii=False)}"
    resp = generate_with_retry(
        lambda: client.models.generate_content(
            model=MODEL_ROLLUP,
            contents=[payload],
            config=types.GenerateContentConfig(temperature=0.3, top_p=0.9),
        )
    )
    if resp is None:
        return None

    return (resp.text or "").strip() or None

import concurrent.futures
import threading


def process_symbol_articles(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Stage 1 worker: Fetches, summarizes, and upserts articles for a single symbol.
    Returns dict with stats if successful, or None.
    """
    sym_u = symbol.upper().strip()
    
    print(f"   [WORKER] Checking {sym_u}...")
    # 1. Fetch Candidates (Reader)
    from db_utils import db_session
    with db_session(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cands = fetch_candidate_articles(cur, sym_u, limit=MAX_ARTICLES_PER_SYMBOL)

    if not cands:
        return None

    print(f"   [WORKER] Found {len(cands)} articles for {sym_u}. Calling Gemini...")
    time.sleep(2)
    client = genai.Client(api_key=GEMINI_API_KEY)

    batch_out: Dict[str, Dict[str, Any]] = {}
    sym_start = time.time()

    MAX_SECONDS_PER_SYMBOL = 30

    for chunk in _chunks(cands, BATCH_SIZE):
        if time.time() - sym_start > MAX_SECONDS_PER_SYMBOL:
            print(f"[{sym_u}] Skipping — symbol took too long")
            break

        out_part = summarize_articles_batch(client=client, symbol=sym_u, cands=chunk, max_items=len(chunk))
        if out_part:
            batch_out.update(out_part)

    if not batch_out:
        return None

    pending_rows = []
    res_stats = {}
    stored_for_symbol = 0
    now_ts = now_utc()
    for a in cands:
        out = batch_out.get(a.article_id)
        if out is None:
            continue

        pending_rows.append((
            a.article_id,
            a.symbol,
            MODEL_ARTICLE,
            out["input_source"],
            out["article_summary"],
            json.dumps(out["key_points"]),
            1 if out["is_relevant"] else 0,
            now_ts,
        ))

        # Check for sentiment change
        ref = out.get("sentiment_score")
        orig = out.get("original_sentiment")
        if ref is not None and orig is not None and abs(float(ref) - float(orig)) > 5.0:
            # We refine!
            from build_nlp import bucket_label
            label = bucket_label(int(round(ref)))
            # We don't have a batching mechanism for NLP updates yet in the worker return, 
            # let's just do it directly or add to return. 
            # Given current structure, let's add it to the return and flush in main.
            if "nlp_updates" not in res_stats:
                res_stats["nlp_updates"] = []
            res_stats["nlp_updates"].append((
                int(round(ref)),
                label,
                f"{MODEL_ARTICLE}-refined",
                now_ts,
                a.article_id
            ))

        stored_for_symbol += 1

    if stored_for_symbol > 0:
        res_stats.update({
            "symbol": sym_u,
            "new_summaries": stored_for_symbol,
            "pending_rows": pending_rows
        })
        return res_stats

    return None


def process_symbol_rollup(symbol: str, asof_date: str, force: bool = False) -> Dict[str, Any] | None:
    """
    Stage 2 worker: Generates daily rollup for a symbol if needed.
    """
    sym_u = symbol.upper().strip()
    
    from db_utils import db_session
    with db_session(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if not should_generate_rollup(cur, sym_u, asof_date, force=force):
            return None
            
        now_ts = now_utc()
        since_utc = now_ts - int(LOOKBACK_HOURS * 3600)
        items = fetch_today_article_summaries(cur, sym_u, since_utc=since_utc, limit=50)

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        rollup = build_daily_rollup(client, sym_u, items)
    except Exception as e:
        print(f"[{sym_u}] Error in process_symbol_rollup AI: {e}")
        return False

    if rollup is None:
        return False
    
    return {
        "symbol": sym_u,
        "rollup": rollup
    }

def process_etf_rollup_worker(etf_symbol: str, asof_date: str, triggered: bool) -> bool:
    """
    Stage 3 worker: Generates daily rollup for an ETF.
    """
    etf = etf_symbol.upper().strip()
    
    from db_utils import db_session
    with db_session(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        missing_today = should_generate_rollup(cur, etf, asof_date)
        
    if (not triggered) and (not missing_today):
        return False

    with db_session(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        now_ts = now_utc()
        since_utc = now_ts - int(LOOKBACK_HOURS * 3600)
        
        holdings = get_top_holdings_for_etf_from_json(etf, limit=MAX_HOLDINGS_FOR_ROLLUP)
        symbol_set = [etf] + holdings

        rollups = fetch_symbol_daily_summaries_multi(cur, symbol_set, asof_date=asof_date)
        
        items_fallback = []
        if not rollups: 
             items_fallback = fetch_today_article_summaries_multi(cur, symbol_set, since_utc=since_utc, limit=200)

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        etf_rollup = build_etf_daily_rollup_from_symbol_rollups(client, etf, rollups)

        if etf_rollup is None and items_fallback:
            etf_rollup = build_etf_daily_rollup(client, etf, items_fallback)
    except Exception as e:
        print(f"[{etf}] AI Error: {e}")
        return False

    if etf_rollup is None:
        return False

    return {
        "symbol": etf,
        "rollup": etf_rollup,
        "reason": "holdings-triggered" if triggered else "filled-missing"
    }

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force rollup regeneration")
    args = parser.parse_args()
    force = args.force

    print(f"Starting build_summary with MAX_WORKERS={MAX_WORKERS} (force={force})")
    
    now_dt = datetime.now(timezone.utc)
    asof_date = ny_asof_date_str(now_dt)
    
    conn_main = get_db_connection(DB_PATH)
    commit_with_retry(conn_main)
    
    symbols = load_enabled_symbols()
    # Inject Macro symbols
    symbols += ["ECONOMY", "TRUMP"]
    
    holding_to_etfs = build_holding_to_etfs_map(ETF_HOLDINGS_JSON_PATH, max_holdings=MAX_HOLDINGS_FOR_ROLLUP)
    conn_main.close() 

    print(f"Loaded {len(symbols)} symbols. Stage 1: Processing Articles...")

    changed_symbols: set[str] = set()
    etfs_to_rollup: set[str] = set()
    total_new = 0
    total_refined = 0

    all_pending_article_rows = []
    all_pending_nlp_updates = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_sym = {executor.submit(process_symbol_articles, sym): sym for sym in symbols}
        
        processed_count = 0
        for future in concurrent.futures.as_completed(future_to_sym):
            sym = future_to_sym[future]
            processed_count += 1
            try:
                res = future.result()
                if res:
                    sym_u = res["symbol"]
                    count = res["new_summaries"]
                    total_new += count
                    changed_symbols.add(sym_u)
                    
                    if "pending_rows" in res:
                        all_pending_article_rows.extend(res["pending_rows"])
                    
                    if "nlp_updates" in res:
                        all_pending_nlp_updates.extend(res["nlp_updates"])
                        total_refined += len(res["nlp_updates"])

                    for parent_etf in holding_to_etfs.get(sym_u, []):
                        etfs_to_rollup.add(parent_etf)

                    if is_etf_symbol(sym_u):
                        etfs_to_rollup.add(sym_u)
                        
                    print(f"[{processed_count}/{len(symbols)}] {sym_u} | +{count} summaries | {len(res.get('nlp_updates', []))} refined")
                else:
                    print(f"[{processed_count}/{len(symbols)}] {sym} | (no new summaries)")
            except Exception as exc:
                print(f"[{processed_count}/{len(symbols)}] {sym} | generated an exception: {exc}")

    if all_pending_article_rows:
        print(f"Flushing {len(all_pending_article_rows)} AI summaries to DB...")
        from db_utils import execute_many_with_retry
        conn_write = get_db_connection(DB_PATH)
        execute_many_with_retry(conn_write, UPSERT_AI_SUMMARY_SQL, all_pending_article_rows)
        if all_pending_nlp_updates:
            print(f"Flushing {len(all_pending_nlp_updates)} refined sentiments to DB...")
            execute_many_with_retry(conn_write, UPDATE_NLP_SENTIMENT_SQL, all_pending_nlp_updates)
        conn_write.close()

    print(f"Stage 1 Complete. New summaries: {total_new}. Refined: {total_refined}. Changed symbols: {len(changed_symbols)}")
    
    rollup_candidates = [s for s in changed_symbols if not is_etf_symbol(s)]
    
    # Ensure ECONOMY and TRUMP rollups are triggered if they had new news
    # (they are already in changed_symbols if processed in Stage 1)
    print(f"Stage 2: Processing {len(rollup_candidates)} Symbol Rollups...")
    
    total_rollups = 0
    processed_rollup_count = 0
    all_pending_rollups = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
         future_to_sym = {executor.submit(process_symbol_rollup, sym, asof_date, force=force): sym for sym in rollup_candidates}
         
         for future in concurrent.futures.as_completed(future_to_sym):
             sym = future_to_sym[future]
             processed_rollup_count += 1
             try:
                 res = future.result()
                 if res:
                     total_rollups += 1
                     all_pending_rollups.append((
                         res["symbol"],
                         asof_date,
                         now_utc(),
                         res["rollup"]
                     ))
                     print(f"[{processed_rollup_count}/{len(rollup_candidates)}] {sym} | Rollup generated")
                 else:
                     print(f"[{processed_rollup_count}/{len(rollup_candidates)}] {sym} | Rollup skipped")
             except Exception as exc:
                 print(f"Stage 2 error for {sym}: {exc}")

    all_etfs = {s.upper().strip() for s in symbols if is_etf_symbol(s)}
    final_etf_set = sorted(all_etfs | etfs_to_rollup)
    
    print(f"Stage 3: Processing {len(final_etf_set)} ETF Rollups...")
    
    processed_etf_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_etf = {}
        for etf in final_etf_set:
            triggered = etf in etfs_to_rollup
            future_to_etf[executor.submit(process_etf_rollup_worker, etf, asof_date, triggered or force)] = etf
            
        for future in concurrent.futures.as_completed(future_to_etf):
            etf = future_to_etf[future]
            processed_etf_count += 1
            try:
                res = future.result()
                if res and res.get("rollup"):
                    total_rollups += 1
                    all_pending_rollups.append((
                        res["symbol"],
                        asof_date,
                        now_utc(),
                        res["rollup"]
                    ))
                    print(f"[{processed_etf_count}/{len(final_etf_set)}] {etf} | ETF Rollup generated ({res['reason']})")
                else:
                    print(f"[{processed_etf_count}/{len(final_etf_set)}] {etf} | ETF Rollup skipped")
            except Exception as exc:
                print(f"Stage 3 error for {etf}: {exc}")

    if all_pending_rollups:
        print(f"Flushing {len(all_pending_rollups)} rollups to DB...")
        from db_utils import execute_many_with_retry
        conn_write = get_db_connection(DB_PATH)
        execute_many_with_retry(conn_write, UPSERT_DAILY_SNAPSHOT_SQL, all_pending_rollups)
        conn_write.close()

    print(f"Done. Total new articles: {total_new}. Total rollups: {total_rollups}")

if __name__ == "__main__":
    main()
