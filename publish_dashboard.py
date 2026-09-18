import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def publish(dry_run=False):
    base = os.environ.get('RADAR_URL', '').rstrip('/')
    token = os.environ.get('RADAR_SYNC_TOKEN', '')
    url = urllib.parse.urlparse(base)
    if not dry_run and (url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path or len(token) < 32):
        print('Set RADAR_URL to the HTTPS site origin and RADAR_SYNC_TOKEN to at least 32 random characters.', file=sys.stderr)
        return 1
    feeds = json.loads((Path(__file__).parent / 'feeds.json').read_text())
    failures = 0
    for feed in feeds:
        try:
            req = urllib.request.Request(feed['url'], headers={'User-Agent': 'CapitalRadar/2.0', 'Accept': 'application/rss+xml'})
            with urllib.request.urlopen(req, timeout=15) as response:
                xml = response.read(1500001)
            if len(xml) > 1500000 or b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
                raise ValueError('Invalid XML')
            root = ET.fromstring(xml)
            if root.tag != 'rss' or root.find('channel') is None:
                raise ValueError('Not RSS')
            if dry_run:
                print(f"{feed['id']}: {len(root.findall('./channel/item'))} raw RSS items; no upload")
                continue
            req = urllib.request.Request(base + '/api/feeds/' + feed['id'], data=xml, method='POST', headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/rss+xml', 'X-Collected-At': str(int(time.time()*1000)), 'User-Agent': 'RadarCollector/1.0'})
            with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as response:
                receipt = json.loads(response.read(8192))
            if receipt.get('accepted') is not True or receipt.get('source') != feed['id']:
                raise ValueError('Upload not acknowledged')
            print(f"{feed['id']}: accepted; {receipt.get('count')} filtered leads; updated={receipt.get('updated')}")
        except urllib.error.HTTPError as error:
            failures += 1
            print(f"{feed['id']}: HTTP {error.code}; verify endpoint and sync configuration", file=sys.stderr)
        except (OSError, ValueError, ET.ParseError):
            failures += 1
            print(f"{feed['id']}: collection or upload failed; sensitive details withheld", file=sys.stderr)
    return int(failures > 0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sync public RSS to Radar D1. Does not send notifications.')
    parser.add_argument('--dry-run', action='store_true')
    sys.exit(publish(parser.parse_args().dry_run))
