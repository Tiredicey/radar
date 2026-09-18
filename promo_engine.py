#!/usr/bin/env python3
"""
Philippine Student Non-Dilutive Capital & Grant Intelligence Engine
Platform: Python 3.10+ (Standard Library Only)
Target: STI College Lipa / Direct Cash Inflow Priority Pipeline
"""

import argparse
import datetime
import hashlib
import html
import json
import logging
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# Force UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(SCRIPT_DIR, "vouchers.db")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

# Commercial coupon farms and clickbait domain blacklist
BLACKLIST_DOMAINS = [
    "forbes.com",
    "dexerto.com",
    "pocketgamer.com",
    "whoscored.com",
    "retailmenot.com",
    "couponbirds.com",
    "rappler.com/coupons",
    "iprice.ph",
    "picodi.com",
    "discounts.tribune.net.ph"
]

# Consumer spending triggers - any item requiring retail spend is dropped
SPENDING_TRIGGERS = [
    r"\bmin(?:imum)?\s*spend\b",
    r"\bmin(?:imum)?\s*purchase\b",
    r"\bbuy\s+\d+\s+take\s+\d+\b",
    r"\bbuy\s+one\s+get\s+one\b",
    r"\bcheckout\s+promo\b",
    r"\bupon\s+checkout\b",
    r"\boff\s+on\s+(?:all\s+)?orders\b",
    r"\border(?:s)?\s+over\b",
    r"\bshampoo\b",
    r"\bburger\b",
    r"\bcheeseburger\b",
    r"\bhadiah\s+gratis\b",
    r"\btoyota\b",
    r"\bcar\s+promo\b",
    r"\bflight\s+booking\b",
    r"\bhotel\s+stay\b",
    r"\bretail\s+discount\b",
    r"\bflash\s+deal\b",
    r"\bpiso\s+sale\b"
]

# Pure Non-Dilutive Capital Feeds (Grants, Scholarships, Subsidies, Bounties)
CAPITAL_FEEDS = [
    {
        "name": "DOST-SEI JLSS & PCIEERD Research Grants",
        "url": "https://news.google.com/rss/search?q=(DOST+OR+PCIEERD+OR+SEI)+AND+(scholarship+OR+grant+OR+JLSS+OR+stipend+OR+bounty)+when:30d&hl=en-PH&gl=PH&ceid=PH:en",
        "type": "rss"
    },
    {
        "name": "CHED TDP-TES & UniFAST Subsidies",
        "url": "https://news.google.com/rss/search?q=(CHED+OR+UniFAST)+AND+(TDP+OR+TES+OR+scholarship+OR+subsidy+OR+grant)+when:30d&hl=en-PH&gl=PH&ceid=PH:en",
        "type": "rss"
    },
    {
        "name": "DICT Hack4Gov & Startup Challenges",
        "url": "https://news.google.com/rss/search?q=DICT+AND+(Hack4Gov+OR+\"Startup+Challenge\"+OR+bounty+OR+hackathon+OR+grant)+when:30d&hl=en-PH&gl=PH&ceid=PH:en",
        "type": "rss"
    },
    {
        "name": "Batangas & Lipa Educational Funds",
        "url": "https://news.google.com/rss/search?q=(Batangas+OR+Lipa)+AND+(scholarship+OR+\"educational+assistance\"+OR+grant)+when:30d&hl=en-PH&gl=PH&ceid=PH:en",
        "type": "rss"
    }
]

LOCAL_KEYWORDS = ["lipa", "batangas", "calabarzon", "region 4a", "southern tagalog"]


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def get_db_connection(db_path: str = DATABASE_FILE) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def lead_category(text: str) -> str:
    if not re.search(r"\b(scholarships?|scholars|students?|educational assistance|tuition|stipend|hackathon|hack4gov|bounty|startup)\b|research.{0,30}(?:grant|fund)|grant.{0,30}research", text, re.I):
        return "out_of_scope"
    if not re.search(r"\b(closed|awarded|graduates|deadline passed)\b", text, re.I) and re.search(r"\bapply\b|accepting applications|applications? (?:are |is )?(?:open|until|deadline)|call for (?:applications|proposals)", text, re.I):
        return "application_lead"
    return "funding_news"


