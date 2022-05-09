from __future__ import absolute_import
from django.conf import settings

haptik_preprod_create_user_url = "https://us-messenger.hellohaptik.com/v1.0/user/"
haptik_preprod_send_msg_url = "https://us-messenger.hellohaptik.com/v1.0/log_message_from_user/"

haptik_create_user_url = "https://us-messenger.haptikapi.com/v1.0/user/"
haptik_send_msg_url = "https://us-messenger.haptikapi.com/v1.0/log_message_from_user/"

haptik_authorization = settings.REDDIT_WITCHER_AUTH_KEY
haptik_client_id = settings.REDDIT_WITCHER_HAPTIK_CLIENT_ID
business_id = settings.REDDIT_WITCHER_HAPTIK_BUSINESS_ID

client_id = settings.REDDIT_WITCHER_CLIENT_ID
secret_key = settings.REDDIT_WITCHER_SECRET_KEY
user_agent = settings.REDDIT_WITCHER_USER_AGENT
username = settings.REDDIT_WITCHER_USERNAME
password = settings.REDDIT_WITCHER_PASSWORD
submission_id = settings.REDDIT_WITCHER_SUBMISION_ID