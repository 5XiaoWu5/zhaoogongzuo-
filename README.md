# 广州天河黄村附近 · 剪辑/拍摄/装修工作汇总

[![每日自动更新](https://github.com/{{username}}/{{repo}}/actions/workflows/update-jobs.yml/badge.svg)](https://github.com/{{username}}/{{repo}}/actions)

📌 自动搜集广州天河区黄村附近（含车陂/东圃/三溪/大观南路）的剪辑、拍摄、装修类工作岗位。

## ✨ 特性

- 🕐 **每日自动更新** — GitHub Actions 每天8:00/18:00 自动搜集最新岗位
- 📍 **精准定位** — 按黄村地铁站距离分级显示（步行可达 → 1-2站 → 2-3站）
- 🏷️ **分类筛选** — 剪辑 / 摄影摄像 / 装修施工 一键筛选
- 🗺️ **地图定位** — 每个岗位带高德地图直达链接
- 🔗 **多平台投递** — 直达招聘页面 + BOSS直聘 + 前程无忧搜索入口
- 📱 **手机友好** — 响应式设计，手机/电脑均可浏览

## 🚀 快速部署

### 最简单方式（Netlify，5分钟）

1. 打开 https://app.netlify.com/drop
2. 把 `index.html` 和 `jobs.json` 拖进去
3. 获得网址 ✅

### 推荐方式（GitHub Pages + 自动更新）

1. 把整个文件夹上传到 GitHub 仓库
2. Settings → Pages → 选择 main 分支 → Save
3. GitHub Actions 自动每日更新数据 📊

## 📂 文件说明

```
├── index.html          # 网站主页
├── jobs.json           # 岗位数据（JSON格式，自动更新）
├── update_jobs.py      # 自动更新脚本
├── update_log.md       # 更新日志
├── 部署教程.html       # 详细部署教程
├── 网站部署上线教程.docx  # Word版部署教程
└── .github/
    └── workflows/
        └── update-jobs.yml  # GitHub Actions 定时任务
```

## 🔧 手动更新

```bash
python update_jobs.py
```

会自动搜索最新岗位并更新 `jobs.json`。

## ⚠️ 免责声明

- 岗位信息来源于公开招聘平台，仅供参考
- 求职请自行核实公司信息和岗位真实性
- 切勿缴纳任何费用，谨防招聘诈骗