def init_db(db_path: str = DATABASE_FILE) -> None:
    logging.info("Initializing capital database: %s", db_path)
    with get_db_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vouchers (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                affiliate_link TEXT NOT NULL,
                summary TEXT,
                category TEXT,
                payout_php INTEGER DEFAULT 0,
                is_local INTEGER DEFAULT 0,
                is_grant INTEGER DEFAULT 1,
                discovered_at TEXT NOT NULL,
                alerted INTEGER DEFAULT 0
            )
        """)
        # Migration check for payout_php column if updating an existing db
        cursor = conn.execute("PRAGMA table_info(vouchers)")
        columns = [row[1] for row in cursor.fetchall()]
        if "payout_php" not in columns:
            conn.execute("ALTER TABLE vouchers ADD COLUMN payout_php INTEGER DEFAULT 0")
        for row in conn.execute("SELECT id,title,summary FROM vouchers").fetchall():
            text = row["title"] + " " + (row["summary"] or "")
            conn.execute("UPDATE vouchers SET category=?,payout_php=? WHERE id=?", (lead_category(text), extract_monetary_reward(text), row["id"]))
        conn.commit()
    logging.info("Capital schema ready.")


def generate_entry_id(title: str, link: str) -> str:
    raw_key = f"{title.strip().lower()}|{link.strip()}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]


def is_blacklisted(url: str, text: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    
    # 1. Domain blacklist
    if any(b in domain for b in BLACKLIST_DOMAINS):
        return True

    # 2. Spending trigger pattern matching
    t_lower = text.lower()
    for trigger in SPENDING_TRIGGERS:
        if re.search(trigger, t_lower):
            return True

    return False


def extract_monetary_reward(text: str) -> int:
    match = re.search(r"(?:₱|\bPHP\b|\bP(?=\s*\d))\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:-?\s*(thousand|million|billion|[kmb])\b)?", text, re.I)
    if not match:
        return 0
    factor = {"k": 1000, "thousand": 1000, "m": 1000000, "million": 1000000, "b": 1000000000, "billion": 1000000000}.get((match[2] or "").lower(), 1)
    amount = float(match[1].replace(",", "")) * factor
    return round(amount) if 0 <= amount < 2 ** 53 else 0


def parse_rss(feed_url: str) -> list[dict]:
    logging.debug("Polling capital feed: %s", feed_url)
    req = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read(1500001)
        if len(content) > 1500000 or re.search(br"<!DOCTYPE|<!ENTITY", content, re.I):
            raise ValueError("Unsafe or oversized RSS response")
    except urllib.error.URLError as err:
        logging.error("Feed request failed. Previous records retained.")
        raise RuntimeError("Feed unavailable") from None

    entries = []
    try:
        root = ET.fromstring(content)
        if root.tag != "rss" or root.find("channel") is None:
            raise ValueError("RSS channel missing")
        for item in root.findall("./channel/item")[:100]:
            title_node = item.find("title")
            link_node = item.find("link")
            desc_node = item.find("description")

            title = title_node.text if title_node is not None and title_node.text else "No Title"
            link = link_node.text if link_node is not None and link_node.text else ""
            summary = desc_node.text if desc_node is not None and desc_node.text else ""

            summary_clean = re.sub(r"<[^>]+>", "", summary).strip()

            entries.append({
                "title": title.strip(),
                "link": link.strip(),
                "summary": summary_clean
            })
    except ET.ParseError as err:
        logging.error("Feed XML is invalid.")
        raise RuntimeError("Invalid RSS") from None

    return entries


def ingest_feeds(db_path: str = DATABASE_FILE) -> int:
    new_records = 0
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with get_db_connection(db_path) as conn:
        for feed in CAPITAL_FEEDS:
            entries = parse_rss(feed["url"])
            for entry in entries:
                full_text = f"{entry['title']} {entry['summary']}"
                
                # Enforce commercial blacklist
                if is_blacklisted(entry["link"], full_text) or lead_category(full_text) == "out_of_scope":
                    logging.debug("Filtered out commercial/consumer item: %s", entry["title"])
                    continue

                entry_id = generate_entry_id(entry["title"], entry["link"])
                cur = conn.execute("SELECT id FROM vouchers WHERE id = ?", (entry_id,))
                if cur.fetchone() is not None:
                    continue

                payout = extract_monetary_reward(full_text)
                is_local = any(kw in full_text.lower() for kw in LOCAL_KEYWORDS)

                conn.execute("""
                    INSERT INTO vouchers (
                        id, title, link, affiliate_link, summary, 
                        category, payout_php, is_local, is_grant, discovered_at, alerted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0)
                """, (
                    entry_id,
                    entry["title"],
                    entry["link"],
                    entry["link"],
                    entry["summary"],
                    lead_category(full_text),
                    payout,
                    1 if is_local else 0,
                    now_iso
                ))
                new_records += 1

        conn.commit()
    logging.info("Ingestion completed. Inserted %d research leads; awards and eligibility are unverified.", new_records)
    return new_records


def list_records(db_path: str = DATABASE_FILE, limit: int = 15) -> None:
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("""
            SELECT id, title, payout_php, is_local, discovered_at, category
            FROM vouchers
            WHERE category != 'out_of_scope'
            ORDER BY (category='application_lead') DESC, is_local DESC, discovered_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()

    if not rows:
        print("No capital records found in database.")
        return

    print(f"\n{'ID':<18} | {'SOURCE AMOUNT':<12} | {'LOCAL':<5} | {'TITLE'}")
    print("-" * 85)
    for row in rows:
        payout_str = f"P{row['payout_php']:,}" if row['payout_php'] > 0 else "UNKNOWN"
        local_str = "YES" if row["is_local"] else "NO"
        clean_title = row['title'].replace(chr(0x20b1), 'P')[:46]
        print(f"{row['id']:<18} | {payout_str:<12} | {local_str:<5} | {clean_title}")
    print("-" * 85)


