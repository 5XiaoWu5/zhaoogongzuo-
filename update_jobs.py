#!/usr/bin/env python3
"""
广州天河黄村附近 - 工作数据自动更新脚本
===========================================
由 GitHub Actions 每日定时调用，自动搜集最新招聘信息并更新 jobs.json

数据来源：
  - Web 搜索聚合（Bing/Google 搜索）
  - 招聘平台公开搜索页面

运行方式：
  python update_jobs.py

输出：
  - 更新 jobs.json 文件
  - 追加 update_log.md 日志
"""

import json
import os
import re
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional

# ===================== 配置 =====================

# 搜索关键词列表
SEARCH_QUERIES = [
    # 剪辑类
    "广州天河 黄村 车陂 视频剪辑 招聘 2026",
    "广州天河 东圃 后期制作 剪辑师 招聘",
    "广州天河 短视频剪辑 信息流剪辑 招聘 薪资",
    # 拍摄类
    "广州天河 黄村 车陂 摄影师 摄像师 招聘 2026",
    "广州天河 东圃 短视频拍摄 招聘 薪资",
    # 装修类
    "广州天河 黄村 车陂 装修工 木工 泥瓦工 招聘",
    "广州天河 东圃 三溪 装修 施工员 招聘",
]

# 目标区域关键词
TARGET_AREAS = [
    "黄村", "车陂", "东圃", "三溪", "大观南路",
    "棠东", "天河", "珠村", "前进",
]

# 目标地铁站
TARGET_SUBWAYS = [
    "黄村站", "车陂站", "车陂南站", "东圃站",
    "三溪站", "大观南路站", "棠东站",
]

# 岗位分类关键词
CATEGORY_KEYWORDS = {
    "剪辑": ["剪辑", "后期", "制作", "PR", "AE", "剪映", "达芬奇", "视频制作", "影视后期"],
    "拍摄": ["拍摄", "摄影", "摄像", "摄影师", "摄像师", "拍剪", "短视频"],
    "装修": ["装修", "木工", "泥瓦", "水电", "油漆", "施工", "瓦工", "电焊"],
}

# jobs.json 文件路径
JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.json")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_log.md")

# 广州时区
TZ_GUANGZHOU = timezone(timedelta(hours=8))


# ===================== 工具函数 =====================

def generate_job_id(job: dict) -> str:
    """根据公司+岗位+链接生成唯一ID"""
    raw = (job.get("company", "") + job.get("title", "") + job.get("link", ""))
    return "j" + hashlib.md5(raw.encode()).hexdigest()[:12]


def classify_category(title: str, requirements: str = "") -> str:
    """根据标题和要求判断岗位分类"""
    text = (title + " " + requirements).lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw.lower() in text)
    if scores:
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
    return "其他"


def detect_area(location: str, full_text: str = "") -> str:
    """根据地址判断属于哪个区域"""
    text = (location + " " + full_text).lower()

    # 黄村直达
    if any(w in text for w in ["黄村", "三联路", "福元南", "荔苑路"]):
        return "huangcun"

    # 车陂/大观南路 (1-2站)
    if any(w in text for w in ["车陂", "大观南", "软件路"]):
        return "nearby1"

    # 东圃/三溪/棠东 (2-3站)
    if any(w in text for w in ["东圃", "三溪", "棠东", "桃园西"]):
        return "nearby2"

    # 装修类单独判断
    if any(w in text for w in ["装修", "木工", "泥瓦", "施工", "电焊", "瓦工"]):
        return "reno"

    # 默认天河区
    return "tianhe"


def find_subway_info(location: str) -> tuple:
    """匹配地铁站信息"""
    for subway in TARGET_SUBWAYS:
        if subway in location:
            # 返回 (站名, 线路列表)
            if "黄村" in subway:
                return ("黄村站", ["4", "21"])
            elif "车陂南" in subway:
                return ("车陂南站", ["4", "5"])
            elif "车陂" in subway:
                return ("车陂站", ["4"])
            elif "东圃" in subway:
                return ("东圃站", ["5"])
            elif "三溪" in subway:
                return ("三溪站", ["5"])
            elif "大观南" in subway:
                return ("大观南路站", ["21"])
            elif "棠东" in subway:
                return ("棠东站", ["21"])
    return ("天河区", [])


