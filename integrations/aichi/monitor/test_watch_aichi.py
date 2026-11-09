import unittest
from watch_aichi import parse,parse_dates,diff

HTML="""<html><table>
<tr><td>10月</td></tr>
<tr><th>日</th><th>競技会・行事</th><th>会場</th><th>要項</th><th>タイムテーブル</th><th>エントリー</th><th>注意事項</th><th>スタート・受付</th><th>結果</th></tr>
<tr><td>4（日）</td><td>2026年駅伝強化豊川長距離競技会</td><td>豊川</td><td></td><td></td><td></td><td></td><td><a href="assets/start.pdf">スタートリスト</a></td><td></td></tr>
<tr><td>12（月・祝）</td><td>2026年第1回駅伝強化長距離競技会</td><td>知多</td><td></td><td><a href="time.pdf">タイムテーブル</a></td><td></td><td></td><td></td><td></td></tr>
</table></html>"""
URL="https://www.aichi-rk.jp/01nittei.htm"

class ParserTests(unittest.TestCase):
 def test_dates(self):
  self.assertEqual(parse_dates("4（土） 5（日）",4),["2026-04-04","2026-04-05"])
  self.assertEqual(parse_dates("5/30（土）6/6（土）",5),["2026-05-30","2026-06-06"])
 def test_events_and_direct_urls(self):
  rows=parse(HTML,"aichi",URL)
  self.assertEqual(len(rows),2)
  self.assertEqual(rows[0]["dates"],["2026-10-04"])
  self.assertEqual(rows[0]["documents"][0]["kind"],"スタート・受付")
  self.assertEqual(rows[0]["documents"][0]["url"],"https://www.aichi-rk.jp/assets/start.pdf")
 def test_new_event(self):
  rows=parse(HTML,"aichi",URL)
  self.assertEqual(len(diff(rows,[],{},{},'today')),2)
 def test_changes_and_pdf_replacement(self):
  rows=parse(HTML,"aichi",URL)
  u=rows[0]["documents"][0]["url"]
  modified=[dict(r) for r in rows]
  modified[0]["venue"]="OKAKEN"
  kinds=[x["type"] for x in diff(modified,rows,{u:"before"},{u:"after"},"today")]
  self.assertIn("event_changed",kinds)
  self.assertIn("document_replaced",kinds)
if __name__=="__main__":
 unittest.main()
