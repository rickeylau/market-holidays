#!/usr/bin/env python3
"""Publish Cboe U.S. options holiday exceptions as all-day ICS events."""
import argparse
import calendar
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SOURCE = 'https://www.cboe.com/about/hours/us-options/'
SPEC = 'https://www.cboe.com/tradable-products/sp-500/spx-options/spx-specifications'
CME = 'https://www.cmegroup.com/trading-hours.html'
SNAPSHOT = ROOT / 'holidays.json'
OUTPUT = ROOT / 'market-holidays.ics'
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if i}


def clean(s):
    return ' '.join(s.split())


def parse(html):
    soup = BeautifulSoup(html, 'html.parser')
    result = {}
    for table in soup.find_all('table'):
        rows = [[clean(c.get_text(' ', strip=True)) for c in tr.find_all(['th','td'], recursive=False)] for tr in table.find_all('tr')]
        header = next((i for i, r in enumerate(rows) if len(r)>=4 and [x.lower() for x in r[:4]] == ['holiday','date','regular trading hours','global trading hours']), None)
        if header is None:
            continue
        heading = next((h for h in table.find_all_previous(['h1','h2','h3','h4','h5','h6']) if re.search(r'\b20\d{2}\s+Options Holiday Schedule\b', h.get_text(' ',strip=True), re.I)), None)
        if heading is None:
            raise ValueError('Holiday table has no year heading')
        year = int(re.search(r'\b20\d{2}\b',heading.get_text(' ',strip=True)).group())
        if year in result:
            raise ValueError(f'Duplicate holiday table: {year}')
        events = []
        for r in rows[header+1:]:
            if not any(r):
                continue
            if len(r)!=4:
                raise ValueError(f'Unexpected row: {r}')
            name, date_text, rth, gth = r
            match = re.fullmatch(r'([A-Za-z]+)\s+(\d{1,2})(?:,?\s+(20\d{2}))?', date_text)
            if not match or match[1].lower() not in MONTHS or (match[3] and int(match[3])!=year):
                raise ValueError(f'Unexpected date: {date_text}')
            d = date(year, MONTHS[match[1].lower()], int(match[2]))
            if rth.lower() in {'none','closed','n/a','—'}:
                close = None
            else:
                hours = re.fullmatch(r'(\d{1,2}:\d{2})(?::\d{2})?\s*[-–—]\s*(\d{1,2}:\d{2})(?::\d{2})?',rth)
                if not hours:
                    raise ValueError(f'Unknown regular hours: {rth}')
                start, close = [datetime.strptime(x,'%H:%M').strftime('%H:%M') for x in hours.groups()]
                if start != '09:30' or not start < close < '16:00':
                    raise ValueError(f'Unexpected holiday session: {rth}')
            events.append(dict(date=d.isoformat(), holiday=name, close=close))
        validate_year(year,events)
        result[year] = sorted(events,key=lambda x:x['date'])
    if not result:
        raise ValueError('No Cboe options holiday tables found')
    return result


def validate_year(year, events):
    if not 9 <= len(events) <= 20 or len({e['date'] for e in events}) != len(events):
        raise ValueError(f'Incomplete or duplicate {year} holiday dates: {len(events)}')
    if sum(e['close'] is None for e in events)<9:
        raise ValueError(f'Incomplete closure schedule for {year}')
    for e in events:
        if date.fromisoformat(e['date']).year != year or not e['holiday']:
            raise ValueError(f'Invalid event: {e}')


def escape(s):
    return s.replace('\\','\\\\').replace('\n','\\n').replace(';','\\;').replace(',','\\,')


def fold(line):
    # RFC 5545: at most 75 octets; continuation starts with a space.
    out=[]; part=''
    for ch in line:
        if len((part+ch).encode('utf-8'))>75:
            out.append(part); part=' '+ch
        else:
            part+=ch
    out.append(part)
    return '\r\n'.join(out)


def render(data, stamp):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Market Holidays//EN','CALSCALE:GREGORIAN','X-WR-CALNAME:Market Holidays','X-WR-TIMEZONE:America/New_York']
    for e in sorted(data,key=lambda x:x['date']):
        d=date.fromisoformat(e['date']); close=e['close']; name=e['holiday']
        title=f'Market Closed (RTH) - {name}' if close is None else f'Early Close {close} ET - {name}'
        desc=(f'Cboe U.S. options regular session: closed.' if close is None else f'Cboe holiday regular session: 09:30-{close} ET. Expiring SPXW half-day cutoff: 13:00 ET per product specification.')
        desc+=f'\nHoliday exception for regular trading only. Global trading hours may differ. ES futures follow CME, not this calendar.\nOfficial Cboe schedule: {SOURCE}\nSPX specifications: {SPEC}\nCME schedule: {CME}'
        lines += ['BEGIN:VEVENT',f'UID:cboe-rth-{d.isoformat()}@market-holidays',f'DTSTAMP:{stamp}',f'DTSTART;VALUE=DATE:{d:%Y%m%d}',f'DTEND;VALUE=DATE:{d+timedelta(days=1):%Y%m%d}',f'SUMMARY:{escape(title)}',f'DESCRIPTION:{escape(desc)}',f'URL:{SOURCE}','TRANSP:TRANSPARENT','END:VEVENT']
    lines+=['END:VCALENDAR']
    return ('\r\n'.join(fold(x) for x in lines)+'\r\n').encode('utf-8')


def main():
    p=argparse.ArgumentParser(); p.add_argument('--offline',action='store_true',help='Build from last verified snapshot, no network'); args=p.parse_args()
    old=json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    current=datetime.now(ZoneInfo('America/New_York')).year
    if args.offline:
        data=old['events']; stamp=old['stamp']
    else:
        r=requests.get(SOURCE,timeout=(10,30),headers={'User-Agent':'Mozilla/5.0 (Market Holidays calendar)'})
        r.raise_for_status()
        fresh=parse(r.content)
        if current not in fresh:
            raise ValueError(f'Current-year schedule missing: {current}')
        prior={int(e['date'][:4]) for e in old['events'] if int(e['date'][:4])>=current}
        if not prior.issubset(fresh):
            raise ValueError(f'Previously published current/future schedule disappeared: {prior-set(fresh)}')
        data=sorted([e for e in old['events'] if int(e['date'][:4]) not in fresh]+[e for es in fresh.values() for e in es],key=lambda x:x['date'])
        stamp=old['stamp'] if data==old['events'] else datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for year in {int(e['date'][:4]) for e in data}:
        validate_year(year,[e for e in data if int(e['date'][:4])==year])
    payload=render(data,stamp)
    snapshot=(json.dumps(dict(source=SOURCE,stamp=stamp,events=data),indent=2,ensure_ascii=False)+'\n').encode('utf-8')
    for path, content in [(SNAPSHOT,snapshot),(OUTPUT,payload)]:
        if not path.exists() or path.read_bytes()!=content:
            tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_bytes(content); tmp.replace(path)
    print(f'{len(data)} holiday exceptions: {sum(e["close"] is None for e in data)} closures, {sum(e["close"] is not None for e in data)} early closes.')

if __name__=='__main__':
    main()
