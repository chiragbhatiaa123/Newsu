import tweepy
import logging
from datetime import datetime, timedelta, timezone
from src.config import X_CONSUMER_KEY, X_CONSUMER_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET

logger = logging.getLogger(__name__)

def get_twitter_client():
    if not all([X_CONSUMER_KEY, X_CONSUMER_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]):
        logger.warning("X API keys are missing.")
        return None

    try:
        client = tweepy.Client(
            consumer_key=X_CONSUMER_KEY,
            consumer_secret=X_CONSUMER_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET
        )
        return client
    except Exception as e:
        logger.error(f"Failed to create X client: {e}")
        return None

def get_trending_news(query="India"):
    """
    Simulated trending news fetcher. 
    Real implementation requires paid API for Trends or Search.
    We will try to search for recent popular tweets if possible, 
    otherwise returning a placeholder or falling back.
    """
    client = get_twitter_client()
    if not client:
        return []

    try:
        # Search for recent tweets with the query
        # Note: 'recent' search helps find what's happening now
        response = client.search_recent_tweets(
            query=f"{query} lang:en -is:retweet is:verified",
            max_results=10,
            tweet_fields=['created_at', 'public_metrics', 'author_id']
        )
        
        if not response.data:
            return []

        news_items = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)
        
        for tweet in response.data:
            # Check age
            if tweet.created_at < cutoff_time:
                continue

            # Simple filter for "major" based on metrics if available, 
            # but basic search might not return metrics for all tiers.
            # We'll just take the verified tweets.
            item = {
                'title': tweet.text,
                'link': f"https://twitter.com/user/status/{tweet.id}",
                'published': tweet.created_at.isoformat(),
                'source': 'X (Twitter)'
            }
            news_items.append(item)
            
        return news_items

    except Exception as e:
        logger.error(f"Error fetching from X: {e}")
        return []
