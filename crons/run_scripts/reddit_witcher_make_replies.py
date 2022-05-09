"""
Send replies stored in Redis to Reddit
"""
from __future__ import absolute_import

import django
import structlog
from integration.utils import reddit_witcher
from django.conf import settings
from django_redis import get_redis_connection

django.setup()
logger = structlog.getLogger('utils')

redis_cache = get_redis_connection('redis')
redis_cache.connection_pool.connection_kwargs["decode_responses"] = True
redis_cache.connection_pool.reset()


try:
    logger.info("Replying to comments started", usecase="Send Replies", bot_name='Reddit Witcher')
    reddit_witcher.HaptikToRedditAdapter.HaptikToRedditService(payload={}).worker_v2()
    resp = {'message': "success"}
except Exception as e:
    logger.exception(f"[REDDIT_WITCHER] [HaptikReddit] reddit_witcher_make_replies failed", exception=e)
