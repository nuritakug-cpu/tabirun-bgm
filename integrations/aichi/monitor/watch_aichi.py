#!/usr/bin/env python3
"""Read-only Aichi athletics metadata watcher; never publishes athlete personal data."""
import hashlib,json,re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
from urllib.request import Request,urlopen
from bs4 import BeautifulSoup

JST=timezone(timedelta(hours=9))
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
SOURCES={
 "aichi":"https://www.aichi-rk.jp/01nittei.htm",
 "nagoya":"https://www.aichi-rk.jp/01_01nittei.htm",
 "owari":"https://www.aichi-rk.jp/01_02nittei.htm",
 "nishimikawa":"https://www.aichi-rk.jp/01_03nittei.htm",
}
KINDS=["要項","タイムテーブル","エントリー","注意事項","スタート・受付","結果"]
UA="TOPRUN-PublicScheduleWatcher/1.0 (read-only, six-hour interval)"

def clean(s):
 return re.sub(r"\s+","",str(s or "").replace("\u3000"," "))

def txt(tag):
 return " ".join(tag.stripped_strings)

def uid(*parts):
 return hashlib.sha256("|".join(clean(p) for p in parts).encode()).hexdigest()[:20]

def parse_dates(raw,month,year=2026):
 out=[]
 for m in re.finditer(r"(?<!\d)(?:(\d{1,2})/)?(\d{1,2})\s*[（(]",raw):
  mo,day=int(m.group(1) or month or 0),int(m.group(2))
  try:
   v=f"{year:04d}-{mo:02d}-{day:02d}"
   datetime.strptime(v,"%Y-%m-%d")
   if v not in out:out.append(v)
  except ValueError:pass
 return out

def parse(raw,key,url,year=2026):
 soup=BeautifulSoup(raw,"html.parser")
 month=None;out=[];seen={}
 for tr in soup.find_all("tr"):
  cells=tr.find_all(["td","th"],recursive=False)
  if len(cells)<3:
   if cells:
    m=re.match(r"\s*(1[0-2]|[1-9])\s*月",txt(tr))
    if m:month=int(m.group(1))
   continue
  if len(cells)<7:continue
  name,place=txt(cells[1]).strip(),txt(cells[2]).strip()
  dates=parse_dates(txt(cells[0]),month,year)
  if not name or not place or not dates or len(name)>220 or len(place)>100:continue
  base=uid(key,str(year),name);dup=seen.get(base,0);seen[base]=dup+1
  eid=base if not dup else uid(base,str(dup))
  docs=[]
  for i,cell in enumerate(cells[3:9]):
   kind=KINDS[i]
   for a in cell.find_all("a",href=True):
    href=a.get("href","").strip()
    if not href or href.lower().startswith(("javascript:","mailto:","#")):continue
    link=urljoin(url,href)
    if urlparse(link).scheme not in ("https","http"):continue
    label=txt(a).strip() or (a.find("img") or {}).get("alt") or kind
    doc={"kind":kind,"label":label[:100],"url":link}
    if doc not in docs:docs.append(doc)
  out.append({"id":eid,"name":name,"dates":dates,"venue":place,"source":key,"sourceUrl":url,"documents":docs})
 return out

