# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""热搜榜单 (hot search lists) for dy / bili / wb / zhihu."""
from .fetchers import FETCHERS, HotItem, fetch_hot_search

__all__ = ["FETCHERS", "HotItem", "fetch_hot_search"]
