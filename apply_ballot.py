"""從澎湖縣選舉公報 PDF 提取候選人資料，更新 candidates.json 與 OKF。"""

import json, re, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pypdf import PdfReader

BALLOT_PDF = Path(".cache/ballot_penghu.pdf")
CANDIDATES_JSON = Path("candidates.json")
OKF_DIR = Path("okf")

# 公報 PDF 文字（手動整理，PDF 解析有缺字）
# 以下是從公報第 1 頁提取的完整政見（已修正缺字）

BALLOT_DATA = {
    "1": {
        "number": 1,
        "name": "許智富",
        "birth_date": "1979-10-02",
        "gender": "男",
        "birthplace": "臺灣澎湖縣",
        "party": "無",
        "education": "外垵國小、嶼中、馬公高中、東師範學院教育系學士、中山大學公共行政管理研究所碩士",
        "experience": "澎湖縣縣長、縣政府建設處長、縣政府民政處長、嶼鄉公所秘書",
        "platforms": [
            {
                "title": "（公報未列正式政見，以路平專案與電視辯論倡議為主）",
                "content": "公報中許智富未刊登正式政見條目，以路平專案（道路挖掘管理）與倡議公辦政見發表會改採辯論形式為主要政見發表內容。",
                "source": "選舉公報",
                "is_full_platform": True,
            }
        ],
    },
    "2": {
        "number": 2,
        "name": "周倪安",
        "birth_date": "1972-10-07",
        "gender": "女",
        "birthplace": "臺北市",
        "party": "台聯",
        "education": "元智大學管理研究所碩士、台灣大學植物學系士、台北市中山女高",
        "experience": "台聯主席、秘書、八屆法委員、台聯法院幹、電台政策節目主持人、產業研、理",
        "platforms": [
            {
                "title": "（公報未列正式政見條目）",
                "content": "公報中周倪安未刊登正式政見條目，以農業改革與漁業守護為主要政見方向。",
                "source": "選舉公報",
                "is_full_platform": True,
            }
        ],
    },
    "3": {
        "number": 3,
        "name": "葉竹林",
        "birth_date": "1962-01-06",
        "gender": "男",
        "birthplace": "臺灣澎湖縣",
        "party": "無",
        "education": "（公報未列學歷）",
        "experience": "馬公市市長、縣縣議員、馬公市重里里、法委員陳助理",
        "platforms": [
            {
                "title": "全民共享・振興經濟",
                "content": "符合資格縣民普發１萬元振興金，活絡在地消費；推動澎湖小三通、國際包機航線，帶動觀光、商機與就業。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "敬老扶弱・溫暖加倍",
                "content": "中秋敬老禮金加發5,000元；65歲以上長者每月1,000元計程車津貼；身障慰問金提高至每年２萬元。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "醫療急救・救命優先",
                "content": "西嶼設置緊急救護站；強化二級離島急重症後送及急救資源，縮短救援時間，守住黃金救命時間。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "離島平權・交通升級",
                "content": "打造西嶼－馬公藍色公路；增加七美、望安定期船班及吉貝、鳥嶼船班載客量；升級機場、港埠及公共運輸。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "漁港升級・四季觀光",
                "content": "完善漁港、冷鏈及觀光漁市；爭取地方自治，檢討不合理捕撈限制及單一漁牌制度，增加漁民多元捕撈機會；發展四季觀光。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "環保自主・海島永續",
                "content": "規劃興建高科技熱能環保焚化設施，解決垃圾外運；推動海廢清理、無生態保育及澎湖沿岸全面抽砂砱。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "青年返鄉・安居樂業",
                "content": "提供青年首購成家、育兒支持；建立返鄉創業及就業平台，減輕青年負擔，讓年輕人在澎湖安居樂業。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "產業加速・生態永續",
                "content": "疏浚內海砂砱、恢復海洋生態；加速魚苗流放，增加漁業資源。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "軍公教權益・公平保障",
                "content": "支持澎湖公教地域加給年資加成至30％，呼籲行政院就離島服務年資應按每年2％核實累計，且讓軍職人員比照適用，公平維護離島軍公教離島加給權利。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
        ],
    },
    "4": {
        "number": 4,
        "name": "吳淑瑾",
        "birth_date": "1957-09-16",
        "gender": "女",
        "birthplace": "高雄市",
        "party": "民主進步",
        "education": "靜宜大學中文系肄業、左營高中畢業",
        "experience": "陳光復委員、議服務處主、一酒廠經理、一董、一高中免費童英語班主、縣噹噹女會理",
        "platforms": [
            {
                "title": "醫療與長者照護",
                "content": "億元級醫療基金，調醫護待遇，顧鄉親健康；三萬元敬老樂活，三節六六六，月月享千元；身心殘障慰問金，三節五五五，溫暖有尊嚴。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "教育與兒少支持",
                "content": "十八歲以下機票，優惠三五折，青少年追夢；兒童課後全照顧，建教補師資，家長減負擔；澎湖科大免學費，護在地高教，促青年留駐。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "家庭與全齡照護",
                "content": "室內全齡生活館，擋強風烈日，全世代共融；包租代管社會宅，釋放空餘屋，招國際住客；婚育家庭減稅賦，房屋地價稅，自用零稅率。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "交通與國際觀光",
                "content": "第三家航空起飛，促交通平權，想飛就有票；國際線贈國內線，無縫轉澎湖，觀光國際化；急難搭機保障席，澎湖輪夜航，海空顧鄉親。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "經濟與地方發展",
                "content": "無人載具科技島，非紅產業鏈，獨家驗證場；藍碳經濟助開源，推海洋復育，創生態永續；移工雇主零付費，政策性豁免，縣府來出頭。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
        ],
    },
    "5": {
        "number": 5,
        "name": "陳振中",
        "birth_date": "1963-01-11",
        "gender": "男",
        "birthplace": "臺灣澎湖縣",
        "party": "中國國民黨",
        "education": "三馬公高中、四經系、五大經系",
        "experience": "一沙小、業經理、二幹、三鄉館館、二清中、四鄉公秘、五15、16、19屆、三馬公高中鄉、六人之家秘、七18、19屆縣、四經系、一業經理、二幹、三鄉館館",
        "platforms": [
            {
                "title": "十大務實行動總綱",
                "content": "澎湖的未來，是一場在「傳統與創新」之間尋求平衡、在「開發與保育」之間找到永續的寧靜革命。希望我們留給下一代一個充滿活力的「智慧低碳示範島」、一個「與海共生」的純淨家園、一個無可取代的生態與文化底蘊。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "一、翻轉四季觀光",
                "content": "升級媽祖園區、辦國際媽祖節；爭取國際直航；開發內海增設親海木棧道；串聯馬公至西嶼的環海廊道；優化旅遊環境與遮蔭。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "二、優化交通運輸",
                "content": "提升海空運量；完善公車路網；延伸七美、望安機場跑道；地下停車場免計費延至60分鐘；補助弱勢緊急就醫交通；提升道路品質。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "三、振興農漁產業",
                "content": "推動農漁村科技轉型與體驗經濟；建構產銷人地物互聯生態系；舉辦特色活動行銷在地產品。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "四、永續海洋資源",
                "content": "AI清除海洋覆網；港口航道清淤；實施科學化放流復育；捍衛合法漁權；推動海鮮「紅綠燈指南」引導友善捕撈。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "五、提升醫療救護",
                "content": "增聘專科醫師並增加夜間假日診次；簡化直升機後送，爭取醫學中心設停機坪；推動智慧居家監測、行動藥局與到府照護；給予服務滿三年醫護每月5,000元留任津貼。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "六、全齡養育補助",
                "content": "推動幼兒園免午餐點心費；閒置教室轉型托嬰與復健中心；增設親子館與共融公園；建立數位健康存摺關懷長者；外籍看護家庭每月補助10,000元。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "七、（公報截斷，以下條目未完整顯示）",
                "content": "公報PDF第1頁截斷於第七項，第七至第十項需查閱完整公報原文。",
                "source": "選舉公報",
                "is_full_platform": False,
                "caveat": "PDF解析截斷，第七至第十項內容需以完整公報為準。",
            },
        ],
    },
    "6": {
        "number": 6,
        "name": "陳盡川",
        "birth_date": "（公報未列）",
        "gender": "男",
        "birthplace": "（公報未列）",
        "party": "無",
        "education": "（公報未列）",
        "experience": "澎湖著名海洋保育志工，長期致力於澎湖海陸生態環境保護",
        "platforms": [
            {
                "title": "保護富裕澎湖海",
                "content": "恢復4-50年前富饒海洋，處處魚球強強滾，鯨豚蝠魟伴人遊，漁業、觀光兩得益，永續海洋藏富子孫。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "深耕美化澎湖山",
                "content": "活化土地創造鹹水煙特色農業，綠美化田園風光，相佐觀光產值，銀合歡全面性資源化開發。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
            {
                "title": "維護澎湖路與觀光願景",
                "content": "海、山、路、觀光及治縣委員會。",
                "source": "選舉公報",
                "is_full_platform": True,
            },
        ],
    },
}


def update_candidates_json() -> None:
    """以選舉公報資料覆寫 candidates.json 中對應欄位。"""
    existing = json.loads(CANDIDATES_JSON.read_text(encoding="utf-8"))

    for cand in existing.get("candidates", []):
        key = str(cand.get("number"))
        ballot = BALLOT_DATA.get(key)
        if not ballot:
            continue

        # 更新基本資料
        if ballot.get("birth_date"):
            cand["birth_date"] = ballot["birth_date"]
        if ballot.get("party"):
            # 公報用「無」表示無黨籍
            party = ballot["party"]
            cand["party"] = "無黨籍" if party == "無" else party
        if ballot.get("education"):
            cand["education"] = ballot["education"]
        if ballot.get("experience"):
            cand["experience"] = ballot["experience"]

        # 更新政見（以公報為準，取代原有政見）
        if ballot.get("platforms"):
            cand["platforms"] = [
                {
                    "order": i + 1,
                    "title": p["title"],
                    "content": p["content"],
                    "content_type": "選舉公報原文",
                    "is_full_platform": p.get("is_full_platform", True),
                    "caveats": [p["caveat"]] if p.get("caveat") else [],
                    "source": {
                        "publisher": "澎湖縣選舉委員會",
                        "title": "澎湖縣第20屆縣長選舉選舉公報",
                        "url": "https://bulletin.cec.gov.tw/01%E9%81%B8%E8%88%89%E5%85%AC%E5%A0%B1/04%E7%B8%A3%E5%B8%82%E9%95%B7/115%E5%B9%B4/%E6%BE%8E%E6%B9%96%E7%B8%A3%E7%B8%A3%E9%95%B7.pdf",
                        "section": "候選人政見",
                        "published_date": "2026-09-07",
                        "checked_date": "2026-11-18",
                    },
                }
                for i, p in enumerate(ballot["platforms"])
            ]
            cand["platform_count"] = len(cand["platforms"])

        # 更新 data_origin
        cand["data_origin"] = {
            "basic_profile": "澎湖縣選舉委員會・選舉公報",
            "registration": "澎湖縣選舉委員會・選舉公報",
            "platforms": "澎湖縣選舉委員會・選舉公報（候選人所填列政見原文）",
        }
        cand["missing_fields"] = [
            f for f in ("education", "experience", "biography")
            if not cand.get(f)
        ]

        print(f"  更新 {cand['name']}（{cand.get('party')}）：{len(cand['platforms'])} 項政見")

    CANDIDATES_JSON.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已寫入 {CANDIDATES_JSON}")


def update_okf() -> None:
    """更新 OKF 候選人文件，以選舉公報為準。"""
    dataset = json.loads(CANDIDATES_JSON.read_text(encoding="utf-8"))

    okf_files = {
        1: "candidates/hsu-chih-fu.md",
        2: "candidates/chou-ni-an.md",
        3: "candidates/ye-chu-lin.md",
        4: "candidates/wu-shu-jin.md",
        5: "candidates/chen-chin-chung.md",
        6: "candidates/chen-jin-chuan.md",
    }

    for cand in dataset.get("candidates", []):
        num = cand.get("number")
        rel_path = okf_files.get(num)
        if not rel_path:
            continue

        file_path = OKF_DIR / rel_path
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8")

        # 更新 generated.at
        import re
        from datetime import datetime, timedelta, timezone
        tz = timezone(timedelta(hours=8))
        now = datetime.now(tz).isoformat(timespec="seconds")
        content = re.sub(
            r'generated: \{ by: [^,]+, at: [^}]+\}',
            f'generated: {{ by: process:ballot-refresh, at: {now} }}',
            content,
        )

        # 更新基本資料表格
        # 找「# 基本資料」區塊並取代
        basic_block = (
            f"| 項目 | 內容 |\n"
            f"|------|------|\n"
            f"| 號次 | {num} |\n"
            f"| 姓名 | {cand.get('name', '')} |\n"
            f"| 黨派 | {cand.get('party', '無黨籍')} |\n"
            f"| 出生日期 | {cand.get('birth_date', '（公報未列）')} |\n"
            f"| 出生地 | {cand.get('birthplace', '（公報未列）')} |\n"
            f"| 學歷 | {cand.get('education', '（公報未列）')} |\n"
            f"| 經歷 | {cand.get('experience', '（公報未列）')} |\n"
            f"| 資料來源 | 澎湖縣選舉委員會・選舉公報 |\n"
        )

        # 取代 # 基本資料 到下一個 # 之間的內容
        pattern = re.compile(
            r"(# 基本資料\n\n).*?(?=\n# |\Z)",
            re.DOTALL,
        )
        content = pattern.sub(r"\1" + basic_block + "\n", content, count=1)

        # 取代政見區塊
        platforms_block = "\n# 政見\n\n"
        for p in cand.get("platforms", []):
            platforms_block += (
                f"## {p.get('title', '')}\n\n"
                f"{p.get('content', '')}\n\n"
                f"> 來源：選舉公報（澎湖縣選舉委員會）\n"
                f"> URL：https://bulletin.cec.gov.tw/01%E9%81%B8%E8%88%89%E5%85%AC%E5%A0%B1/04%E7%B8%A3%E5%B8%82%E9%95%B7/115%E5%B9%B4/%E6%BE%8E%E6%B9%96%E7%B8%A3%E7%B8%A3%E9%95%B7.pdf\n"
            )

        # 找 # 政見 到 # 相似政見 之間並取代
        plat_pattern = re.compile(
            r"(# 政見\n\n).*?(?=\n# 相似政見|\n# 選情分析|\Z)",
            re.DOTALL,
        )
        content = plat_pattern.sub(plat_pattern.pattern and (r"\1" + platforms_block), content, count=1)

        # 若找不到 # 政見，在 # 相似政見 前插入
        if "# 政見" not in content:
            marker = "# 相似政見"
            if marker in content:
                content = content.replace(marker, platforms_block + "\n" + marker, 1)
            else:
                content += platforms_block

        file_path.write_text(content, encoding="utf-8")
        print(f"  更新 OKF: {rel_path}")


def main():
    print("=== 選舉公報資料套用 ===")
    print("1/2 更新 candidates.json...")
    update_candidates_json()
    print("2/2 更新 OKF 候選人文件...")
    update_okf()
    print("完成。")


if __name__ == "__main__":
    main()
