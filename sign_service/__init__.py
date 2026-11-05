# -*- coding: utf-8 -*-
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
"""
Signing service (签名服务).

Signature logic for platforms that can be signed without a browser
(xhs, dy, zhihu) is exposed behind one interface. By default crawlers sign
in-process; set ``SIGN_SRV_URL`` (or env ``MC_SIGN_SRV_URL``) to send signing
requests to a separately deployed service instead::

    uv run uvicorn sign_service.server:app --host 0.0.0.0 --port 8989

This lets several crawler processes / machines share one place where the
signing code is updated when a platform changes its algorithm.
"""