def fetch(url,limit=4*1024*1024):
 req=Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/pdf,*/*;q=0.5"})
 with urlopen(req,timeout=25) as r:
  chunks=[];size=0
  while True:
   piece=r.read(min(65536,limit+1-size))
   if not piece:break
   size+=len(piece)
   if size>limit:raise ValueError("Size limit exceeded")
   chunks.append(piece)
  return b"".join(chunks)

def diff(current,old,oldhash,hashes,stamp):
 before={v["id"]:v for v in old}
 after={v["id"]:v for v in current}
 changes=[]
 for eid,e in after.items():
  b=before.get(eid)
  if b is None:
   changes.append({"type":"new_event","eventId":eid,"name":e["name"],"at":stamp})
   continue
  for field in ("name","dates","venue"):
   if e[field]!=b.get(field):
    changes.append({"type":"event_changed","field":field,"eventId":eid,"name":e["name"],"before":b.get(field),"after":e[field],"at":stamp})
  olddocs={(d["kind"],d["url"]):d for d in b.get("documents",[])}
  docs={(d["kind"],d["url"]):d for d in e["documents"]}
  for k in docs.keys()-olddocs.keys():
   changes.append({"type":"document_added","eventId":eid,"name":e["name"],"document":docs[k],"at":stamp})
  for k in olddocs.keys()-docs.keys():
   changes.append({"type":"document_link_removed","eventId":eid,"name":e["name"],"document":olddocs[k],"at":stamp})
  for k in docs.keys()&olddocs.keys():
   url=k[1]
   if oldhash.get(url) and hashes.get(url) and oldhash[url]!=hashes[url]:
    changes.append({"type":"document_replaced","eventId":eid,"name":e["name"],"document":docs[k],"at":stamp})
 for eid,e in before.items():
  if eid not in after:
   changes.append({"type":"event_not_found","eventId":eid,"name":e["name"],"at":stamp})
 return changes

def run():
 now=datetime.now(JST);stamp=now.isoformat(timespec="seconds")
 oldfile=DATA/"aichi_catalog.json"
 old=json.loads(oldfile.read_text("utf-8")) if oldfile.exists() else {"events":[],"documentHashes":{}}
 events=[];errors=[];status={};ok=set()
 for key,url in SOURCES.items():
  try:
   rows=parse(fetch(url),key,url)
   if not rows:raise ValueError("No event rows recognized: HTML may have changed")
   events.extend(rows);ok.add(key)
   status[key]={"ok":True,"events":len(rows),"at":stamp}
  except Exception as ex:
   msg=f"{key}: {type(ex).__name__} {str(ex)[:120]}";errors.append(msg)
   status[key]={"ok":False,"message":msg,"at":stamp}
 if not ok:raise RuntimeError("All official sources failed. Keep last published data.")
 for e in old.get("events",[]):
  if e["source"] not in ok:events.append(e)
 events.sort(key=lambda e:(e["dates"][0] if e["dates"] else "9999",e["source"],e["name"]))
 hashes=dict(old.get("documentHashes",{}));nbytes=0;checks=0
 for e in events:
  if not e["dates"] or max(e["dates"])<(now.date()-timedelta(days=40)).isoformat() or min(e["dates"])>(now.date()+timedelta(days=160)).isoformat():continue
  for d in e["documents"]:
   u=d["url"]
   if (urlparse(u).hostname or "") not in ("aichi-rk.jp","www.aichi-rk.jp"):continue
   if checks>=150 or nbytes>=120*1024*1024:
    errors.append("Document check budget exceeded; retry next run");break
   checks+=1
   try:
    blob=fetch(u,12*1024*1024);nbytes+=len(blob)
    hashes[u]=hashlib.sha256(blob).hexdigest()
   except Exception as ex:
    errors.append(f"Document check failed: {u} ({type(ex).__name__})")
 changes=diff(events,old.get("events",[]),old.get("documentHashes",{}),hashes,stamp)
 DATA.mkdir(parents=True,exist_ok=True)
 new={"schemaVersion":1,"checkedAt":stamp,"fiscalYear":2026,"sources":SOURCES,"sourceStatus":status,"events":events,"documentHashes":hashes,"errors":errors}
 oldfile.write_text(json.dumps(new,ensure_ascii=False,indent=2)+"\n","utf-8")
 histfile=DATA/"aichi_changes.json"
 history=json.loads(histfile.read_text("utf-8")) if histfile.exists() else {"changes":[]}
 history["checkedAt"]=stamp;history["changes"]=(changes+history["changes"])[:500]
 histfile.write_text(json.dumps(history,ensure_ascii=False,indent=2)+"\n","utf-8")
 print(f"Events: {len(events)}; changes: {len(changes)}; errors: {len(errors)}")

if __name__=="__main__":
 run()
