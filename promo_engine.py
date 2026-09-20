#!/usr/bin/env python3
"""
Philippine Student Non-Dilutive Capital & Grant Intelligence Engine
Platform: Python 3.10+ (Standard Library Only)
Target: STI College Lipa / Direct Cash Inflow Priority Pipeline
"""

import argparse
import datetime
from contextlib import contextmanager
from dataclasses import dataclass
import time
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


@contextmanager
def get_db_connection(db_path: str = DATABASE_FILE):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


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
        conn.execute("""CREATE TABLE IF NOT EXISTS notification_state (
            id INTEGER PRIMARY KEY CHECK(id=1), last_attempt INTEGER NOT NULL DEFAULT 0,
            last_accepted INTEGER NOT NULL DEFAULT 0, result TEXT NOT NULL DEFAULT 'never-attempted',
            initialized INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("INSERT OR IGNORE INTO notification_state(id,initialized) SELECT 1,EXISTS(SELECT 1 FROM vouchers)")
        conn.execute("CREATE INDEX IF NOT EXISTS vouchers_alert_queue ON vouchers(alerted,category,discovered_at)")
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


@dataclass(frozen=True)
class GatewayResult:
    outcome: str
    reason: str
    http_status: int = 0


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_messenger_callmebot(apikey: str, text: str) -> GatewayResult:
    url = "https://api.callmebot.com/facebook/send.php?" + urllib.parse.urlencode({"apikey": apikey, "text": text})
    req = urllib.request.Request(url, headers={"User-Agent": "CapitalRadar/3.0"})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as resp:
            body = resp.read(65537)
            reason = classify_callmebot_response(body.decode('utf-8', errors='replace')) if len(body) <= 65536 else 'oversized-response'
            if not 200 <= resp.status < 300:
                result = GatewayResult('uncertain', 'unexpected-http-status', resp.status)
            elif reason == 'accepted':
                result = GatewayResult('accepted', reason, resp.status)
            elif reason in {'invalid-key', 'rate-limited', 'message-too-long', 'not-authorized', 'provider-error'}:
                result = GatewayResult('rejected', reason, resp.status)
            else:
                result = GatewayResult('uncertain', reason, resp.status)
    except urllib.error.HTTPError as error:
        result = GatewayResult('rejected' if error.code in {400, 401, 403, 413, 414, 429} else 'uncertain', 'http-' + str(error.code), error.code)
        error.close()
    except (OSError, urllib.error.URLError):
        result = GatewayResult('uncertain', 'network-error')
    logging.info('CallMeBot outcome=%s reason=%s http=%s message_chars=%d; response body withheld.', result.outcome, result.reason, result.http_status, len(text))
    return result


def queue_counts(conn) -> dict:
    rows = conn.execute('SELECT alerted,category,COUNT(*) AS count FROM vouchers GROUP BY alerted,category').fetchall()
    return {
        'pending_applications': sum(r['count'] for r in rows if r['alerted'] == 0 and r['category'] == 'application_lead'),
        'unnotified_news': sum(r['count'] for r in rows if r['alerted'] == 0 and r['category'] == 'funding_news'),
        'uncertain_leads': sum(r['count'] for r in rows if r['alerted'] == 2),
        'accepted_leads': sum(r['count'] for r in rows if r['alerted'] == 1),
        'baseline_leads': sum(r['count'] for r in rows if r['alerted'] == 3)
    }


def message_fits(text: str) -> bool:
    return len(text) <= 1500 and len(urllib.parse.urlencode({'text': text})) <= 6000


def pht_timestamp(epoch: int) -> str:
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M PHT')


def dispatch_alerts(callmebot_key: str, db_path: str = DATABASE_FILE, *, heartbeat_hours=24,
                    test_message=False, retry_uncertain=False, report=None, now=None) -> int:
    if not (callmebot_key or '').strip():
        raise ValueError('CALLMEBOT_KEY missing')
    if not 0 <= heartbeat_hours <= 168:
        raise ValueError('Heartbeat interval must be between 0 and 168 hours')
    report = report if report is not None else {}
    now = int(time.time()) if now is None else now
    selected = []
    with get_db_connection(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        if retry_uncertain:
            report['requeued'] = conn.execute("UPDATE vouchers SET alerted=0 WHERE alerted=2 AND category='application_lead'").rowcount
            logging.warning('Explicit recovery requeued %d uncertain leads; duplicates are possible.', report['requeued'])
        report.update(queue_counts(conn))
        state = conn.execute('SELECT * FROM notification_state WHERE id=1').fetchone()
        report.update(previous_gateway_result=state['result'], last_gateway_accepted_at=state['last_accepted'], oversized_leads=0)
        header = 'Radar research leads. Awards, eligibility and deadlines unverified.'
        text, kind = header, 'digest'
        if test_message:
            kind = 'test'
            text = (f'Radar Messenger connection test — {pht_timestamp(now)}.\n'
                    'If you can read this message, delivery reached this chat.\n'
                    'No research leads were marked as notified.\nhttps://radar-1y6.pages.dev/static/#sources')
        else:
            for item in conn.execute("SELECT id,title,link FROM vouchers WHERE alerted=0 AND category='application_lead' ORDER BY discovered_at ASC,is_local DESC,id ASC"):
                entry = '\n\n' + item['title'][:220] + '\n' + item['link']
                if not message_fits(header + entry):
                    report['oversized_leads'] += 1
                elif message_fits(text + entry):
                    text += entry
                    selected.append(item)
            if not selected:
                due = heartbeat_hours > 0 and (state['last_attempt'] == 0 or now - state['last_attempt'] >= heartbeat_hours * 3600)
                if due:
                    kind = 'heartbeat'
                    text = (f'Radar status — {pht_timestamp(now)}\n'
                            f"New research leads collected this run: {report.get('new_records', 'not checked')}.\n"
                            f"Pending application-wording leads: {report['pending_applications']}.\n"
                            f"Unnotified funding news: {report['unnotified_news']} (not verified open applications).\n"
                            f"Uncertain lead attempts needing review: {report['uncertain_leads']}.\n"
                            'No new application digest was sent in this check.\n'
                            'Awards, eligibility and deadlines remain unverified.\nhttps://radar-1y6.pages.dev/static/#discover')
                else:
                    report['notification'] = 'message-budget-blocked' if report['pending_applications'] else 'no-pending-applications'
                    report['next_heartbeat_at'] = state['last_attempt'] + heartbeat_hours * 3600 if heartbeat_hours else None
                    report['attention_required'] = bool(report['uncertain_leads'] or report['oversized_leads'] or state['result'] in {'uncertain', 'rejected'})
                    if report['attention_required']:
                        raise RuntimeError('Notification history needs review')
                    return 0
        conn.executemany('UPDATE vouchers SET alerted=2 WHERE id=?', [(r['id'],) for r in selected])
        conn.execute("UPDATE notification_state SET last_attempt=?,result='uncertain' WHERE id=1", (now,))
        report['notification'] = kind + '-attempted'
    result = send_messenger_callmebot(callmebot_key, text)
    report.update(gateway_outcome=result.outcome, gateway_reason=result.reason, gateway_http=result.http_status)
    with get_db_connection(db_path) as conn:
        if result.outcome != 'uncertain':
            conn.executemany('UPDATE vouchers SET alerted=? WHERE id=?', [(1 if result.outcome == 'accepted' else 0, r['id']) for r in selected])
        conn.execute("UPDATE notification_state SET result=?,last_accepted=CASE WHEN ?='accepted' THEN ? ELSE last_accepted END WHERE id=1", (result.outcome, result.outcome, now))
        report.update(queue_counts(conn))
    report.update(notification=kind + '-' + result.outcome, accepted_this_run=len(selected) if result.outcome == 'accepted' else 0)
    report['attention_required'] = result.outcome != 'accepted' or bool(report['uncertain_leads'] or report['oversized_leads'])
    if result.outcome != 'accepted':
        raise RuntimeError('Gateway did not confirm acceptance; rejected leads remain pending, uncertain attempts require review')
    report['last_gateway_accepted_at'] = now
    logging.info('Gateway accepted %s with %d leads; Messenger delivery and device notifications remain unverified.', kind, len(selected))
    if report['attention_required'] and not test_message:
        raise RuntimeError('Notification history needs review')
    return len(selected)


def write_run_summary(report: dict, db_path: str = DATABASE_FILE) -> None:
    with get_db_connection(db_path) as conn:
        report.update(queue_counts(conn))
    logging.info('Notification summary: %s', json.dumps(report, sort_keys=True))
    if not os.environ.get('GITHUB_STEP_SUMMARY'):
        return
    lines = ['## Messenger notification report', '', '| Check | Result |', '| --- | --- |']
    for key, value in report.items():
        if key.endswith('_at') and value:
            value = pht_timestamp(value)
        lines.append(f"| {key.replace('_', ' ').capitalize()} | {value} |")
    lines += ['', 'Gateway acceptance is not a Messenger delivery/read receipt or a device-notification confirmation.',
              'Only new application-wording leads enter digests. Funding news is counted, not represented as an open application.',
              'Daily status is sent on the first eligible successful scan, not at an exact clock time.',
              'Run workflow → test sends one diagnostic. Check Messenger before retry-uncertain; duplicates are possible.',
              'Cache history is best-effort. Missing history baselines existing leads instead of rebroadcasting them.', '']
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
        summary.write('\n'.join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Philippine Student Non-Dilutive Capital Engine")
    parser.add_argument("--init-db", action="store_true", help="Initialize or upgrade capital storage")
    parser.add_argument("--fetch", action="store_true", help="Fetch and filter capital inflows")
    parser.add_argument("--list", action="store_true", help="Display capital records ranked by payout")
    parser.add_argument("--callmebot-key", type=str, default=os.environ.get("CALLMEBOT_KEY"), help="CallMeBot Messenger API key")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--auto', action='store_true', help='Fetch leads and send pending applications or a due status')
    mode.add_argument('--test-notification', action='store_true', help='Send one diagnostic without fetching or altering lead flags')
    parser.add_argument('--retry-uncertain', action='store_true', help='With --auto, requeue uncertain application attempts; duplicates are possible')
    parser.add_argument('--heartbeat-hours', type=int, default=24, help='Quiet-status interval, 0 disables, maximum 168 (default: 24)')
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

    if not any([args.init_db, args.fetch, args.list, args.auto, args.test_notification]):
        parser.print_help()
        sys.exit(1)
    if args.retry_uncertain and not args.auto:
        parser.error('--retry-uncertain requires --auto')
    if not 0 <= args.heartbeat_hours <= 168:
        parser.error('--heartbeat-hours must be between 0 and 168')
    if args.test_notification and (args.fetch or args.list):
        parser.error('--test-notification cannot fetch or list leads')
    init_db()
    report = {'run_result': 'failed', 'notification': 'not-attempted', 'heartbeat_hours': args.heartbeat_hours}
    try:
        if (args.auto or args.test_notification) and not (args.callmebot_key or '').strip():
            report['notification'] = 'missing-key'
            raise ValueError('CALLMEBOT_KEY must be configured for notifications')
        if args.fetch or args.auto:
            with get_db_connection() as conn:
                baseline = not conn.execute('SELECT initialized FROM notification_state WHERE id=1').fetchone()[0]
            report['new_records'] = ingest_feeds()
            with get_db_connection() as conn:
                if args.auto:
                    report['baseline'] = baseline or os.environ.get('RADAR_BASELINE') == '1'
                    if report['baseline']:
                        conn.execute('UPDATE vouchers SET alerted=3 WHERE alerted=0')
                        logging.warning('Silent lead baseline saved; status messages remain enabled. No old lead digest will be sent.')
                conn.execute('UPDATE notification_state SET initialized=1 WHERE id=1')
        if args.auto or args.test_notification:
            dispatch_alerts(args.callmebot_key, heartbeat_hours=args.heartbeat_hours,
                            test_message=args.test_notification, retry_uncertain=args.retry_uncertain, report=report)
        if args.list or args.auto:
            list_records()
        report['run_result'] = 'completed'
    finally:
        if args.auto or args.test_notification:
            write_run_summary(report)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        logging.error("Run failed. Check feed availability, storage and secret configuration. Sensitive details withheld.")
        sys.exit(1)
