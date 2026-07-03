#!/usr/bin/env python3
"""
Generate and verify concrete job-card data for the static site.

Every scheduled run checks each source job page before writing jobs.json. Jobs
that are unreachable, clearly expired, or no longer contain the expected title
and company are removed from the published data.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent
JOBS_FILE = ROOT / "jobs.json"
LOG_FILE = ROOT / "update_log.md"
TZ_GUANGZHOU = timezone(timedelta(hours=8))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

EXPIRED_PATTERNS = [
    "职位已下线",
    "职位已关闭",
    "职位已过期",
    "职位不存在",
    "岗位已下架",
    "招聘已结束",
    "停止招聘",
    "页面不存在",
]


def boss_search(keyword: str) -> str:
    return f"https://www.zhipin.com/web/geek/job?query={quote(keyword)}&city=101280100&district=440106"


def job51_search(keyword: str) -> str:
    return f"https://we.51job.com/pc/search?keyword={quote(keyword)}&jobArea=030200"


def zhilian_search(keyword: str) -> str:
    return f"https://sou.zhaopin.com/?jl=763&kw={quote(keyword)}"


def c58_search(keyword: str) -> str:
    return f"https://gz.58.com/job/?key={quote(keyword)}"


def liepin_search(keyword: str) -> str:
    return f"https://www.liepin.com/zhaopin/?city=050020&dq=050020&key={quote(keyword)}"


def boss_mobile_search(keyword: str) -> str:
    return f"https://m.zhipin.com/gz/job/?query={quote(keyword)}"


def job51_mobile_search(keyword: str) -> str:
    return f"https://m.51job.com/search/joblist.php?keyword={quote(keyword)}&jobarea=030200"


def c58_mobile_search(keyword: str) -> str:
    return f"https://m.58.com/gz/job/?key={quote(keyword)}"


def liepin_mobile_search(keyword: str) -> str:
    return liepin_search(keyword)


def zhilian_mobile_link(url: str) -> str:
    match = re.search(r"/jobdetail/([^/?#]+)\.htm", url)
    if match:
        return f"https://m.zhaopin.com/jobs/{match.group(1)}.htm"
    match = re.search(r"/jobs/([^/?#]+)\.htm", url)
    if match:
        return f"https://m.zhaopin.com/jobs/{match.group(1)}.htm"
    return url


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", unescape(text or "")).lower()


def fetch_page(url: str) -> tuple[int, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=18) as resp:
        raw = resp.read(300_000)
        charset = resp.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="ignore")
        return resp.status, resp.geturl(), html


def verify_job(job: dict) -> tuple[bool, str]:
    url = job["directLink"]
    try:
        status, final_url, html = fetch_page(url)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    if status < 200 or status >= 300:
        return False, f"HTTP {status}"

    compact = normalize_text(html)
    for pattern in EXPIRED_PATTERNS:
        if normalize_text(pattern) in compact:
            return False, f"expired marker: {pattern}"

    title_ok = normalize_text(job["title"]) in compact
    company_ok = normalize_text(job["company"]) in compact
    if not title_ok or not company_ok:
        return False, "source page no longer matches title/company"

    return True, f"ok {status} {final_url}"


def make_job(
    job_id: str,
    title: str,
    company: str,
    salary: str,
    category: str,
    location: str,
    subway: str,
    subway_lines: list[str],
    subway_distance: str,
    area: str,
    direct_link: str,
    requirements: str,
    tags: list[str],
    source: str,
    source_published: str,
    now: str,
) -> dict:
    search_keyword = f"{company} {title}"
    return {
        "id": job_id,
        "title": title,
        "company": company,
        "salary": salary,
        "category": category,
        "location": location,
        "subway": subway,
        "subwayLines": subway_lines,
        "subwayDistance": subway_distance,
        "area": area,
        "directLink": direct_link,
        "linkType": "verified",
        "requirements": requirements,
        "tags": tags + [source, "每日核验"],
        "isNew": source_published in {"3天内", "本周"},
        "verified": True,
        "source": source,
        "sourcePublished": source_published,
        "lastChecked": now,
        "verificationStatus": "verified-active",
        "platformLinks": {
            "boss": boss_search(search_keyword),
            "51job": job51_search(search_keyword),
            "zhilian": zhilian_search(search_keyword),
            "58": c58_search(search_keyword),
            "liepin": liepin_search(search_keyword),
        },
        "mobilePlatformLinks": {
            "direct": zhilian_mobile_link(direct_link),
            "boss": boss_mobile_search(search_keyword),
            "51job": job51_mobile_search(search_keyword),
            "zhilian": zhilian_mobile_link(direct_link),
            "58": c58_mobile_search(search_keyword),
            "liepin": liepin_mobile_search(search_keyword),
        },
        "miniProgramLinks": {
            "direct": "",
            "boss": "",
            "51job": "",
            "zhilian": "",
            "58": "",
            "liepin": "",
        },
    }


def source_key(source: str) -> str:
    if "BOSS" in source:
        return "boss"
    if "前程" in source or "51" in source:
        return "51job"
    if "58" in source:
        return "58"
    if "猎聘" in source:
        return "liepin"
    return "zhilian"


def platform_company_search(source: str, company: str) -> str:
    key = source_key(source)
    if key == "boss":
        return boss_search(company)
    if key == "51job":
        return job51_search(company)
    if key == "58":
        return c58_search(company)
    if key == "liepin":
        return liepin_search(company)
    return zhilian_search(company)


def platform_company_mobile_search(source: str, company: str) -> str:
    key = source_key(source)
    if key == "boss":
        return boss_mobile_search(company)
    if key == "51job":
        return job51_mobile_search(company)
    if key == "58":
        return c58_mobile_search(company)
    if key == "liepin":
        return liepin_mobile_search(company)
    return zhilian_search(company)


def make_platform_job(
    job_id: str,
    title: str,
    company: str,
    salary: str,
    category: str,
    location: str,
    subway: str,
    subway_lines: list[str],
    subway_distance: str,
    area: str,
    direct_link: str,
    requirements: str,
    tags: list[str],
    source: str,
    source_published: str,
    now: str,
) -> dict:
    job = make_job(
        job_id,
        title,
        company,
        salary,
        category,
        location,
        subway,
        subway_lines,
        subway_distance,
        area,
        direct_link,
        requirements,
        tags,
        source,
        source_published,
        now,
    )
    key = source_key(source)
    search_keyword = f"{company} {title}"
    company_search_link = platform_company_search(source, company)
    company_mobile_search_link = platform_company_mobile_search(source, company)
    job["linkType"] = "platform-candidate"
    job["directLink"] = company_search_link
    job["originalDetailLink"] = direct_link
    job["verified"] = False
    job["verificationStatus"] = "platform-candidate"
    job["verificationReason"] = f"{source} 详情页可能需要登录、安全验证或已下架；按钮改为在{source}搜索公司名称，请打开平台核对。"
    job["tags"] = tags + [source, "搜索公司"]
    job["platformLinks"][key] = company_search_link
    job["mobilePlatformLinks"]["direct"] = company_mobile_search_link
    job["mobilePlatformLinks"][key] = company_mobile_search_link
    job["miniProgramLinks"] = {
        "direct": "",
        "boss": "",
        "51job": "",
        "zhilian": "",
        "58": "",
        "liepin": "",
    }
    if key != "zhilian":
        job["platformLinks"]["zhilian"] = zhilian_search(search_keyword)
    return job


def filter_known_company_candidates(jobs: list[dict]) -> list[dict]:
    vague_company_markers = ["平台企业", "电商企业", "招聘公司"]
    return [
        job for job in jobs
        if job.get("company") and not any(marker in job["company"] for marker in vague_company_markers)
    ]


def candidate_jobs(now: str) -> list[dict]:
    return [
        make_job(
            "job-20260703-001",
            "短视频拍摄剪辑师13薪（双休）",
            "广州市雅俗共赏文化传媒有限公司",
            "9000-13000元/月",
            "拍摄",
            "广州天河区",
            "天河区",
            [],
            "天河区范围，需打开来源核对具体地址",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1281652160J40596384804.htm",
            "1-3年经验，大专；短视频拍摄剪辑岗位，13薪、双休。",
            ["13薪", "双休", "拍剪一体"],
            "智联招聘",
            "上周",
            now,
        ),
        make_job(
            "job-20260703-002",
            "Ai漫剧剪辑师助理",
            "广州汇智云人工智能科技有限公司",
            "6000-8000元/月",
            "剪辑",
            "广州天河区",
            "天河区",
            [],
            "天河区范围，需打开来源核对具体地址",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1525435800J40857563611.htm",
            "经验不限，大专；AI漫剧剪辑助理，招聘负责人刚在线。",
            ["经验不限", "AI漫剧", "助理"],
            "智联招聘",
            "2周内",
            now,
        ),
        make_job(
            "job-20260703-003",
            "短视频制作剪辑助理",
            "广州汇智云人工智能科技有限公司",
            "5000-8000元/月",
            "剪辑",
            "广州天河区",
            "天河区",
            [],
            "天河区范围，需打开来源核对具体地址",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1525435800J40858756911.htm",
            "协助完成短视频素材整理与粗剪，适合剪辑助理方向。",
            ["剪辑助理", "短视频", "本周"],
            "智联招聘",
            "上周",
            now,
        ),
        make_job(
            "job-20260703-004",
            "信息流短视频剪辑师",
            "广州用心选供应链有限公司",
            "6000-8000元/月",
            "剪辑",
            "广州天河区",
            "天河区",
            [],
            "天河区范围，需打开来源核对具体地址",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1495809540J40747711801.htm",
            "1-3年经验，学历不限；信息流短视频剪辑，负责人刚在线。",
            ["信息流", "短视频", "学历不限"],
            "智联招聘",
            "近期",
            now,
        ),
        make_job(
            "job-20260703-005",
            "摄像师",
            "ZAKER",
            "6000-11000元/月",
            "拍摄",
            "广州天河区",
            "天河区",
            [],
            "天河区范围，需打开来源核对具体地址",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CC464221920J40810353713.htm",
            "经验不限，大专；摄像师岗位，发布较新，负责人刚在线。",
            ["摄像师", "经验不限", "3天内"],
            "智联招聘",
            "3天内",
            now,
        ),
        make_job(
            "job-20260703-006",
            "影视后期剪辑师",
            "广州哔然文化科技有限公司",
            "7000-10000元/月",
            "剪辑",
            "广州天河区",
            "天河区",
            [],
            "天河区范围，需打开来源核对具体地址",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1524900740J41012160804.htm",
            "1-3年经验，学历不限；影视后期剪辑方向。",
            ["影视后期", "学历不限", "剪辑师"],
            "智联招聘",
            "近期",
            now,
        ),
        make_job(
            "job-20260703-007",
            "影楼摄影助理可接受新人",
            "广州侬淇科技有限公司",
            "5000-7000元/月",
            "拍摄",
            "广州天河区",
            "天河区",
            [],
            "天河区范围，需打开来源核对具体地址",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1525387210J40856800411.htm",
            "经验不限，学历不限；影楼摄影助理，可接受新人。",
            ["摄影助理", "接受新人", "经验不限"],
            "智联招聘",
            "上周",
            now,
        ),
        make_job(
            "job-20260703-008",
            "TikTok短视频剪辑/拍摄/跨境电商",
            "广东全球拼购电子商务有限公司",
            "6000-8000元/月",
            "拍摄",
            "广州天河区",
            "天河区",
            [],
            "天河区范围，需打开来源核对具体地址",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1293253300J40866134205.htm",
            "1-3年经验，大专；TikTok短视频剪辑/拍摄，周末休息。",
            ["TikTok", "拍摄剪辑", "周末休息"],
            "智联招聘",
            "近期",
            now,
        ),
        make_job(
            "job-20260703-009",
            "视频设计专员（双体）",
            "广州贤易达信息科技有限公司",
            "4000-5000元/月",
            "剪辑",
            "广州天河区",
            "天河区",
            [],
            "天河区范围，需打开来源核对具体地址",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1498769150J40817298201.htm",
            "经验不限，学历不限；视频设计专员，偏视频制作与设计。",
            ["视频设计", "经验不限", "入门"],
            "智联招聘",
            "近期",
            now,
        ),
        make_job(
            "job-20260703-010",
            "视频剪辑实习生",
            "三到书房(广州)文化传播有限公司",
            "100-200元/天",
            "剪辑",
            "广州天河区汉银广场",
            "天河区",
            [],
            "汉银广场，需打开来源核对通勤",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1511498490J40867280210.htm",
            "经验不限，学历不限；视频剪辑实习生，适合实习/入门。",
            ["实习", "汉银广场", "文化传播"],
            "智联招聘",
            "近期",
            now,
        ),
        make_job(
            "job-20260703-011",
            "短视频剪辑师",
            "广州云芒电媒科技有限公司",
            "4000-5000元/月",
            "剪辑",
            "广州天河区富力盈隆广场",
            "冼村",
            ["18"],
            "黄村地铁约4-5站换乘可达，需打开来源核对通勤路线",
            "nearby5",
            "https://www.zhaopin.com/jobdetail/CCL1513938220J40863267902.htm",
            "经验不限，大专；负责短视频全流程剪辑，适配 TikTok 等平台风格，熟练 PR/剪映优先。",
            ["短视频", "TikTok", "PR/剪映"],
            "智联招聘",
            "6月23日",
            now,
        ),
        make_job(
            "job-20260703-012",
            "视频混剪专员",
            "智绘传媒(广州)有限公司",
            "6000-8000元/月",
            "剪辑",
            "广州市天河区燕岭路89号4楼4027",
            "兴华 / 燕塘",
            ["3", "6"],
            "黄村地铁约4-5站换乘可达，需打开来源核对通勤路线",
            "nearby5",
            "https://www.zhaopin.com/jobdetail/CCL1515562090J40839247310.htm",
            "1-3年经验；负责视频素材整理、混剪、卡点、转场、调色、字幕和平台比例适配。",
            ["混剪", "剪映", "PR"],
            "智联招聘",
            "近期",
            now,
        ),
        make_job(
            "job-20260703-013",
            "电商短视频剪辑主管/经理（高薪、双休）",
            "东莞市科询信息科技有限公司",
            "20000-35000元/月",
            "剪辑",
            "广州天河区联合社区车陂北街28号之一8-2栋111室",
            "车陂",
            ["4"],
            "黄村附近优先：车陂方向，需打开来源核对具体步行距离",
            "huangcun",
            "https://www.zhaopin.com/jobdetail/CCL1524925070J40890257513.htm",
            "3-5年经验；负责信息流广告视频创意、脚本、剪辑合成和团队质量把控，双休。",
            ["车陂", "高薪", "双休", "主管"],
            "智联招聘",
            "6月18日",
            now,
        ),
        make_job(
            "job-20260703-014",
            "短视频剪辑师（中级）",
            "长沙回声网络科技有限公司",
            "7000-8000元/月",
            "剪辑",
            "广州天河区中山大道珠吉路6号佳信商务大厦7楼",
            "珠吉 / 黄村",
            ["4"],
            "黄村附近优先：珠吉方向，需打开来源核对具体地址",
            "huangcun",
            "https://www.zhaopin.com/jobdetail/CCL1522602060J40857536610.htm",
            "3-5年经验；根据素材包完成剪辑、字幕清洗、音频处理、基础调色和动画包装。",
            ["珠吉", "剪辑", "今日发布"],
            "智联招聘",
            "今日",
            now,
        ),
        make_job(
            "job-20260703-015",
            "产品摄影助理",
            "长沙回声网络科技有限公司",
            "4000-6000元/月",
            "拍摄",
            "广州天河区中山大道珠吉路6号佳信商务大厦7楼",
            "珠吉 / 黄村",
            ["4"],
            "黄村附近优先：珠吉方向，需打开来源核对具体地址",
            "huangcun",
            "https://www.zhaopin.com/jobdetail/CCL1522602060J40857284710.htm",
            "经验不限；协助产品拍摄、调色、素材整理归档，偏3C数码产品摄影助理。",
            ["摄影助理", "产品拍摄", "今日发布"],
            "智联招聘",
            "今日",
            now,
        ),
    ]


def tourism_candidate_jobs(now: str) -> list[dict]:
    return [
        make_job(
            "tourism-20260703-001",
            "销售顾问（入境游）",
            "广东华畅国际旅行社有限公司",
            "5000-10000元",
            "入境游销售",
            "广州越秀区梅花村",
            "越秀 / 杨箕方向",
            ["1", "5"],
            "从东圃、车陂可接5号线方向通勤，投递前核对具体地址",
            "nearby5",
            "https://www.zhaopin.com/jobdetail/CC445823180J40920272715.htm",
            "3-5年经验，本科；入境游销售顾问，负责人刚在线。",
            ["入境游", "销售顾问", "旅行社"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-002",
            "入境游计调",
            "广之旅",
            "8000-12000元",
            "入境游销售",
            "广州白云区棠景",
            "白云棠景",
            ["2"],
            "广州范围可投递，距离东圃/黄村较远，先核对通勤",
            "guangzhou",
            "https://www.zhaopin.com/jobdetail/CC136781110J40886618913.htm",
            "3-5年经验，本科；入境游计调，交通便利，负责人刚在线。",
            ["入境游", "计调", "广之旅"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-003",
            "定制计调员（来粤地接方向）",
            "广之旅",
            "6000-9000元",
            "入境游销售",
            "广州白云区棠景",
            "白云棠景",
            ["2"],
            "广州范围可投递，来粤地接方向，先核对通勤",
            "guangzhou",
            "https://www.zhaopin.com/jobdetail/CC136781110J40790158613.htm",
            "1-3年经验，本科；来粤地接方向定制计调，负责人刚在线。",
            ["地接", "定制计调", "广之旅"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-004",
            "旅游销售经理",
            "广州普昕酒店有限公司",
            "8000-16000元",
            "入境游销售",
            "广州天河区冼村",
            "冼村 / 猎德方向",
            ["5"],
            "天河5号线方向，东圃/车陂到冼村一线可达",
            "nearby5",
            "https://www.zhaopin.com/jobdetail/CCL1451168770J40737363816.htm",
            "3-5年经验，大专；旅游销售经理，负责人刚在线。",
            ["旅游销售", "经理", "天河"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-005",
            "旅行社销售专员",
            "五月花(广州)旅行社有限公司",
            "6000-9000元",
            "入境游销售",
            "广州天河区林和",
            "林和 / 广州东站",
            ["1", "3"],
            "天河区地铁可达，需核对从黄村/东圃通勤时间",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1246011670J40661126911.htm",
            "3-5年经验，大专；旅行社销售专员，负责人刚在线。",
            ["旅行社", "销售专员", "天河"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-006",
            "旅游产品经理（薪酬面议）",
            "广州市智能网联汽车示范区运营中心",
            "8000-12000元",
            "入境游销售",
            "广州天河区五山",
            "五山",
            ["3"],
            "天河区地铁可达，偏产品/线路方向",
            "tianhe",
            "https://www.zhaopin.com/jobdetail/CCL1386489560J40866179509.htm",
            "3-5年经验，本科；旅游产品经理，负责人刚在线。",
            ["旅游产品", "产品经理", "天河"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-007",
            "旅游业务销售",
            "广东省中国青年旅行社有限公司永泰分公司",
            "7000-8000元",
            "入境游销售",
            "广州白云区永平",
            "白云永平",
            ["3"],
            "广州范围可投递，距离东圃/黄村较远，先核对通勤",
            "guangzhou",
            "https://www.zhaopin.com/jobdetail/CCL1479577250J40849174509.htm",
            "1-3年经验；旅游业务销售，负责人刚在线。",
            ["旅游销售", "旅行社", "业务销售"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-008",
            "旅游销售",
            "广东亚太国际旅行社有限公司",
            "4000-8000元",
            "入境游销售",
            "广州越秀区人民街道",
            "越秀人民街道",
            ["6"],
            "广州范围可投递，先核对通勤和门店地址",
            "guangzhou",
            "https://www.zhaopin.com/jobdetail/CC299814580J40778114806.htm",
            "1-3年经验，大专；旅游销售，负责人刚在线。",
            ["旅游销售", "旅行社", "越秀"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-009",
            "旅游销售助理-广州",
            "MIKI TRAVEL LIMITED",
            "6000-8000元·13薪",
            "入境游销售",
            "广州越秀区人民街道",
            "越秀人民街道",
            ["6"],
            "广州范围可投递，偏入境/旅游销售助理方向",
            "guangzhou",
            "https://www.zhaopin.com/jobdetail/CC310294510J40785236106.htm",
            "3-5年经验，本科；旅游销售助理，13薪，负责人刚在线。",
            ["旅游销售助理", "13薪", "外企"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-010",
            "旅游同业销售",
            "广东亚太国际旅行社有限公司",
            "5000-9000元",
            "入境游销售",
            "广州越秀区人民街道",
            "越秀人民街道",
            ["6"],
            "广州范围可投递，同业销售方向，先核对通勤",
            "guangzhou",
            "https://www.zhaopin.com/jobdetail/CC299814580J40782549406.htm",
            "3-5年经验，大专；旅游同业销售，负责人刚在线。",
            ["同业销售", "旅行社", "旅游"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-011",
            "旅游保险顾问",
            "中国人寿保险股份有限公司广州市天河支公司",
            "1-2万",
            "入境游销售",
            "广州天河区猎德",
            "猎德",
            ["5"],
            "天河5号线方向，东圃/车陂到猎德一线可达",
            "nearby5",
            "https://www.zhaopin.com/jobdetail/CC482881230J40836551901.htm",
            "经验不限，大专；旅游保险顾问，负责人刚在线。",
            ["旅游保险", "顾问", "天河"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-012",
            "旅游顾问",
            "广东省中国青年旅行社有限公司永泰分公司",
            "5000-9000元",
            "入境游销售",
            "广州白云区永平",
            "白云永平",
            ["3"],
            "广州范围可投递，旅行社旅游顾问方向",
            "guangzhou",
            "https://www.zhaopin.com/jobdetail/CCL1479577250J40831556409.htm",
            "经验不限；旅游顾问，负责人刚在线。",
            ["旅游顾问", "旅行社", "销售"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-013",
            "旅游顾问",
            "广东亚太国际旅行社有限公司",
            "4000-8000元",
            "入境游销售",
            "广州越秀区人民街道",
            "越秀人民街道",
            ["6"],
            "广州范围可投递，旅游顾问方向，先核对通勤",
            "guangzhou",
            "https://www.zhaopin.com/jobdetail/CC299814580J40782438006.htm",
            "1-3年经验，大专；旅游顾问，负责人刚在线。",
            ["旅游顾问", "旅行社", "越秀"],
            "智联招聘",
            "本周",
            now,
        ),
        make_job(
            "tourism-20260703-014",
            "旅游顾问（门店销售员）(J10047)",
            "广之旅",
            "5000-10000元",
            "入境游销售",
            "广州白云区棠景",
            "白云棠景",
            ["2"],
            "广州范围可投递，门店销售方向，先核对通勤",
            "guangzhou",
            "https://www.zhaopin.com/jobdetail/CC136781110J40475537913.htm",
            "3-5年经验，中专/中技；门店旅游顾问，负责人刚在线。",
            ["旅游顾问", "门店销售", "广之旅"],
            "智联招聘",
            "本周",
            now,
        ),
    ]


def platform_media_candidate_jobs(now: str) -> list[dict]:
    return [
        make_platform_job(
            "boss-media-20260703-001",
            "短视频剪辑师",
            "有媒有传媒",
            "薪资以平台为准",
            "剪辑",
            "广州",
            "广州",
            [],
            "BOSS直聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.zhipin.com/job_detail/a03e4b1f1c92b6901nx42967E1VY.html",
            "短视频剪辑方向，BOSS直聘搜索结果候选。",
            ["BOSS", "短视频剪辑", "平台候选"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "boss-media-20260703-002",
            "视频剪辑师",
            "广州心合教育投资",
            "薪资以平台为准",
            "剪辑",
            "广州天河区",
            "天河",
            [],
            "BOSS直聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.zhipin.com/job_detail/e2bb6f95c959cb411nx_2du8FVVX.html",
            "视频剪辑师方向，BOSS直聘搜索结果候选。",
            ["BOSS", "视频剪辑", "天河"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "boss-media-20260703-003",
            "短视频拍摄剪辑",
            "华研外语",
            "薪资以平台为准",
            "拍摄",
            "广州",
            "广州",
            [],
            "BOSS直聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.zhipin.com/job_detail/dafee20b851fdacc1nJ429y7FVVV.html",
            "短视频拍摄剪辑方向，BOSS直聘搜索结果候选。",
            ["BOSS", "拍摄剪辑", "短视频"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "boss-media-20260703-004",
            "拍摄剪辑岗（双休）",
            "拾优科技",
            "薪资以平台为准",
            "拍摄",
            "广州",
            "广州",
            [],
            "BOSS直聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.zhipin.com/job_detail/893d7debd30b98571nN43dW6FFZZ.html",
            "拍摄剪辑岗，BOSS直聘搜索结果候选。",
            ["BOSS", "拍摄剪辑", "双休"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "boss-media-20260703-005",
            "服装摄影师-合成/静物【天河东圃地铁口】",
            "莫生气科技",
            "5-8K",
            "拍摄",
            "广州天河区东圃地铁口",
            "东圃",
            ["5"],
            "东圃地铁口，黄村/车陂方向短通勤优先",
            "nearby2",
            "https://www.zhipin.com/job_detail/a23a2b36df1ac19e1nJ52ty9E1FX.html",
            "1-3年，大专；服装静物摄影/合成方向，BOSS直聘搜索结果候选。",
            ["BOSS", "东圃", "服装摄影"],
            "BOSS直聘",
            "2天内",
            now,
        ),
        make_platform_job(
            "boss-media-20260703-006",
            "产品摄影摄像师",
            "时光量子",
            "薪资以平台为准",
            "拍摄",
            "广州天河区",
            "天河",
            [],
            "BOSS直聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.zhipin.com/job_detail/ed4622adf4387a7e1nR83N29E1FX.html",
            "产品摄影摄像师方向，BOSS直聘搜索结果候选。",
            ["BOSS", "产品摄影", "摄像"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "boss-media-20260703-007",
            "电商服装摄影师/剪辑",
            "广州曜灿明科技有限公司",
            "5-8K",
            "拍摄",
            "广州天河区天河城",
            "天河城",
            ["1", "3"],
            "天河商圈，需核对从黄村/东圃通勤",
            "tianhe",
            "https://www.zhipin.com/job_detail/30972a3aab05f6201nV_0tS6GFNY.html",
            "1-3年；电商服装摄影、剪辑方向，BOSS直聘搜索结果候选。",
            ["BOSS", "电商摄影", "剪辑"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "boss-media-20260703-008",
            "拍摄剪辑实习助理",
            "派德汽车配件",
            "薪资以平台为准",
            "拍摄",
            "广州",
            "广州",
            [],
            "BOSS直聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.zhipin.com/job_detail/e1805a13cd620c8703d83Nu9E1JS.html",
            "拍摄剪辑实习助理方向，BOSS直聘搜索结果候选。",
            ["BOSS", "实习助理", "拍摄剪辑"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "boss-media-20260703-009",
            "抖音信息流剪辑",
            "娜丽丝",
            "薪资以平台为准",
            "剪辑",
            "广州",
            "广州",
            [],
            "BOSS直聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.zhipin.com/job_detail/ebe5cef5ff1c7d5e1nx_29y9EFFW.html",
            "抖音信息流剪辑方向，BOSS直聘搜索结果候选。",
            ["BOSS", "信息流", "抖音"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "boss-media-20260703-010",
            "摄影/摄像师",
            "香云故里",
            "薪资以平台为准",
            "拍摄",
            "广州",
            "广州",
            [],
            "BOSS直聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.zhipin.com/job_detail/b744f5e62e3dcfac1nJ939S9GVJW.html",
            "摄影/摄像师方向，BOSS直聘搜索结果候选。",
            ["BOSS", "摄影摄像", "平台候选"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "liepin-media-20260703-001",
            "摄影剪辑师",
            "广东路卡服装集团有限公司",
            "10-15k",
            "拍摄",
            "广州天河区",
            "天河",
            [],
            "猎聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.liepin.com/job/1978112193.shtml",
            "3-5年，大专；摄影剪辑师，猎聘搜索结果候选。",
            ["猎聘", "摄影剪辑", "天河"],
            "猎聘",
            "今日更新",
            now,
        ),
        make_platform_job(
            "liepin-media-20260703-002",
            "视频剪辑师",
            "广州来音广告有限公司",
            "4-6k",
            "剪辑",
            "广州天河区",
            "天河",
            [],
            "猎聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.liepin.com/job/1967554207.shtml",
            "视频剪辑师方向，猎聘搜索结果候选。",
            ["猎聘", "视频剪辑", "天河"],
            "猎聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "liepin-media-20260703-003",
            "电商视频剪辑师",
            "广州电商企业",
            "薪资以平台为准",
            "剪辑",
            "广州",
            "广州",
            [],
            "猎聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.liepin.com/job/1977998665.shtml",
            "电商视频剪辑方向，猎聘搜索结果候选。",
            ["猎聘", "电商视频", "剪辑"],
            "猎聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "liepin-media-20260703-004",
            "短视频剪辑",
            "广州斯伯特生物科技有限公司",
            "8-12k",
            "剪辑",
            "广州",
            "广州",
            [],
            "猎聘候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://www.liepin.com/job/1979235723.shtml",
            "短视频剪辑方向，猎聘搜索结果候选。",
            ["猎聘", "短视频", "剪辑"],
            "猎聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "job51-media-20260703-001",
            "摄影师（会设计，双休）",
            "广东拓必拓科技股份有限公司",
            "6-8千",
            "拍摄",
            "广州天河区",
            "天河",
            [],
            "前程无忧候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://jobs.51job.com/guangzhou-thq/170970923.html",
            "摄影师方向，前程无忧搜索结果候选。",
            ["前程无忧", "摄影师", "双休"],
            "前程无忧",
            "平台候选",
            now,
        ),
        make_platform_job(
            "job51-media-20260703-002",
            "电商美工/摄影",
            "前程无忧平台企业",
            "薪资以平台为准",
            "拍摄",
            "广州",
            "广州",
            [],
            "前程无忧候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://jobs.51job.com/guangzhou/162228131.html",
            "电商美工/摄影方向，前程无忧搜索结果候选。",
            ["前程无忧", "电商摄影", "美工"],
            "前程无忧",
            "平台候选",
            now,
        ),
        make_platform_job(
            "job51-media-20260703-003",
            "短视频摄影师",
            "前程无忧平台企业",
            "薪资以平台为准",
            "拍摄",
            "广州",
            "广州",
            [],
            "前程无忧候选岗位，打开平台核对具体地址",
            "tianhe",
            "https://jobs.51job.com/guangzhou/146295269.html",
            "短视频摄影师方向，前程无忧搜索结果候选。",
            ["前程无忧", "短视频摄影", "拍摄"],
            "前程无忧",
            "平台候选",
            now,
        ),
    ]


def platform_tourism_candidate_jobs(now: str) -> list[dict]:
    return [
        make_platform_job(
            "boss-tourism-20260703-001",
            "入境游计调",
            "广之旅国际旅行社",
            "8-12K",
            "入境游销售",
            "广州白云区棠景",
            "白云棠景",
            ["2"],
            "BOSS直聘候选岗位，广州范围可投递，先核对通勤",
            "guangzhou",
            "https://www.zhipin.com/job_detail/e7cefdfb581347b11nZ509y7GVZR.html",
            "入境游计调方向，BOSS直聘搜索结果候选。",
            ["BOSS", "入境游", "计调"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "boss-tourism-20260703-002",
            "入境游OP",
            "三国国际旅行社",
            "4-6K",
            "入境游销售",
            "广州",
            "广州",
            [],
            "BOSS直聘候选岗位，打开平台核对具体地址",
            "guangzhou",
            "https://www.zhipin.com/job_detail/3a4063fe5822ce1f1nd40tS6EFdU.html",
            "1-3年；入境游OP方向，BOSS直聘搜索结果候选。",
            ["BOSS", "入境游", "OP"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "boss-tourism-20260703-003",
            "旅游定制师",
            "不遛湾",
            "10-15K",
            "入境游销售",
            "广州天河区珠江新城",
            "珠江新城",
            ["3", "5"],
            "天河5号线方向，东圃/车陂可接5号线",
            "nearby5",
            "https://www.zhipin.com/job_detail/9f03bd5717c79d711XB-29S8F1RX.html",
            "旅游定制师方向，BOSS直聘搜索结果候选。",
            ["BOSS", "旅游定制", "天河"],
            "BOSS直聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "liepin-tourism-20260703-001",
            "旅游销售总助（出境&入境定制游方向）",
            "深圳市好旅途国际旅行社有限公司广州分公司",
            "8-13k",
            "入境游销售",
            "广州越秀区",
            "越秀",
            [],
            "猎聘候选岗位，广州范围可投递，先核对通勤",
            "guangzhou",
            "https://www.liepin.com/job/1981654891.shtml",
            "出境&入境定制游方向，猎聘搜索结果候选。",
            ["猎聘", "入境定制游", "旅游销售"],
            "猎聘",
            "近期",
            now,
        ),
        make_platform_job(
            "liepin-tourism-20260703-002",
            "旅游销售",
            "Topalways Group",
            "5-10k",
            "入境游销售",
            "广州",
            "广州",
            [],
            "猎聘候选岗位，打开平台核对具体地址",
            "guangzhou",
            "https://www.liepin.com/job/1965468071.shtml",
            "旅游销售方向，猎聘搜索结果候选。",
            ["猎聘", "旅游销售", "平台候选"],
            "猎聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "liepin-tourism-20260703-003",
            "旅游产品销售",
            "广州市途喜文化传播有限公司",
            "7-8k",
            "入境游销售",
            "广州",
            "广州",
            [],
            "猎聘候选岗位，打开平台核对具体地址",
            "guangzhou",
            "https://www.liepin.com/job/1963547543.shtml",
            "旅游产品销售方向，猎聘搜索结果候选。",
            ["猎聘", "旅游产品", "销售"],
            "猎聘",
            "平台候选",
            now,
        ),
        make_platform_job(
            "liepin-tourism-20260703-004",
            "出境计调",
            "广东华畅国际旅行社有限公司",
            "6-10k",
            "入境游销售",
            "广州",
            "广州",
            [],
            "猎聘候选岗位，打开平台核对具体地址",
            "guangzhou",
            "https://www.liepin.com/job/1982161255.shtml",
            "旅行社计调方向，猎聘搜索结果候选。",
            ["猎聘", "旅行社", "计调"],
            "猎聘",
            "近期",
            now,
        ),
    ]


def build_jobs(now: str) -> tuple[list[dict], list[dict]]:
    active_jobs: list[dict] = []
    removed_jobs: list[dict] = []
    for job in candidate_jobs(now):
        ok, reason = verify_job(job)
        job["verificationReason"] = reason
        if ok:
            active_jobs.append(job)
            print(f"ACTIVE  {job['id']} {job['title']} - {reason}")
        else:
            removed_jobs.append(
                {
                    "id": job["id"],
                    "title": job["title"],
                    "company": job["company"],
                    "directLink": job["directLink"],
                    "reason": reason,
                }
            )
            print(f"REMOVED {job['id']} {job['title']} - {reason}")
    for job in filter_known_company_candidates(platform_media_candidate_jobs(now)):
        active_jobs.append(job)
        print(f"CANDIDATE {job['id']} {job['title']} - {job['source']}")
    return active_jobs, removed_jobs


def build_tourism_jobs(now: str) -> tuple[list[dict], list[dict]]:
    active_jobs: list[dict] = []
    removed_jobs: list[dict] = []
    for job in tourism_candidate_jobs(now):
        ok, reason = verify_job(job)
        job["verificationReason"] = reason
        if ok:
            active_jobs.append(job)
            print(f"ACTIVE  {job['id']} {job['title']} - {reason}")
        else:
            removed_jobs.append(
                {
                    "id": job["id"],
                    "title": job["title"],
                    "company": job["company"],
                    "directLink": job["directLink"],
                    "reason": reason,
                }
            )
            print(f"REMOVED {job['id']} {job['title']} - {reason}")
    for job in filter_known_company_candidates(platform_tourism_candidate_jobs(now)):
        active_jobs.append(job)
        print(f"CANDIDATE {job['id']} {job['title']} - {job['source']}")
    return active_jobs, removed_jobs


def write_log(now_dt: datetime, total_count: int, removed_jobs: list[dict]) -> None:
    timestamp = now_dt.strftime("%Y-%m-%d %H:%M")
    removed_text = "无"
    if removed_jobs:
        removed_text = "\n".join(
            f"- {job['title']} / {job['company']}：{job['reason']}" for job in removed_jobs
        )

    entry = f"""
