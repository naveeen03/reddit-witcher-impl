import datetime
import json

import api.requests.methods as api_requests
import praw
import praw.reddit
import structlog
from django_redis import get_redis_connection
from integration.const import reddit_witcher as const

redis_cache = get_redis_connection('redis')
redis_cache.connection_pool.connection_kwargs["decode_responses"] = True
redis_cache.connection_pool.reset()

logger = structlog.getLogger("utils")


class RedditToHaptikAdapter:
    class HaptikService:
        def __init__(self):
            """
            Initializing/Login reddit account
            """
            self.r = praw.Reddit(
                client_id=const.client_id,
                client_secret=const.secret_key,
                user_agent=const.user_agent,
                username=const.username,
                password=const.password
            )

            self.bot_id = ""
            if const.username and const.password:
                self.bot_id = self.r.user.me().id
                self.bot_name = str(self.r.user.me())

            self.HEADERS = {
                "client-id": const.haptik_client_id,
                "Authorization": const.haptik_authorization
            }

        def create_user(self, payload):
            """
            Create user using Haptik API
            :param payload: {
                auth_id: str
            }
            :return:
            """
            from django.conf import settings
            if settings.HAPTIK_ENV == "production":
                create_user_url = const.haptik_create_user_url
            else:
                create_user_url = const.haptik_preprod_create_user_url
            response = api_requests.post(
                create_user_url,
                json=payload,
                headers=self.HEADERS,
                timeout=5
            )
            logger.info(
                usecase="Create User",
                class_name="RedditToHaptikAdapter",
                response=response.text,
                bot_name="Reddit Witcher"
            )
            return response

        def send_message(self, payload):
            """
            Send message to Haptik using Haptik API
            :param payload: {
                "user": {
                    "auth_id": str
                },
                "message_body": "Hi",
                "message_type": 0,
                "business_id": int
            }
            :return:
            """
            from django.conf import settings
            if settings.HAPTIK_ENV == "production":
                send_msg_url = const.haptik_send_msg_url
            else:
                send_msg_url = const.haptik_preprod_send_msg_url
            response = api_requests.post(
                send_msg_url,
                json=payload,
                headers=self.HEADERS
            )
            logger.info(
                usecase="Send Message",
                class_name="RedditToHaptikAdapter",
                response=str(response.json()),
                bot_name="Reddit Witcher"
            )
            return response

        def get_remaining_hits(self):
            """
            Checks how many hits are can be make in remaining time of 9 mins
            :return: int
            """
            remaining_hits = self.r.auth.limits["remaining"]
            return remaining_hits

        def get_create_user_payload(self, author_id):
            """
            Payload for Create User Haptik API
            :param author_id: str
            :return: Dict
            """
            return {
                "auth_id": author_id,
            }

        def get_send_message_payload(self, author_id, message):
            """
            Payload for Send Message Haptik API
            :param author_id: str
            :param message: str
            :return: Dict
            """
            return {
                "user": {
                    "auth_id": author_id
                },
                "message_body": message,
                "message_type": 0,
                "business_id": const.business_id
            }

        @staticmethod
        def get_reddit_comments_from_redis():
            """
            Get comments stored in redis cache
            :return: List of comment object

            comment object: {
                "id": str,
                "body": str,
                "author": str
            }
            """
            try:
                reddit_comments = redis_cache.get("reddit_comments")
                logger.info(
                    usecase="Get Comments",
                    class_name="RedditToHaptikAdapter",
                    reddit_comments=reddit_comments,
                    bot_name="Reddit Witcher"
                )
            except Exception as e:
                logger.info(
                    usecase="Get Comments", class_name="RedditToHaptikAdapter", exception=e, bot_name="Reddit Witcher")
            if reddit_comments:
                reddit_comments = json.loads(reddit_comments)
            else:
                reddit_comments = []
            return reddit_comments

        def validate_comment(self, comment):
            """
            Checks if comment can be replied or not.

            Validation checks:
            1. comment should not be replied already
            2. comment should not be bot break comment
            3. comment should not be made by bot
            4. comment should not be removed or deleted by any case

            This checks will be done using ids stored in redis cache
            :param comment:
            :return: bool
            """
            from praw.models import MoreComments
            if isinstance(comment, MoreComments):
                return False

            redis_key_for_answered_comment = f"reddit_answered_comment_id_{comment.id}"
            if is_redis_key_already_exists(redis_key_for_answered_comment):
                logger.info(
                    "Already Replied not sending to Haptik",
                    usecase="Validate Comment",
                    class_name="RedditToHaptikAdapter",
                    comment_id=comment.id,
                    bot_name="Reddit Witcher"
                )
                return False

            redis_key_for_bot_break_comment = f"reddit_bot_break_comment_id_{comment.id}"
            if is_redis_key_already_exists(redis_key_for_bot_break_comment):
                logger.info(
                    "Bot break comment not sending to Haptik",
                    usecase="Validate Comment",
                    class_name="RedditToHaptikAdapter",
                    comment_id=comment.id,
                    bot_name="Reddit Witcher"
                )
                return False

            is_bot_author = comment.author and str(comment.author) == self.bot_name
            if is_bot_author:
                logger.info(
                    "Bot comment",
                    usecase="Validate Comment",
                    class_name="RedditToHaptikAdapter",
                    comment_id=comment.id,
                    bot_name="Reddit Witcher"
                )
                return False

            is_comment_removed = comment.banned_by is True or \
                comment.body == "[removed]" or comment.body == '[deleted]'
            has_replied = self.bot_name in [str(re.author) for re in comment.replies if comment.author]
            if is_comment_removed or has_replied:
                logger.info(
                    "Comment is removed by moderator or Replied already",
                    usecase="Validate Comment",
                    class_name="RedditToHaptikAdapter",
                    comment_id=comment.id,
                    bot_name="Reddit Witcher"
                )
                return False
            return True

        def get_all_comments_without_stream(self, submission_id: str):
            """
            Get all comments from submission/post and sends the comment to Haptik if it is can be replied


            Get comments
                Check comment can be replied or not
                store it in redis cache

            Get all the comments from redis
                Send comment to Haptik
            Update redis cache

            :param submission_id: str
            :return: none
            """
            logger.info(usecase="Get Comments", class_name="RedditToHaptikAdapter", bot_name="Reddit Witcher")

            epoch = datetime.datetime.fromtimestamp(self.r.auth.limits["reset_timestamp"])
            duration = (epoch - datetime.datetime.now()).total_seconds()
            if self.check_rate_limit(duration):
                return

            submission = self.r.submission(submission_id)
            submission.comment_sort = "new"
            submission.comments.replace_more(limit=None)

            comments = submission.comments.list()
            logger.info(
                usecase="Get Comments",
                class_name="RedditToHaptikAdapter",
                comments=comments,
                bot_name="Reddit Witcher"
            )
            reddit_comments = self.get_reddit_comments_from_redis()
            while comments:
                for comment in comments:
                    can_be_replied = self.validate_comment(comment=comment)
                    if can_be_replied:
                        comment_dict = {
                            "id": str(comment.id),
                            "body": str(comment.body),
                            "author": str(comment.author).replace('-', '__')
                        }
                        if comment_dict not in reddit_comments:
                            reddit_comments.append(comment_dict)
                            redis_cache.set("reddit_comments", json.dumps(reddit_comments))

                epoch = datetime.datetime.fromtimestamp(self.r.auth.limits["reset_timestamp"])
                duration = (epoch - datetime.datetime.now()).total_seconds()
                if self.check_rate_limit(duration):
                    return
                comments = []
                if submission.comments.replace_more():
                    comments = submission.comments.list()
                    logger.info(
                        usecase="Get Comments",
                        class_name="RedditToHaptikAdapter",
                        comments=comments,
                        bot_name="Reddit Witcher"
                    )

            reddit_comments = self.get_reddit_comments_from_redis()
            while reddit_comments:
                comment = reddit_comments.pop(0)
                logger.info(
                    "Processing Comment", usecase="Get Comments",
                    class_name="RedditToHaptikAdapter", comment_id=comment["id"]
                )
                user_payload = self.get_create_user_payload(comment["author"] + comment["id"])
                self.create_user(user_payload)

                logger.info(
                    "Send Message", usecase="Get Comments", class_name="RedditToHaptikAdapter",
                    author=comment["author"], comment_body=comment["body"], comment_id=comment["id"],
                    bot_name="Reddit Witcher"
                )
                message_payload = self.get_send_message_payload(comment["author"] + comment["id"], comment["body"])
                response = self.send_message(message_payload)

                # caching
                message_response = response.json()
                message_id = message_response.get("message_id")
                redis_key = f"{message_id}"
                redis_cache.set(redis_key, comment["id"])
                redis_cache.set("reddit_comments", json.dumps(reddit_comments))

        def check_rate_limit(self, duration):
            """
            Checks rate limit for account
            :param duration:
            :return:
            """
            minute_in_sec = 60
            if duration < minute_in_sec or self.get_remaining_hits() < 10:
                if duration <= 0:
                    duration = minute_in_sec
                    logger.info(
                        "Handling Rate Limit",
                        usecase="Get Comments",
                        class_name="RedditToHaptikAdapter",
                        message=f"Cooling down takes duration {duration}secs",
                        bot_name="Reddit Witcher"
                    )
                    return True
            return False

    class RedditToHaptikService:
        def __init__(self, payload):
            self.payload = payload
            self.haptik_service = RedditToHaptikAdapter.HaptikService()

        def worker(self):
            """
            VERIFY AND POST THE RESPONSE TO THE REDDIT
            """
            if isinstance(self.payload, dict):
                if self.payload.get('type') == 'respond_comments':
                    logger.info(
                        usecase="Send Comments",
                        event_name="Bot Start",
                        class_name="RedditToHaptikAdapter",
                        bot_name="Reddit Witcher"
                    )
                    self.haptik_service.get_all_comments_without_stream(submission_id=const.submission_id)
                    logger.info(
                        usecase="Send Comments",
                        event_name="Bot Stop",
                        class_name="RedditToHaptikAdapter",
                        bot_name="Reddit Witcher"
                    )
                    return {"status": "success"}


