#!/usr/bin/env python3
"""
Philippine Student Non-Dilutive Capital & Grant Intelligence Engine
Platform: Python 3.10+ (Standard Library Only)
Target: STI College Lipa / Direct Cash Inflow Priority Pipeline
"""

import argparse
import datetime
import hashlib
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
    clean = text.replace(chr(0x20b1), "P").replace("Php", "P").replace("PHP", "P")
    
    # Regex for monetary figures like P680-K, P50,000, P40K
    match = re.search(r'P\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*[-]?\s*([kKmMbB])?', clean)
    if match:
        raw_num = match.group(1).replace(",", "")
        multiplier_str = match.group(2)
        try:
            val = float(raw_num)
            if multiplier_str:
                m = multiplier_str.upper()
                if m == "K":
                    val *= 1000
                elif m == "M":
                    val *= 1000000
                elif m == "B":
                    val *= 1000000000
            # Discard general macro-budget lines (e.g. over 50M) to focus on actionable student funding
            if 1000 <= val <= 50000000:
                return int(val)
        except ValueError:
            pass

    # Known institutional student funding baselines
    t_lower = clean.lower()
    if "dost" in t_lower and any(w in t_lower for w in ["jlss", "scholarship", "stipend"]):
        return 80000  # DOST JLSS tuition support + monthly stipend benchmark
    if "ched" in t_lower and any(w in t_lower for w in ["tes", "tdp", "subsidy", "merit"]):
        return 40000  # CHED TES subsidy benchmark per school year
    if any(w in t_lower for w in ["hack4gov", "startup challenge", "bounty", "hackathon"]):
        return 50000  # Regional tech competition prize baseline
    if "batangas" in t_lower and any(w in t_lower for w in ["educational assistance", "scholarship"]):
        return 10000  # Provincial student grant per semester
    return 0


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
            content = resp.read()
    except urllib.error.URLError as err:
        logging.error("Failed to retrieve feed %s: %s", feed_url, err)
        return []

    entries = []
    try:
        root = ET.fromstring(content)
        for item in root.findall(".//item"):
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
        logging.error("XML parse error on %s: %s", feed_url, err)
        return []

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
                if is_blacklisted(entry["link"], full_text):
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
                    ) VALUES (?, ?, ?, ?, ?, 'grants', ?, ?, 1, ?, 0)
                """, (
                    entry_id,
                    entry["title"],
                    entry["link"],
                    entry["link"],
                    entry["summary"],
                    payout,
                    1 if is_local else 0,
                    now_iso
                ))
                new_records += 1

        conn.commit()
    logging.info("Ingestion completed. Inserted %d high-yield non-dilutive capital items.", new_records)
    return new_records


def list_records(db_path: str = DATABASE_FILE, limit: int = 15) -> None:
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("""
            SELECT id, title, payout_php, is_local, discovered_at
            FROM vouchers
            ORDER BY payout_php DESC, discovered_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()

    if not rows:
        print("No capital records found in database.")
        return

    print(f"\n{'ID':<18} | {'EST. PAYOUT':<12} | {'LOCAL':<5} | {'TITLE'}")
    print("-" * 85)
    for row in rows:
        payout_str = f"P{row['payout_php']:,}" if row['payout_php'] > 0 else "APPLY"
        local_str = "YES" if row["is_local"] else "NO"
        clean_title = row['title'].replace(chr(0x20b1), 'P')[:46]
        print(f"{row['id']:<18} | {payout_str:<12} | {local_str:<5} | {clean_title}")
    print("-" * 85)


def send_messenger_callmebot(apikey: str, text: str) -> bool:
    encoded_text = urllib.parse.quote(text)
    url = f"https://api.callmebot.com/facebook/send.php?apikey={apikey}&text={encoded_text}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.URLError as err:
        logging.error("CallMeBot delivery failed: %s", err)
        return False


def dispatch_alerts(callmebot_key: str, db_path: str = DATABASE_FILE) -> int:
    dispatched = 0
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("""
            SELECT id, title, link, payout_php, is_local
            FROM vouchers
            WHERE alerted = 0
            ORDER BY payout_php DESC
            LIMIT 5
        """)
        unalerted = cursor.fetchall()

        for item in unalerted:
            payout_badge = f"[PHP {item['payout_php']:,}]" if item['payout_php'] > 0 else "[CASH INFLOW]"
            local_badge = "[LIPA / BATANGAS]" if item['is_local'] else "[NATIONAL GRANT]"
            message_text = f"{payout_badge} {local_badge}\n{item['title']}\nSource: {item['link']}"

            if send_messenger_callmebot(callmebot_key, message_text):
                conn.execute("UPDATE vouchers SET alerted = 1 WHERE id = ?", (item["id"],))
                dispatched += 1

        conn.commit()
    logging.info("Dispatched %d priority capital alerts.", dispatched)
    return dispatched


def main() -> None:
    parser = argparse.ArgumentParser(description="Philippine Student Non-Dilutive Capital Engine")
    parser.add_argument("--init-db", action="store_true", help="Initialize or upgrade capital storage")
    parser.add_argument("--fetch", action="store_true", help="Fetch and filter capital inflows")
    parser.add_argument("--list", action="store_true", help="Display capital records ranked by payout")
    parser.add_argument("--callmebot-key", type=str, help="CallMeBot Messenger API key")
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

    if args.init_db:
        init_db()
    if args.fetch:
        ingest_feeds()
    if args.list:
        list_records()
    if args.auto:
        ingest_feeds()
        if args.callmebot_key:
            dispatch_alerts(args.callmebot_key)
        list_records()


if __name__ == "__main__":
    main()
