# from __future__ import print_function
import argparse
import json
import datetime
import logging as log
from time import sleep
from concurrent.futures import ThreadPoolExecutor

try:
    from urllib.parse import urlparse, urlencode, urlunparse
except ImportError:
    # Python 2 imports
    from urlparse import urlparse, urlunparse
    from urllib import urlencode

import requests
from abc import ABCMeta
from bs4 import BeautifulSoup

import pandas as pd

__author__ = 'Tom Dickinson'
__modifier__ = 'Karyna Avramenko'


class TwitterSlicer(object):

    __meta__ = ABCMeta

    def __init__(self, rate_delay, error_delay, since, until, path, language, n_threads=1):
        self.rate_delay = rate_delay
        self.error_delay = error_delay
        self.since = datetime.datetime.strptime(since, "%Y-%m-%d")
        self.until = datetime.datetime.strptime(until, "%Y-%m-%d")
        self.path = path
        self.language = language
        self.n_threads = n_threads
        self.counter = 0

    def search(self, query):
        n_days = (self.until - self.since).days
        tp = ThreadPoolExecutor(max_workers=self.n_threads)
        for i in range(0, n_days):
            since_query = self.since + datetime.timedelta(days=i)
            until_query = self.since + datetime.timedelta(days=(i + 1))
            day_query = "%s since:%s until:%s" % (query, since_query.strftime("%Y-%m-%d"),
                                                  until_query.strftime("%Y-%m-%d"))
            tp.submit(self.perform_search, day_query)
        tp.shutdown(wait=True)

    def perform_search(self, query):
        """
        Scrape items from twitter
        :param query:   Query to search Twitter with. Takes form of queries constructed with using Twitters
                        advanced search: https://twitter.com/search-advanced
        """
        url = self.construct_url(query, self.language)
        continue_search = True
        min_tweet = None
        response = self.execute_search(url)
        
        while response is not None and continue_search and response['items_html'] is not None:
            tweets = self.parse_tweets(response['items_html'])
            
            # If we have no tweets, then we can break the loop early
            if len(tweets) == 0:
                break

            # If we haven't set our min tweet yet, set it now
            if min_tweet is None:
                min_tweet = tweets[0]

            continue_search = True
            self.save_tweets(tweets)

            # Our max tweet is the last tweet in the list
            max_tweet = tweets[-1]
            if min_tweet['tweet_id'] is not max_tweet['tweet_id']:
                if "min_position" in response.keys():
                    max_position = response['min_position']
                else:
                    max_position = "TWEET-%s-%s" % (max_tweet['tweet_id'], min_tweet['tweet_id'])
                url = self.construct_url(query, self.language, max_position=max_position)

                # Sleep for our rate_delay
                sleep(self.rate_delay)
                response = self.execute_search(url)
            

    def execute_search(self, url):
        """
        Executes a search to Twitter for the given URL
        :param url: URL to search twitter with
        :return: A JSON object with data from Twitter
        """
        try:
            # Specify a user agent to prevent Twitter from returning a profile card
            headers = {
                'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.'
                              '86 Safari/537.36'
            }
            req = requests.get(url, headers=headers)
            # response = urllib2.urlopen(req)
            data = json.loads(req.text)
            return data

        # If we get a ValueError exception due to a request timing out, we sleep for our error delay, then make
        # another attempt
        except Exception as e:
            log.error(e)
            log.error("Sleeping for %i" % self.error_delay)
            sleep(self.error_delay)
            return self.execute_search(url)

    def save_tweets(self, tweets):
        """
        Save our tweets and append them to .csv file using pandas
        """
        path = self.path
        if path[-4:] != ".csv":
            path += ".csv"

        temp = pd.DataFrame()
        for tweet in tweets:
            twt_frame = pd.DataFrame([tweet], columns=tweet.keys())
            temp = temp.append(twt_frame, ignore_index=True)
        with open(path, 'a') as f:
            if self.counter == 0:
                temp.to_csv(f, mode='a', index=False)
            else:
                temp.to_csv(f, mode='a', header=False, index=False)

        self.counter += 1

    @staticmethod
    def parse_tweets(items_html):
        """
        Parses Tweets from the given HTML
        :param items_html: The HTML block with tweets
        :return: A JSON list of tweets
        """
        soup = BeautifulSoup(items_html, "html.parser")
        tweets = []

        for li in soup.find_all("li", class_='js-stream-item'):
            # If our li doesn't have a tweet-id, we skip it as it's not going to be a tweet.
            if 'data-item-id' not in li.attrs:
                continue

            tweet = {
                'tweet_id': str(li['data-item-id']),
                'text': None,
                'user_id': None,
                'user_name': None,
                'created_at': None,
                'retweets': 0,
                'favorites': 0
            }

            # Tweet Text
            text_p = li.find("p", class_="tweet-text")
            if text_p is not None:
                tweet['text'] = text_p.get_text()

            # Tweet User ID, User Screen Name, User Name
            user_details_div = li.find("div", class_="tweet")
            if user_details_div is not None:
                tweet['user_id'] = str(user_details_div['data-user-id'])
                tweet['user_name'] = str(user_details_div['data-name'])

            # Tweet date
            date_span = li.find("span", class_="_timestamp")
            if date_span is not None:
                # tweet['created_at'] = float(date_span['data-time-ms'])
                t = datetime.datetime.fromtimestamp((float(date_span['data-time-ms'])/1000))
                fmt = "%Y-%m-%d %H:%M:%S"
                tweet['created_at'] = t.strftime(fmt)

            # Tweet Retweets
            retweet_span = li.select("span.ProfileTweet-action--retweet > span.ProfileTweet-actionCount")
            if retweet_span is not None and len(retweet_span) > 0:
                tweet['retweets'] = int(retweet_span[0]['data-tweet-stat-count'])

            # Tweet Favourites
            favorite_span = li.select("span.ProfileTweet-action--favorite > span.ProfileTweet-actionCount")
            if favorite_span is not None and len(retweet_span) > 0:
                tweet['favorites'] = int(favorite_span[0]['data-tweet-stat-count'])

            tweets.append(tweet)
        return tweets

    @staticmethod
    def construct_url(query, language, max_position=None):
        """
        For a given query, will construct a URL to search Twitter with
        :param query: The query term used to search twitter
        :param max_position: The max_position value to select the next pagination of tweets
        :return: A string URL
        """
        params = {
            # Type Param
            'f': 'tweets',
            # Query Param
            'q': query,
            # Language Param
            'l': language
        }

        # If our max_position param is not None, we add it to the parameters
        if max_position is not None:
            params['max_position'] = max_position

        url_tupple = ('https', 'twitter.com', '/i/search/timeline', '', urlencode(params), '')
        return urlunparse(url_tupple)



if __name__ == '__main__':
    log.basicConfig(level=log.INFO)

    threads = 10

    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="name of resulting .csv file")
    parser.add_argument("since", help="since date")
    parser.add_argument("until", help="until date")
    parser.add_argument("-q", "--query", help="query to search")
    parser.add_argument("-l", "--lang", help="language to search")
    args = parser.parse_args()

    if args.query:
        search_query = args.query
    else:
        search_query = input("Enter a search query please: ")

    if args.lang:
        language = args.lang
    else:
        language = ''

    twitSlice = TwitterSlicer(0, 5, args.since, args.until, args.filename, language, threads)
    twitSlice.search(search_query)
    print("threads: %i" % twitSlice.counter)