## {timestamp} 自动更新

| 项目 | 数值 |
|------|------|
| 更新方式 | GitHub Actions 每日核验 |
| 数据策略 | 具体岗位卡片 + 来源页有效性检查 |
| 行业范围 | 剪辑、拍摄 |
| 保留岗位数 | {total_count} |
| 剔除岗位数 | {len(removed_jobs)} |

剔除明细：

{removed_text}

"""
    if LOG_FILE.exists():
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(entry)
    else:
        with LOG_FILE.open("w", encoding="utf-8") as f:
            f.write("# 更新日志\n\n> 记录每日自动核验 jobs.json 的结果。\n")
            f.write(entry)


def main() -> None:
    now_dt = datetime.now(TZ_GUANGZHOU)
    now = now_dt.isoformat(timespec="seconds")
    jobs, removed_jobs = build_jobs(now)
    tourism_jobs, removed_tourism_jobs = build_tourism_jobs(now)
    output = {
        "updateTime": now,
        "updateMethod": "github-actions-daily-verified-job-cards",
        "totalCount": len(jobs),
        "tourismCount": len(tourism_jobs),
        "removedCount": len(removed_jobs) + len(removed_tourism_jobs),
        "dataNote": "本站保留剪辑/拍摄岗位，并新增独立的入境游销售板块。每天自动打开具体来源页核验；无法访问、疑似下架或页面不再匹配岗位/公司的卡片会自动剔除。",
        "sources": ["BOSS直聘", "前程无忧", "智联招聘", "58同城", "猎聘"],
        "removedJobs": removed_jobs,
        "removedTourismJobs": removed_tourism_jobs,
        "jobs": jobs,
        "tourismJobs": tourism_jobs,
    }
    JOBS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_log(now_dt, len(jobs) + len(tourism_jobs), removed_jobs + removed_tourism_jobs)
    print(
        f"Updated {JOBS_FILE.name}: {len(jobs)} video/photo cards, "
        f"{len(tourism_jobs)} tourism cards, "
        f"{len(removed_jobs) + len(removed_tourism_jobs)} removed at {now}"
    )


if __name__ == "__main__":
    main()