def classify_callmebot_response(body: str) -> str:
    visible = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", body, flags=re.I | re.S)
    visible = html.unescape(re.sub(r"<[^>]*>", " ", visible))
    visible = re.sub(r"\s+", " ", visible).strip().lower()
    for pattern, reason in [
        (r"(?:invalid|wrong|incorrect|missing)\s*(?:api[ -]?key|key)", "invalid-key"),
        (r"too many|rate limit|quota|wait.{0,15}(?:seconds|minutes)", "rate-limited"),
        (r"too long|too large|maximum.{0,20}(?:length|characters)", "message-too-long"),
        (r"not activated|not authorized|blocked|disabled", "not-authorized"),
        (r"\berror\s*[:!]|\bfailed\b|\bnot (?:be )?(?:sent|queued|accepted)\b|\bno message", "provider-error")
    ]:
        if re.search(pattern, visible):
            return reason
    if re.search(r"\bmessage\s+(?:(?:was|has been|is|successfully)\s+)*(?:sent|queued|accepted)\b|\bsuccessfully\s+(?:sent|queued)\b", visible):
        return "accepted"
    return "unrecognized-response"


def send_messenger_callmebot(apikey: str, text: str) -> bool:
    url = "https://api.callmebot.com/facebook/send.php?" + urllib.parse.urlencode({"apikey": apikey, "text": text})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read(4096).decode('utf-8', errors='replace')
            result = classify_callmebot_response(body)
            logging.info("CallMeBot result=%s http=%s message_chars=%d; response body withheld.", result, resp.status, len(text))
            return result == "accepted"
    except urllib.error.URLError as err:
        logging.error("CallMeBot request failed; credential-bearing details withheld.")
        return False


def dispatch_alerts(callmebot_key: str, db_path: str = DATABASE_FILE) -> int:
    if not callmebot_key:
        raise ValueError("CALLMEBOT_KEY missing")
    with get_db_connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        items = conn.execute("SELECT id,title,link FROM vouchers WHERE alerted=0 AND category='application_lead' ORDER BY is_local DESC,discovered_at DESC LIMIT 20").fetchall()
        text = "Radar research leads. Awards, eligibility and deadlines unverified."
        selected = []
        for item in items:
            candidate = text + "\n\n" + item["title"][:220] + "\n" + item["link"]
            if len(candidate) <= 1500 and len(urllib.parse.urlencode({"text": candidate})) <= 6000:
                text = candidate
                selected.append(item)
        items = selected
        conn.executemany("UPDATE vouchers SET alerted=2 WHERE id=?", [(r["id"],) for r in items])
    if not items:
        logging.info("No unalerted application leads fit the message budget. No message sent.")
        return 0
    if not send_messenger_callmebot(callmebot_key, text):
        logging.error("Notification not confirmed. See CallMeBot result above. Feed collection succeeded; no automatic retry in this database.")
        raise RuntimeError("Notification unconfirmed")
    with get_db_connection(db_path) as conn:
        conn.executemany("UPDATE vouchers SET alerted=1 WHERE id=?", [(r["id"],) for r in items])
    logging.info("Gateway accepted a digest of %d research leads; delivery unverified.", len(items))
    return len(items)


def main() -> None:
    parser = argparse.ArgumentParser(description="Philippine Student Non-Dilutive Capital Engine")
    parser.add_argument("--init-db", action="store_true", help="Initialize or upgrade capital storage")
    parser.add_argument("--fetch", action="store_true", help="Fetch and filter capital inflows")
    parser.add_argument("--list", action="store_true", help="Display capital records ranked by payout")
    parser.add_argument("--callmebot-key", type=str, default=os.environ.get("CALLMEBOT_KEY"), help="CallMeBot Messenger API key")
    parser.add_argument("--auto", action="store_true", help="Run fetch and dispatch in single pipeline execution")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()
    configure_logging(args.verbose)

    # Auto-load key from config.json if not passed via CLI
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as cf:
                cfg = json.load(cf)
                if not args.callmebot_key and "callmebot_key" in cfg:
                    args.callmebot_key = cfg["callmebot_key"]
        except Exception:
            pass

    if not any([args.init_db, args.fetch, args.list, args.auto]):
        parser.print_help()
        sys.exit(1)

    init_db()
    if args.fetch:
        ingest_feeds()
    if args.list:
        list_records()
    if args.auto:
        if not args.callmebot_key:
            raise ValueError("CALLMEBOT_KEY must be configured for automatic alerts")
        ingest_feeds()
        if os.environ.get("RADAR_BASELINE") == "1":
            with get_db_connection() as conn:
                conn.execute("UPDATE vouchers SET alerted=3 WHERE alerted=0")
            logging.warning("Silent baseline saved. Future new leads can notify.")
        else:
            dispatch_alerts(args.callmebot_key)
        list_records()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        logging.error("Run failed. Check feed availability, storage and secret configuration. Sensitive details withheld.")
        sys.exit(1)
