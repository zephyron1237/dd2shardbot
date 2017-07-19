import difflib
import re
import requests
import json
import time
from collections import deque
import praw
#from bs4 import BeautifulSoup

WAIT_TIME_SECONDS = 30

SHARD_URL_FORMAT = "https://dd2tools.com/shards/{}"
SHARD_JSON_TIMESTAMP_URL = "http://dd2tools.com/shards-ext-ts.json"
SHARD_JSON_URL = "http://dd2tools.com/shards-ext.json"

SUBREDDIT = 'dungeondefenders'

USER_AGENT = "dd2shardbot 1.0 created by /u/zephyron1237"
USERNAME = "dd2shardbot"
PASSWORD = "will move this"
CLIENT_ID = "to a config file"
CLIENT_SECRET = "at some point"

shardDict = {}
idCache = deque(maxlen=200)
lastJsonTimestamp = 0;
startupTimestamp = int(time.time()); # only reply to posts that appear after we start, to avoid caching issues

shardRegex = re.compile('\[\[.+?\]\]')

def main():
    global lastCheckTimestamp
    
    reddit = praw.Reddit(client_id = CLIENT_ID,
                client_secret = CLIENT_SECRET,
                password = PASSWORD,
                user_agent = USER_AGENT,
                username = USERNAME)

    subreddit = reddit.subreddit(SUBREDDIT)
    update_shard_dictionary()

    running = True    
    while running:        
        print("Checking new comments and submissions: ", time.ctime())

        try:
            for comment in subreddit.comments(limit=25):
                done = handle_body(comment.body, comment, comment.replies)
                if done:
                    break

            for submission in subreddit.new(limit=15):
                if submission.selftext:
                    done = handle_body(submission.selftext, submission, submission.comments)
                    if done:
                        break
                    
        except praw.exceptions.APIException as e:
            print("ERROR: ", e)
        except Exception as e:
            print("ERROR: ", e)
                            
        time.sleep(WAIT_TIME_SECONDS)
                

# Takes a body text and its comment/submission, determines whether to respond, and responds
# Returns whether the body has already been analysed.
def handle_body(bodyText, bodyRedditObject, replies):
    global idCache

    #print("handle_body ", bodyText, bodyRedditObject)
    
    if bodyRedditObject.id in idCache:
        return True # end of new comments
    idCache.append(bodyRedditObject.id)

    # make sure that it was created after we started so we could've cached it
    if bodyRedditObject.created_utc < startupTimestamp :
        return True
    
    shards = get_body_shards(bodyText)
    if shards and len(shards) > 0:
        print("COMMENT: ", bodyText)
        update_shard_dictionary() # too late for these shards, but good for the future
        response = get_response_body(shards)
        if response:
            try:
                bodyRedditObject.reply(response)
                print("RESPONSE: ", response)

            except praw.exceptions.APIException as e:
                print("ERROR: ", e)
            except Exception as e:
                print("ERROR: ", e)

    return False

# Returns nothing. If new data, setup internal dictionary with shards info.
def update_shard_dictionary():
    global shardDict
    global lastJsonTimestamp

    try:
        timestampJson = requests.get(SHARD_JSON_TIMESTAMP_URL).text
    except Exception as e:
        print("ERROR: ", e)
        return
        
    if not timestampJson:
        print("ERROR: Could not load timestamp json URL")
        return
    timestampTree = json.loads(timestampJson)
    if not timestampTree:
        print("ERROR: Could not load timestamp json tree.")
        return
    timestamp = timestampTree['timestamp']
    if not timestamp:
        print("ERROR: Could not find timestamp in tree")
        return
    if timestamp <= lastJsonTimestamp:
        print("INFO: No new shards since ", timestamp)
        return

    # We have a new timestamp!
    # We'll wait until after we parse shards to set lastJsonTimestamp to ensure success.    
    
    newShardDict = {}

    try:
        shardJson = requests.get(SHARD_JSON_URL).text
    except Exception as e:
        print("ERROR: ", e)
        return
        
    if not shardJson:
        print("ERROR: Could not load shard json URL")
        return    
    shardTree = json.loads(shardJson)
    if not shardTree:
        print("ERROR: Could not load shard json tree")
        return

    for shard in shardTree:
        shardName = shard['name']
        if not shardName:
            print("ERROR: Found shard without shard name.")
            continue

        newShardDict[shardName] = shard
        print(shard)
        
    print("Total shards found: ", len(newShardDict))
    shardDict = newShardDict
    lastJsonTimestamp = timestamp

# Returns shard info that is closest to given text
def get_real_shard(shardText):
    matches = difflib.get_close_matches(shardText, list(shardDict.keys()), 1)
    if len(matches) == 0:
        return None
    else:
        return shardDict[matches[0]]

# Returns the first N correct shard infos inside a text body
def get_body_shards(body):
    result = []
    bodyShards = re.findall(shardRegex, body)
    for bodyShard in bodyShards:
        shard = get_real_shard(bodyShard[2:-2])
        if shard:
            result.append(shard)

    return result[:10]

# Returns the URL for a given shards
def get_shard_url(shard):
    return SHARD_URL_FORMAT.format(shard['slug'])

# Returns the reddit-formatted text of the shard.
def get_shard_formatted_text(shard):
    print("GET_SHARD_FORMATTED_TEXT DEBUG: ", shard)
    if 'shard_pack' in shard:
        result = """
**[{}]({})**

{}

{} - {} - {}
""".format(shard['name'], get_shard_url(shard), shard['description'], shard['shard_pack'], shard['slot'], ', '.join(shard['classes']))

    elif 'not_in_game' in shard:
        result = """
**[{}]({})**

{}

{} - {}

*({})*
""".format(shard['name'], get_shard_url(shard), shard['description'], shard['slot'], ', '.join(shard['classes']), shard['not_in_game'])

    else:
        result = """
**[{}]({})**

{}

{} - {}
""".format(shard['name'], get_shard_url(shard), shard['description'], shard['slot'], ', '.join(shard['classes']))
    return result

# Returns the static footer line for each post
def get_footer():
    return "^^Created ^^by ^^[/u\\/zephyron1237](/u/zephyron1237) ^^and ^^powered ^^by ^^[dd2tools.com](https://dd2tools.com)."

# Returns a string that is the body of the bot's response to given shards
def get_response_body(shards):
    result = ''
    for shard in shards:
        result += get_shard_formatted_text(shard)
        result += """
***
"""
    result += get_footer()
    return result


if __name__ == "__main__":
    main()
