"""Run example extraction scenarios to validate the extractor pipeline."""
from platform.extractor.engine import AdaptiveExtractor
from platform.agents.llm_client import LLMClient

SAMPLE_CARD_HTML = '''
<div class="events">
  <div class="card">
    <h3>親子社交技巧工作坊（自閉症適用）</h3>
    <p>日期：2026/06/15 上午10:00-12:00</p>
    <p>地點：九龍塘社區中心</p>
    <p>費用：$150</p>
    <a href="https://example.org/register?id=1">報名連結</a>
  </div>
  <div class="card">
    <h3>普通話語言發展班</h3>
    <p>日期：2026/07/01</p>
    <p>地點：灣仔社區中心</p>
    <p>費用：免費</p>
    <a href="https://example.org/register?id=2">報名連結</a>
  </div>
</div>
'''

SAMPLE_TABLE_HTML = '''
<table>
<tr><th>Title</th><th>Date</th><th>Fee</th></tr>
<tr><td>Speech Delay Assessment</td><td>2026-06-20 14:00</td><td>HK$0</td></tr>
<tr><td>ADHD Parent Seminar</td><td>2026-06-25 18:30</td><td>$200</td></tr>
</table>
'''

def run():
    llm = LLMClient()
    extractor = AdaptiveExtractor(llm_client=llm)

    print('\n--- Card HTML Example ---')
    res = extractor.extract_from_page(SAMPLE_CARD_HTML, 'https://example.org/events')
    for r in res[:3]:
        print('MERGED:', r['merged'])
        print('NORMALIZED:', r['normalized'])
        print('CONFIDENCE:', r['confidence'])
        print('LOGS:', r['logs'])

    print('\n--- Table HTML Example ---')
    res2 = extractor.extract_from_page(SAMPLE_TABLE_HTML, 'https://example.org/table')
    for r in res2[:3]:
        print('MERGED:', r['merged'])
        print('NORMALIZED:', r['normalized'])
        print('CONFIDENCE:', r['confidence'])

if __name__ == '__main__':
    run()
