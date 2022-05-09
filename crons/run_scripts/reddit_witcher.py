"""
Get comments from Reddit, and sends to Haptik using Haptik's API
"""
from __future__ import absolute_import

import structlog
import django
from integration.utils import reddit_witcher
from django.conf import settings

django.setup()
cron_logger = structlog.getLogger('cron')
logger = structlog.getLogger('utils')

try:
    logger.info(usecase="Get Comments", bot_name="Reddit Witcher")
    payload = {"type": "respond_comments"}
    response = reddit_witcher.RedditToHaptikAdapter.RedditToHaptikService(payload).worker()
    message = "Success"
    logger.info(
        usecase="Get Comments",
        response=response
    )
except Exception as e:
    logger.exception(f"[REDDIT_WITCHER] [RedditToHaptikAdapter] Cron Job Failure: {e}")
    message = "Failure, exception: " + str(e)

cron_logger.info(message, job_name="reddit_witcher_cron", bot_name="Reddit Witcher")
# print(message)