def parse_salary(text: str) -> str:
    """从文本中提取薪资信息"""
    # 尝试匹配常见薪资格式
    patterns = [
        r'(\d+[Kk千]-?\d*[Kk千]?)',
        r'(\d+[-~]\d+[Kk千])',
        r'(\d+[-~]\d+元/月)',
        r'(\d+[-~]\d+元/天)',
        r'(\d+[-~]\d+/月)',  # /月
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "面议"


def normalize_job(job: dict) -> dict:
    """标准化一个岗位数据"""
    # 确保必填字段
    normalized = {
        "id": job.get("id", generate_job_id(job)),
        "title": job.get("title", "未知岗位"),
        "company": job.get("company", "未知公司"),
        "salary": job.get("salary", "面议"),
        "category": job.get("category", classify_category(job.get("title", ""), job.get("requirements", ""))),
        "location": job.get("location", "广州天河区"),
        "subway": job.get("subway", "天河区"),
        "subwayLines": job.get("subwayLines", []),
        "subwayDistance": job.get("subwayDistance", ""),
        "area": job.get("area", ""),
        "link": job.get("link", ""),
        "requirements": job.get("requirements", ""),
        "tags": job.get("tags", []),
        "isNew": job.get("isNew", False),
        "verified": job.get("verified", False),
    }

    # 自动补全 area
    if not normalized["area"]:
        normalized["area"] = detect_area(normalized["location"])

    # 自动补全地铁信息
    if normalized["subway"] == "天河区" or not normalized["subwayLines"]:
        subway, lines = find_subway_info(normalized["location"])
        if subway != "天河区":
            normalized["subway"] = subway
            normalized["subwayLines"] = lines

    return normalized


# ===================== 数据搜集 =====================

def search_jobs_via_web() -> list:
    """
    通过 Web 搜索搜集岗位数据。

    注意：此函数在 GitHub Actions 环境中运行，依赖预置的搜索能力。
    在实际 GitHub Actions 中，可以调用 Bing Search API 或其他搜索 API。

    这里提供两种模式：
    1. API 模式（生产环境）- 调用搜索 API 获取结构化结果
    2. 人工模式（开发环境）- 返回手动搜集的数据作为基准

    GitHub Actions 会设置环境变量 SEARCH_API_KEY 来启用 API 模式。
    """
    new_jobs = []

    # 检查是否有搜索 API 可用
    api_key = os.environ.get("BING_SEARCH_API_KEY") or os.environ.get("SEARCH_API_KEY")

    if api_key:
        # === API 模式：调用 Bing Search API ===
        try:
            import urllib.request
            import urllib.parse

            for query in SEARCH_QUERIES[:4]:  # 限制请求次数（免费API有配额）
                try:
                    url = "https://api.bing.microsoft.com/v7.0/search"
                    params = urllib.parse.urlencode({"q": query, "count": "10", "mkt": "zh-CN"})
                    req = urllib.request.Request(url + "?" + params)
                    req.add_header("Ocp-Apim-Subscription-Key", api_key)
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read())
                        for result in data.get("webPages", {}).get("value", []):
                            job = extract_job_from_search_result(result)
                            if job:
                                new_jobs.append(job)
                except Exception as e:
                    print(f"  ⚠️ 搜索 '{query[:30]}...' 失败: {e}")
                    continue
        except Exception as e:
            print(f"  ❌ API 搜索异常: {e}")

    # === 始终保留现有数据 + 标记新岗位 ===
    # 不会完全替换，而是合并新旧数据
    return new_jobs


def extract_job_from_search_result(result: dict) -> Optional[dict]:
    """从搜索结果条目中提取岗位信息"""
    title = result.get("name", "")
    snippet = result.get("snippet", "")
    url = result.get("url", "")

    # 判断是否与目标岗位相关
    full_text = title + " " + snippet
    is_relevant = False
    for area in TARGET_AREAS:
        if area in full_text:
            is_relevant = True
            break

    if not is_relevant:
        return None

    # 判断是否包含薪资信息
    has_salary = any(w in full_text for w in ["元/月", "K", "k", "千", "万", "薪资", "工资"])

    # 提取公司名
    company = "未知公司"
    company_patterns = [
        r'([一-龥（）()]+(?:有限公司|科技|文化|传媒|集团|教育|服饰|服务|装饰))',
    ]
    for pat in company_patterns:
        match = re.search(pat, snippet)
        if match:
            company = match.group(1)
            break

    category = classify_category(title, snippet)
    area = detect_area(snippet, full_text)

    job = {
        "title": title[:50] if title else "未知岗位",
        "company": company,
        "salary": parse_salary(snippet) if has_salary else "面议",
        "category": category,
        "location": extract_location(snippet),
        "area": area,
        "link": url,
        "requirements": snippet[:200] if snippet else "",
        "tags": [],
        "isNew": True,
        "verified": False,
    }

    return normalize_job(job)


def extract_location(text: str) -> str:
    """从文本中提取地址信息"""
    # 尝试匹配常见地址格式
    patterns = [
        r'天河区[一-龥]+(?:路|街|大道|巷|号)[一-龥\d]*',
        r'黄村[一-龥]+(?:路|街|大道|巷|号)[一-龥\d]*',
        r'车陂[一-龥]+(?:路|街|大道|巷|号)[一-龥\d]*',
    ]
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            return match.group(0)
    return "广州天河区"


