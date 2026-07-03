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
    return f"https://sou.zhaopin.com/?jl=765&kw={quote(keyword)}"


def boss_mobile_search(keyword: str) -> str:
    return f"https://m.zhipin.com/gz/job/?query={quote(keyword)}"


def job51_mobile_search(keyword: str) -> str:
    return f"https://m.51job.com/search/joblist.php?keyword={quote(keyword)}&jobarea=030200"


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
        },
        "mobilePlatformLinks": {
            "direct": zhilian_mobile_link(direct_link),
            "boss": boss_mobile_search(search_keyword),
            "51job": job51_mobile_search(search_keyword),
            "zhilian": zhilian_mobile_link(direct_link),
        },
        "miniProgramLinks": {
            "direct": "",
            "boss": "",
            "51job": "",
            "zhilian": "",
        },
    }


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
    output = {
        "updateTime": now,
        "updateMethod": "github-actions-daily-verified-job-cards",
        "totalCount": len(jobs),
        "removedCount": len(removed_jobs),
        "dataNote": "本站仅保留剪辑/拍摄行业。每次自动更新都会打开来源页核验；无法访问、疑似下架、或页面不再匹配岗位/公司的卡片会自动剔除。",
        "sources": ["智联招聘", "BOSS直聘搜索", "前程无忧搜索"],
        "removedJobs": removed_jobs,
        "jobs": jobs,
    }
    JOBS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_log(now_dt, len(jobs), removed_jobs)
    print(
        f"Updated {JOBS_FILE.name}: {len(jobs)} active job cards, "
        f"{len(removed_jobs)} removed at {now}"
    )


if __name__ == "__main__":
    main()
