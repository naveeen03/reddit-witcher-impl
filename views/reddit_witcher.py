import json

import structlog
# Import Django Modules
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_redis import get_redis_connection
from integration.utils import reddit_witcher
from integration.views.base_integration import IntegrationBaseClass

redis_cache = get_redis_connection('redis')
redis_cache.connection_pool.connection_kwargs["decode_responses"] = True
redis_cache.connection_pool.reset()

logger = structlog.getLogger('utils')


@method_decorator(csrf_exempt, name='dispatch')
class RedditToHaptikAdapter(IntegrationBaseClass):
    def post(self, request):
        """
        Not in use (only used in testing)
        Send comments from Reddit to Haptik

        Args:
            request (django.http.HttpRequest): Django http request.

        Returns:
            django.http.HttpResponse: Django http response.

        """
        message = ""
        status_code = 200
        try:
            logger.info(usecase="Reddit To Haptik", request_body=json.loads(request.body), bot_name="Reddit Witcher")
            response = {}
            response = reddit_witcher.RedditToHaptikAdapter.RedditToHaptikService(json.loads(request.body)).worker()
            resp = {'message': response}
            return JsonResponse(resp, status=status_code)
        except Exception as e:
            logger.exception(
                "[REDDIT_WITCHER] [RedditToHaptikAdapter] System error occurred: {}".format(e)
            )
            message = f'System error occurred: {e}'
            resp = {'message': "[REDDIT_WITCHER] [RedditToHaptikAdapter] {}".format(message)}
            return JsonResponse(resp, status=status_code)


@method_decorator(csrf_exempt, name='dispatch')
class HaptikToRedditAdapter(IntegrationBaseClass):
    def post(self, request):
        """
        Gets Bot Responses from Haptik
        Checks bot breaks and store comment object in Redis

        Args:
            request (django.http.HttpRequest): Django http request.

        Returns:
            django.http.HttpResponse: Django http response.

        """

        status_code = 200
        try:
            logger.info(usecase="Haptik To Reddit", Response=str(json.loads(request.body)), bot_name="Reddit Witcher")
            response = {}
            req_body = json.loads(request.body)
            message_id = req_body.get("user_message_info", {}).get("id")
            comment_id = redis_cache.get(str(message_id))
            reply = req_body.get("message", {}).get("body", {}).get("text", "")
            if reply != "" and reply != "Bot breaks" and reply != "{}":
                replies = redis_cache.get(comment_id)
                if replies:
                    replies = json.loads(replies)
                    replies.append(reply)
                else:
                    replies = [reply]
                redis_cache.set(comment_id, json.dumps(replies))

                comment_ids = redis_cache.get("comment_ids")
                if comment_ids:
                    comment_ids = json.loads(comment_ids)
                    if comment_id not in comment_ids:
                        comment_ids.append(comment_id)
                else:
                    comment_ids = [comment_id]
                redis_cache.set("comment_ids", json.dumps(comment_ids))

            if reply == "Bot breaks":
                redis_key_for_answered_comment = f"reddit_bot_break_comment_id_{comment_id}"
                redis_cache.set(redis_key_for_answered_comment, "yes", 2592000)  # Expiry of 1 month
                logger.info(usecase="Haptik To Reddit", comment_id=comment_id, bot_name="Reddit Witcher")

            resp = {'message': response}
            return JsonResponse(resp, status=status_code)
        except Exception as e:
            logger.exception(
                "[REDDIT_WITCHER] [HaptikToRedditAdapter] System error occurred: {}".format(e)
            )
            message = f'System error occurred: {e}'
            resp = {'message': "[REDDIT_WITCHER] [HaptikToRedditAdapter] {}".format(message)}
            return JsonResponse(resp, status=status_code)


@method_decorator(csrf_exempt, name='dispatch')
class SendRepliesAdapter(IntegrationBaseClass):
    def post(self, request):
        """
        Sends replies from haptik to reddit
        Sends comments stored in Redis to Reddit

        Args:
            request (django.http.HttpRequest): Django http request.

        Returns:
            django.http.HttpResponse: Django http response.

        """

        status_code = 200
        try:
            logger.info(usecase="Send Replies", bot_name="Reddit Witcher")
            reddit_witcher.HaptikToRedditAdapter.HaptikToRedditService(payload={}).worker_v2()
            resp = {'message': "success"}
            return JsonResponse(resp, status=status_code)
        except Exception as e:
            logger.exception(
                "[REDDIT_WITCHER] [SendRepliesAdapter] System error occurred: {}".format(e)
            )
            resp = {
                'message': "[REDDIT_WITCHER] [SendRepliesAdapter] System error occurred: {}".format(e)
            }
            return JsonResponse(resp, status=status_code)
