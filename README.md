# 广州天河黄村附近 · 剪辑/拍摄工作

[![每日自动更新](https://github.com/5XiaoWu5/zhaoogongzuo-/actions/workflows/update-jobs.yml/badge.svg)](https://github.com/5XiaoWu5/zhaoogongzuo-/actions/workflows/update-jobs.yml)

面向广州天河区黄村、车陂、东圃、三溪、大观南路附近的剪辑、摄影摄像求职信息。

## 特点

- 每日核验：GitHub Actions 每天 08:00 和 18:00（北京时间）打开岗位来源页检查有效性
- 行业收窄：已删除装修施工，只保留视频剪辑、摄影摄像
- 具体岗位：下面的卡片展示公司、岗位、薪资、地点和来源链接
- 自动剔除：无法访问、疑似下架、或来源页不再匹配岗位/公司的卡片不会继续展示
- 风险提示：投递前请确认岗位仍在招，不要缴纳任何费用

## 文件说明

```text
index.html          # 网站首页
jobs.json           # 每日生成的具体岗位数据
update_jobs.py      # 生成 jobs.json 的脚本
update_log.md       # 每日更新日志
.github/workflows/update-jobs.yml  # GitHub Actions 定时任务
```

## 手动更新

```bash
python update_jobs.py
```

## 免责声明

岗位详情、薪资、公司信息和在招状态以招聘平台页面为准。求职请自行核实公司和岗位真实性，不要缴纳任何费用。
