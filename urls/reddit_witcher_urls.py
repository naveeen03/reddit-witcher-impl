from __future__ import absolute_import
from django.urls import path
from integration.views import reddit_witcher

urlpatterns = [
    path("reddit_to_haptik_adapter/", reddit_witcher.RedditToHaptikAdapter.as_view()),
    path("haptik_to_reddit_adapter/", reddit_witcher.HaptikToRedditAdapter.as_view()),
    path("send_replies/", reddit_witcher.SendRepliesAdapter.as_view()),
]
