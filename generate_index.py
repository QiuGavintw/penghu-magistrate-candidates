import json, sys, re
from pathlib import Path
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
data = json.loads((PROJECT_ROOT / "candidates.json").read_text(encoding="utf-8"))

# 計算相似度
import importlib.util
spec = importlib.util.spec_from_file_location("rs", PROJECT_ROOT / "refresh_similarity.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

labels, matrix = mod.compute_similarity_matrix(data["candidates"])
pairs = mod.compute_top_pairs(data["candidates"], top_n=8)

CEC = "https://bulletin.cec.gov.tw/01%E9%81%B8%E8%88%89%E5%85%AC%E5%A0%B1/04%E7%B8%A3%E5%B8%82%E9%95%B7/115%E5%B9%B4/%E6%BE%8E%E6%B9%96%E7%B8%A3%E7%B8%A3%E9%95%B7.pdf"

def policy_html(cand):
    """產生候選人的 policy HTML。"""
    num = cand["number"]
    name = cand["name"]
    party = cand.get("party", "無黨籍")
    badge_cls = {"民主進步":"b-dpp","中國國民黨":"b-kmt","台聯":"b-ttp","台聯黨":"b-ttp"}.get(party, "b-ind")
    badge_label = {"民主進步":"民進黨","中國國民黨":"國民黨","台聯":"台聯黨","台聯黨":"台聯黨"}.get(party, "無黨籍")

    # 參選主軸
    taglines = {
        1: "前澎湖縣副縣長，具建設處長、民政處長行政經歷，以「食衣住行育樂」六面向提出施政願景。",
        2: "台聯黨主席，8 項政見，主打漁業復育、政治透明與海空港國際化。",
        3: "「澎湖2026-扛起澎湖・打開新局」，前馬公市長，9 大政見，定位「平民百姓對抗權貴與財團」。",
        4: "代夫出征，延續執政。陳光復因意外無法參選，由妻子吳淑瑾接棒，主打「世代平權，永續發展」。",
        5: "「澎湖ㄟ代誌阿中來打拼」，30 年基層行政經驗，十大務實行動，喊出「綠地變藍天」。",
        6: "澎湖著名海洋保育志工，長期致力於澎湖海陸生態環境保護，以「海、山、路、觀光」施政願景參選。",
    }
    tagline = taglines.get(num, "")

    # 搜尋關鍵字
    search_kw = " ".join(p.get("title", "") for p in cand.get("platforms", []))

    policies_html = []
    for p in cand.get("platforms", []):
        title = p.get("title", "")
        content = p.get("content", "")
        is_ballot = "公報" in str(p.get("source", {}).get("publisher", "")) or p.get("content_type") == "選舉公報原文" or "公報" in str(p.get("content_type", ""))
        src_tag = '<span class="src-ballot">選舉公報</span>' if is_ballot else '<span class="src-media">媒體</span>'
        src_link = f'<a href="{CEC}" target="_blank" rel="noopener">CEC 選舉公報</a>' if is_ballot else f'<a href="{p.get("source",{}).get("url","")}" target="_blank" rel="noopener">{p.get("source",{}).get("publisher","媒體")}</a>'
        policies_html.append(
            f'<div class="policy"><strong>{title}：</strong>{content}'
            f'<div class="src">{src_tag}{src_link}</div></div>'
        )

    card = (
        f'<div class="card" data-name="{name} {party} {search_kw}" data-content="{search_kw}">\n'
        f'  <div class="card-header" onclick="toggleCard(this)">\n'
        f'    <span class="badge {badge_cls}">{badge_label}</span>\n'
        f'    <h2>{name}{"（牛哥）" if num==6 else ""}</h2>\n'
        f'    <span class="num">{num}號</span>\n'
        f'    <span class="chevron">▼</span>\n'
        f'  </div>\n'
        f'  <div class="card-body">\n'
        f'    <div class="tagline"><strong>參選主軸：</strong>{tagline}</div>\n'
        + "\n".join(policies_html) + "\n"
        f'  </div>\n'
        f'</div>'
    )
    return card

# 產生所有候選人的 card
candidate_cards = [
    policy_html(c) for c in sorted(data["candidates"], key=lambda x: x.get("number", 0))
]

# 相似度矩陣 JS
sim_matrix_js = "\n".join(
    f"  [{', '.join(f'{v:.3f}' for v in row)}],"
    for row in matrix
).rstrip(",")

sim_pairs_js = ",\n".join(
    f'  {{sim:{p["similarity"]:.3f}, a:"{p["candidate_a"]}({p["number_a"]})", '
    f'aPolicy:"{p["policy_a"][:50]}", b:"{p["candidate_b"]}({p["number_b"]})", '
    f'bPolicy:"{p["policy_b"][:50]}"}}'
    for p in pairs
)

html = f'''<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>澎湖縣長候選人政見 | 2026</title>
<style>
:root {{ --bg:#F5F0E8; --card:#FFFDF8; --border:#E8DFD0; --text:#3A3228; --muted:#7A7060; --accent:#B8956B; --highlight:#FFF3D6; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC","Microsoft JhengHei",sans-serif; background:var(--bg); color:var(--text); line-height:1.8; padding:2rem 1rem; }}
.container {{ max-width:900px; margin:0 auto; }}
header {{ text-align:center; margin-bottom:1.5rem; padding:1.5rem 0; border-bottom:2px solid var(--border); }}
header h1 {{ font-size:1.6rem; margin-bottom:0.4rem; }}
header p {{ color:var(--muted); font-size:0.9rem; }}
.banner {{ background:var(--highlight); border-left:4px solid var(--accent); padding:0.9rem 1.1rem; border-radius:0 8px 8px 0; margin-bottom:1.5rem; font-size:0.88rem; }}
.banner strong {{ color:var(--accent); }}
.search-box {{ width:100%; padding:0.7rem 1rem; border:1px solid var(--border); border-radius:8px; font-size:0.95rem; background:var(--card); color:var(--text); margin-bottom:1.5rem; }}
.search-box:focus {{ outline:none; border-color:var(--accent); }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; margin-bottom:1.25rem; overflow:hidden; }}
.card-header {{ padding:1.1rem 1.3rem; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:0.8rem; cursor:pointer; user-select:none; }}
.card-header:hover {{ background:#FAF7F0; }}
.badge {{ display:inline-flex; align-items:center; gap:0.35rem; font-size:0.78rem; font-weight:600; padding:0.2rem 0.55rem; border-radius:20px; white-space:nowrap; }}
.badge::before {{ content:''; width:7px; height:7px; border-radius:50%; flex-shrink:0; }}
.b-dpp {{ background:#e8f5e9; color:#2e7d32; }} .b-dpp::before {{ background:#4A8C5C; }}
.b-kmt {{ background:#e3f2fd; color:#1565c0; }} .b-kmt::before {{ background:#4A7BA8; }}
.b-ttp {{ background:#fff3e0; color:#e65100; }} .b-ttp::before {{ background:#C87830; }}
.b-ind {{ background:#fce4ec; color:#880e4f; }} .b-ind::before {{ background:#B84A4A; }}
.b-teal {{ background:#e0f2f1; color:#00695c; }} .b-teal::before {{ background:#3A8C8C; }}
.card-header h2 {{ font-size:1.05rem; font-weight:700; flex:1; }}
.num {{ font-size:0.82rem; color:var(--muted); font-weight:600; }}
.chevron {{ color:var(--muted); font-size:0.75rem; transition:transform 0.2s; }}
.card.open .chevron {{ transform:rotate(180deg); }}
.card-body {{ display:none; padding:1.25rem; }}
.card.open .card-body {{ display:block; }}
.tagline {{ background:var(--highlight); border:1px solid var(--border); border-radius:8px; padding:0.8rem 1rem; margin-bottom:1rem; font-size:0.92rem; }}
.tagline strong {{ color:var(--accent); }}
.policy {{ background:#F9F6F0; border:1px solid var(--border); border-radius:8px; padding:0.8rem 0.9rem; margin-bottom:0.6rem; font-size:0.9rem; }}
.policy strong {{ color:var(--text); }}
.src {{ display:flex; align-items:center; gap:0.45rem; margin-top:0.4rem; font-size:0.78rem; color:var(--muted); flex-wrap:wrap; }}
.src a {{ color:var(--accent); text-decoration:underline; text-underline-offset:2px; }}
.src-ballot {{ background:var(--accent); color:white; font-size:0.7rem; font-weight:600; padding:0.15rem 0.45rem; border-radius:4px; }}
.src-fb {{ background:#4A7BA8; color:white; font-size:0.7rem; font-weight:600; padding:0.15rem 0.45rem; border-radius:4px; display:inline-flex; align-items:center; gap:0.25rem; }}
.src-media {{ background:var(--highlight); color:var(--accent); font-size:0.7rem; font-weight:600; padding:0.15rem 0.45rem; border-radius:4px; }}
.sim-section {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:1.3rem; margin-top:1.5rem; }}
.sim-section h2 {{ font-size:1rem; color:var(--accent); margin-bottom:0.4rem; }}
.sim-desc {{ font-size:0.83rem; color:var(--muted); margin-bottom:1rem; }}
.sim-table-wrap {{ overflow-x:auto; margin-bottom:1.25rem; }}
table.sim {{ width:100%; border-collapse:collapse; font-size:0.78rem; text-align:center; }}
table.sim th {{ background:var(--highlight); color:var(--accent); font-weight:700; padding:0.45rem 0.5rem; border:1px solid var(--border); min-width:3.5rem; }}
table.sim td {{ padding:0.4rem 0.5rem; border:1px solid var(--border); }}
table.sim .diag {{ background:var(--highlight); font-weight:700; color:var(--accent); }}
.pair {{ background:#F9F6F0; border:1px solid var(--border); border-radius:8px; padding:0.8rem 0.9rem; margin-bottom:0.6rem; font-size:0.85rem; }}
.pair-head {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:0.4rem; flex-wrap:wrap; gap:0.4rem; }}
.pair-sim {{ font-size:0.8rem; font-weight:700; color:white; background:var(--accent); padding:0.1rem 0.5rem; border-radius:20px; }}
.pair-cands {{ font-weight:700; }}
.pair-policy {{ color:var(--muted); font-size:0.8rem; line-height:1.5; }}
.pair-policy strong {{ color:var(--text); }}
.pair-arrow {{ color:var(--accent); font-size:0.85rem; margin:0.2rem 0; }}
.src-section {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:1.3rem; margin-top:1.5rem; }}
.src-section h2 {{ font-size:1rem; color:var(--accent); margin-bottom:0.8rem; }}
.src-list {{ list-style:none; font-size:0.83rem; }}
.src-list li {{ padding:0.35rem 0; border-bottom:1px solid var(--border); display:flex; align-items:flex-start; gap:0.5rem; }}
.src-list li:last-child {{ border-bottom:none; }}
.src-list a {{ color:var(--accent); text-decoration:none; word-break:break-all; }}
.src-list a:hover {{ text-decoration:underline; }}
footer {{ text-align:center; margin-top:1.5rem; padding:0.8rem 0; color:var(--muted); font-size:0.78rem; border-top:1px solid var(--border); }}
.hidden {{ display:none !important; }}
@media (max-width:600px) {{ body {{ padding:1rem 0.7rem; }} header h1 {{ font-size:1.3rem; }} }}
</style>
</head>
<body>
<div class="container">
<header>
  <h1>澎湖縣長候選人政見</h1>
  <p>2026 澎湖縣選舉 · 共 6 位候選人 · 投票日：2026年11月28日 · 資料來源：澎湖縣選舉委員會選舉公報</p>
</header>
<div class="banner">
  <strong>資料來源：</strong>本頁政見以<b>澎湖縣選舉委員會選舉公報</b>（CEC 公告）為最優先來源，1 號許智富與 2 號周倪安之政見以公報截圖轉錄方式取得，其次為候選人官方 Facebook 與主流媒體報導。所有來源均附連結，請自行查證。
</div>
<input type="text" class="search-box" id="searchBox" placeholder="搜尋候選人姓名或政見內容...">
<div id="candidates">

{chr(10).join(candidate_cards)}

</div>
<div class="sim-section">
  <h2>政見相似度分析</h2>
  <p class="sim-desc">以選舉公報政見原文，TF-IDF bigram cosine similarity 計算各候選人整體政策語言重疊程度。數值越高代表越接近。</p>
  <div style="font-size:0.85rem;font-weight:700;color:var(--accent);margin-bottom:0.6rem;">候選人整體相似度矩陣</div>
  <div class="sim-table-wrap" id="simMatrixWrap"></div>
  <div style="font-size:0.85rem;font-weight:700;color:var(--accent);margin-bottom:0.6rem;">最相似的跨候選人政見配對</div>
  <div id="simPairs"></div>
</div>
<div class="src-section">
  <h2>資料來源</h2>
  <ul class="src-list">
    <li><span class="src-ballot">最優先</span><span>澎湖縣選舉委員會・選舉公報</span><a href="{CEC}" target="_blank" rel="noopener">澎湖縣縣長.pdf</a></li>
    <li><span class="src-fb">f FB</span><span>葉竹林官方粉絲團</span><a href="https://www.facebook.com/YEHCHULINinPENGHU/" target="_blank" rel="noopener">YEHCHULINinPENGHU</a></li>
    <li><span class="src-fb">f FB</span><span>吳淑瑾官方粉絲團</span><a href="https://www.facebook.com/wushuchin.penghu/" target="_blank" rel="noopener">wushuchin.penghu</a></li>
    <li><span class="src-fb">f FB</span><span>陳盡川個人帳號</span><a href="https://www.facebook.com/chen.jin.chuan.441889/" target="_blank" rel="noopener">chen.jin.chuan.441889</a></li>
    <li><span class="src-media">媒體</span><span>自由時報</span><a href="https://news.ltn.com.tw/news/politics/breakingnews/5563070" target="_blank" rel="noopener">ltn.com.tw</a></li>
    <li><span class="src-media">媒體</span><span>中央社</span><a href="https://www.cna.com.tw/news/aloc/202611100294.aspx" target="_blank" rel="noopener">cna.com.tw</a></li>
    <li><span class="src-media">媒體</span><span>讀點 ReadMore</span><a href="https://www.moredetailnews.com/" target="_blank" rel="noopener">moredetailnews.com</a></li>
    <li><span class="src-media">追蹤</span><span>選舉政見追蹤</span><a href="https://www.twpromisetracker.org/elections/2026%E5%B9%B4%E6%BE%8E%E6%B9%96%E7%B8%A3%E9%95%B7%E9%81%B8%E8%88%89" target="_blank" rel="noopener">twpromisetracker.org</a></li>
  </ul>
</div>
<footer>資料蒐集日期：2026 年 11 月 18 日 · 政見以澎湖縣選舉委員會選舉公報為準 · 非官方資訊彙整</footer>
</div>
<script>
function toggleCard(h) {{ h.closest('.card').classList.toggle('open'); }}

const SIM_LABELS = {json.dumps([f"{c['name']}({c['number']})" for c in data["candidates"]], ensure_ascii=False)};
const SIM_MATRIX = [
{sim_matrix_js}
];
const SIM_PAIRS = [
{sim_pairs_js}
];

function simBg(v) {{ return v>=0.5?'#B8956B':v>=0.3?'#D4A574':v>=0.15?'#E8C9A0':v>=0.08?'#F0DCC0':'#F5F0E8'; }}
function simColor(v) {{ return v>=0.5?'#3A3228':v>=0.15?'#7A7060':'#B0A898'; }}

function renderMatrix() {{
  let html = '<table class="sim"><tr><th></th>';
  SIM_LABELS.forEach(l => html += '<th>'+l+'</th>');
  html += '</tr>';
  SIM_MATRIX.forEach((row,i) => {{
    html += '<tr><th>'+SIM_LABELS[i]+'</th>';
    row.forEach((v,j) => {{
      if(i===j) html += '<td class="diag">1.00</td>';
      else html += '<td style="background:'+simBg(v)+';color:'+simColor(v)+'">'+v.toFixed(2)+'</td>';
    }});
    html += '</tr>';
  }});
  html += '</table>';
  document.getElementById('simMatrixWrap').innerHTML = html;
}}

function renderPairs() {{
  let html = '';
  SIM_PAIRS.forEach(p => {{
    html += '<div class="pair"><div class="pair-head">' +
      '<span class="pair-cands">'+p.a+' <span style="color:var(--accent)">↔</span> '+p.b+'</span>' +
      '<span class="pair-sim">'+Math.round(p.sim*100)+'%</span></div>' +
      '<div class="pair-policy"><strong>'+p.a+'：</strong>'+p.aPolicy+'</div>' +
      '<div class="pair-arrow">▼ 最接近</div>' +
      '<div class="pair-policy"><strong>'+p.b+'：</strong>'+p.bPolicy+'</div></div>';
  }});
  document.getElementById('simPairs').innerHTML = html;
}}

document.addEventListener('DOMContentLoaded', function() {{
  renderMatrix();
  renderPairs();
  document.getElementById('searchBox').addEventListener('input', function() {{
    var q = this.value.trim().toLowerCase();
    document.querySelectorAll('.card').forEach(function(c) {{
      if(!q) {{ c.classList.remove('hidden'); return; }}
      var m = (c.dataset.name||'').toLowerCase().indexOf(q)!==-1 || c.textContent.toLowerCase().indexOf(q)!==-1;
      c.classList.toggle('hidden', !m);
      if(m) c.classList.add('open');
    }});
  }});
  var first = document.querySelector('.card');
  if(first) first.classList.add('open');
}});
</script>
</body>
</html>
'''

(PROJECT_ROOT / "index.html").write_text(html, encoding="utf-8")
print("index.html 已重新產生")
print(f"  候選人卡片：{len(candidate_cards)} 張")
print(f"  相似度矩陣：{len(matrix)}x{len(matrix)}")
print(f"  相似度配對：{len(pairs)} 組")
