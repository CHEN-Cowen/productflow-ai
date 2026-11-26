"""渠道策略模板。

为 douyin / xiaohongshu / taobao 提供差异化策略，无专属模板时回退到 generic，
不因缺少模板让整个策划流程失败（任务书 §7.4）。
"""
from __future__ import annotations

from typing import Any

CHANNEL_TEMPLATES: dict[str, dict[str, Any]] = {
    "douyin": {
        "channel": "抖音",
        "content_positioning": "短平快，前 3 秒抓注意力，强节奏高完播",
        "expression_strategy": "口语化、直接、配合热门话题与 BGM 卡点",
        "cta": "点击小黄车 / 评论区扣 1 领券",
        "video_constraints": {"duration_min": 10, "duration_max": 15, "aspect_ratio": "9:16"},
    },
    "xiaohongshu": {
        "channel": "小红书",
        "content_positioning": "种草分享、真实体验感、封面高颜值",
        "expression_strategy": "闺蜜式分享、实用干货、笔记式短句 + emoji",
        "cta": "关注收藏 / 评论区问链接",
        "video_constraints": {"duration_min": 10, "duration_max": 15, "aspect_ratio": "3:4"},
    },
    "taobao": {
        "channel": "淘宝",
        "content_positioning": "卖点清晰、参数可信、突出性价比与细节",
        "expression_strategy": "卖点前置、规格化表达、突出材质与尺寸细节",
        "cta": "立即加购 / 领券下单",
        "video_constraints": {"duration_min": 10, "duration_max": 15, "aspect_ratio": "1:1"},
    },
    "generic": {
        "channel": "通用",
        "content_positioning": "商品价值清晰、卖点有据可依",
        "expression_strategy": "通用营销表达，突出核心卖点",
        "cta": "了解更多 / 立即选购",
        "video_constraints": {"duration_min": 10, "duration_max": 15, "aspect_ratio": "9:16"},
    },
}


_ALIASES = {
    "douyin": "douyin", "抖音": "douyin",
    "xiaohongshu": "xiaohongshu", "小红书": "xiaohongshu",
    "taobao": "taobao", "淘宝": "taobao",
    "generic": "generic", "通用": "generic", "": "generic",
}


def resolve(channel: str) -> dict[str, Any]:
    """按渠道名解析模板；支持中英文别名，未知渠道回退通用模板。"""
    raw = (channel or "").strip()
    key = _ALIASES.get(raw) or _ALIASES.get(raw.lower()) or "generic"
    return CHANNEL_TEMPLATES[key]


def supported() -> list[str]:
    return list(CHANNEL_TEMPLATES.keys())