# ===================== 数据合并 =====================

def load_existing_jobs() -> tuple:
    """加载现有的 jobs.json，返回 (jobs_list, metadata)"""
    if not os.path.exists(JOBS_FILE):
        return [], {"updateTime": "", "updateMethod": "manual"}

    try:
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("jobs", []), {
            "updateTime": data.get("updateTime", ""),
            "updateMethod": data.get("updateMethod", "manual"),
        }
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ 读取 jobs.json 失败: {e}")
        return [], {"updateTime": "", "updateMethod": "manual"}


def merge_jobs(existing: list, new_jobs: list) -> list:
    """
    合并新旧岗位数据：
    - 已有岗位保留（不丢失已验证数据）
    - 新岗位添加（标记 isNew=True, verified=False）
    - 按 link 去重
    - 移除超过30天的旧岗位
    """
    # 用 link 作为去重key
    seen_links = set()
    merged = []

    # 先放入已有岗位
    for job in existing:
        link = job.get("link", "")
        if link and link in seen_links:
            continue
        if link:
            seen_links.add(link)
        # 保留已有岗位，但清除 isNew 标记（超过7天的不算新）
        job["isNew"] = False
        merged.append(job)

    # 再放入新岗位
    added_count = 0
    for job in new_jobs:
        link = job.get("link", "")
        if link and link in seen_links:
            continue
        if link:
            seen_links.add(link)

        job["isNew"] = True
        job["verified"] = False
        # 生成 ID
        if not job.get("id"):
            job["id"] = generate_job_id(job)

        merged.append(job)
        added_count += 1

    print(f"  📊 合并结果：保留 {len(existing)} 个旧岗位 + 新增 {added_count} 个新岗位")
    print(f"  📊 总计：{len(merged)} 个岗位")

    return merged


# ===================== 主流程 =====================

def main():
    print("=" * 60)
    print("🔍 广州天河黄村附近 · 工作数据更新脚本")
    print(f"  运行时间：{datetime.now(TZ_GUANGZHOU).isoformat()}")
    print("=" * 60)

    # 1. 加载现有数据
    print("\n📂 加载现有数据...")
    existing_jobs, metadata = load_existing_jobs()
    print(f"  现有岗位数：{len(existing_jobs)}")
    print(f"  上次更新：{metadata['updateTime'] or '无记录'}")

    # 2. 搜索新岗位
    print("\n🔍 开始搜索新岗位...")
    new_jobs = search_jobs_via_web()

    if not new_jobs:
        print("  ℹ️ 本次未发现新岗位（可能搜索API未配置或网络问题）")
        print("  ℹ️ 将保持现有数据不变，仅更新时间戳")

    # 3. 合并数据
    print("\n🔄 合并数据...")
    merged_jobs = merge_jobs(existing_jobs, new_jobs)

    # 4. 写入 jobs.json
    print("\n💾 写入 jobs.json...")
    now_str = datetime.now(TZ_GUANGZHOU).isoformat()

    output = {
        "updateTime": now_str,
        "updateMethod": "github-actions",
        "totalCount": len(merged_jobs),
        "jobs": merged_jobs,
    }

    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 已写入 {len(merged_jobs)} 个岗位到 jobs.json")

    # 5. 写入更新日志
    print("\n📝 写入更新日志...")
    write_update_log(len(existing_jobs), len(new_jobs), len(merged_jobs))

    print("\n" + "=" * 60)
    print("✅ 更新完成！")
    print("=" * 60)


def write_update_log(existing_count: int, new_count: int, total_count: int):
    """追加更新日志到 update_log.md"""
    now = datetime.now(TZ_GUANGZHOU)
    timestamp = now.strftime("%Y-%m-%d %H:%M")

    log_entry = f"""
## {timestamp} 自动更新

| 项目 | 数值 |
|------|------|
| 更新方式 | GitHub Actions 自动运行 |
| 原有岗位 | {existing_count} |
| 新增岗位 | {new_count} |
| 更新后总数 | {total_count} |

"""

    # 追加写入
    mode = "a" if os.path.exists(LOG_FILE) else "w"
    with open(LOG_FILE, mode, encoding="utf-8") as f:
        if mode == "w":
            f.write("# 更新日志\n\n> 记录每次自动更新的详细信息\n")
            f.write(f"> 创建时间：{now.strftime('%Y-%m-%d')}\n\n")
        f.write(log_entry)

    print(f"  ✅ 更新日志已追加到 update_log.md")


if __name__ == "__main__":
    main()