class HaptikToRedditAdapter:
    class RedditService:
        def __init__(self):
            self.r = praw.Reddit(
                client_id=const.client_id,
                client_secret=const.secret_key,
                user_agent=const.user_agent,
                username=const.username,
                password=const.password
            )

        def reply_to_comment(self, comment_id: str, msg: str):
            """
            Reply to a comment

            Checks if comment is removed or deleted
            :param comment_id: str
            :param msg: str
            :return: none
            """
            comment = None
            try:
                comment = self.r.comment(id=comment_id)
                msg = msg.replace('\n', '  \n  ')
                is_comment_removed = comment.banned_by is True or \
                    comment.body == "[removed]" or comment.body == '[deleted]'
                if not is_comment_removed:
                    comment.reply(msg)
            except praw.exceptions.RedditAPIException as re:
                logger.exception(f"[REDDIT_WITCHER] [HaptikToRedditAdapter] reply_to_comment", comment=comment,
                                 comment_id=comment_id, msg=msg)
            except Exception as e:
                logger.exception(f"[REDDIT_WITCHER] [HaptikToRedditAdapter] reply_to_comment", comment=comment,
                                 comment_id=comment_id, msg=msg)

        def respond_to_user(self, payload):
            """
            LOGIC TO POST COMMENTS ON REDDIT
            """
            try:
                reply = payload.get("message", {}).get("body", {}).get("text", "")
                message_id = payload.get("user_message_info", {}).get("id")
                redis_key = f"{message_id}"
                comment_id = redis_cache.get(redis_key)

                if not comment_id:
                    return

                if reply == "" or reply == "Bot breaks" or reply == "{}":
                    return
                redis_cache.delete(redis_key)
                self.reply_to_comment(comment_id=comment_id, msg=reply)
                logger.info(
                    usecase="Reply to comment",
                    class_name="HaptikToRedditAdapter",
                    comment_id=comment_id,
                    reply=reply,
                    bot_name="Reddit Witcher"
                )
            except Exception as e:
                logger.exception('[REDDIT_WITCHER] [HaptikToRedditAdapter] Error replying to comment: {}'.format(e))
                return {
                    "status": "failed",
                    "reason": e
                }
            return {"status": "success"}

    class HaptikToRedditService:
        def __init__(self, payload):
            self.payload = payload
            self.reddit_service = HaptikToRedditAdapter.RedditService()

        def worker(self):
            """
            VERIFY AND POST THE RESPONSE OT THE REDDIT
            """
            if isinstance(self.payload, dict):
                if self.payload.get('event_name') == 'message':
                    self.reddit_service.respond_to_user(self.payload)

        def worker_v2(self):
            """
            Replies to comments, and the ids to answered category in redis cache
            :return:
            """
            comment_ids = self._get_comment_ids_from_redis()
            replied_comment_ids = []
            for comment_id in comment_ids:
                redis_key_for_answered_comment = f"reddit_answered_comment_id_{comment_id}"

                if is_redis_key_already_exists(redis_key_for_answered_comment):
                    logger.info(
                        "Already Replied",
                        usecase="Reply to comment",
                        class_name="HaptikToRedditAdapter",
                        comment_id=comment_id,
                        bot_name="Reddit Witcher"
                    )
                    continue

                try:
                    redis_cache.set(redis_key_for_answered_comment, "yes", 1800)  # Expiry of 30 min
                    self.send_replies(comment_id=comment_id)
                except Exception as e:
                    logger.exception("[REDDIT_WITCHER] [HaptikReddit] Unable to reply to comment",
                                     comment_id=comment_id, exception=e)
                redis_cache.delete(comment_id)
                replied_comment_ids.append(comment_id)

            redis_cache.set("comment_ids", json.dumps([]))

        @staticmethod
        def _get_comment_ids_from_redis():
            comment_ids = []
            try:
                comment_ids = json.loads(redis_cache.get("comment_ids"))
                return comment_ids
            except Exception as e:
                logger.exception("[REDDIT_WITCHER] [SendReplies]"
                            + f" Getting Comments from Redis, Exception: {e}"
                            + " Ignore if there are no Comments")
                return comment_ids

        @staticmethod
        def _get_replies_for_comment(comment_id: str):
            """
            Get reply msgs for comment from redis
            :param comment_id:
            :return: List of replies
            """
            replies = []
            try:
                replies = json.loads(redis_cache.get(comment_id))
                return replies
            except Exception as e:
                logger.exception(f"[REDDIT_WITCHER] [SendReplies] Getting Replies from Redis, Exception: {e}"
                            + " Ignore if there are no replies")
                return replies

        def send_replies(self, comment_id: str):
            """
            Send Replies to comment

            Getting reply msg from redis cache
            :param comment_id: str
            :return: none
            """
            replies = self._get_replies_for_comment(comment_id=comment_id)

            replied_msgs = []
            for reply in replies:
                if reply in replied_msgs:
                    continue
                self.reddit_service.reply_to_comment(comment_id=comment_id, msg=reply)
                replied_msgs.append(reply)
                logger.info(
                    'Replied to comment',
                    usecase="Send Replies",
                    class_name="HaptikToRedditAdapter",
                    comment_id=comment_id,
                    reply=reply,
                    bot_name="Reddit Witcher"
                )
                return


def is_redis_key_already_exists(redis_key_for_answered_comment):
    """
    Checks the key is present in the redis cache
    :param redis_key_for_answered_comment: str
    :return: bool
    """
    redis_value_for_answered_comment = redis_cache.get(redis_key_for_answered_comment)
    if redis_value_for_answered_comment and redis_value_for_answered_comment == "yes":
        return True
    return False
