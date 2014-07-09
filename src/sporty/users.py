import json
from tweets import Tweets
from utils import TwitterAPIUser
from datastructures import LSF
import time
import sys
import requests
import os.path
import re
from collections import defaultdict


class api(TwitterAPIUser):
    def __init__(self, user_ids=[], settings_file=None):
        super(api, self).__init__(settings_file)
        self.loadIds(user_ids)
        self.users = []
        self.friends = defaultdict(list)
        self.similarFriend = {}

    def loadIds(self, user_ids=[]):
        """
        Store a list of user IDs in the instance. This list will be used to load users and
        users' friends.
        """
        if type(user_ids) == list:
            self.user_ids = user_ids
        elif type(user_ids) == int:
            self.user_ids = [user_ids]
        else:
            self.user_ids = LSF(user_ids).tolist()

    def load(self, user_dir):
        """
        For every user id, this function loads the user from a file which name matches with the
        user id in the given user_dir directory.
        """
        self.users = []
        for uid in self.user_ids:
            user_file = os.path.join(user_dir, str(uid))
            if os.path.isfile(user_file):
                with open(user_file) as uf:
                    tw = json.loads(uf.readline())
                    user = tw['user']
                    self.users.append(user)
        return self.users

    def loadFriends(self, friends_dir):
        """
        For every user id, this function loads its friends from a file which name match with the 
        user id in the given friends_dir directory.
        """
        self.friends = defaultdict(list)
        for uid in self.user_ids:
            friends_file = os.path.join(friends_dir, str(uid) + '.extended')
            if os.path.isfile(friends_file):
                friends = self.friends[uid]
                with open(friends_file) as ff:
                    for line in ff:
                        friends.append(json.loads(line))
        return self.friends

    def outputFriendsIds(self, output_dir="./"):
        """
        Outputs the list of friends (intersection between followees and followers) for a user.
        """
        for user_id in self.user_ids:
            user_path = os.path.join(output_dir, user_id)
            if os.path.isfile(user_path):  # friends list already exists for this user
                continue
            friends = set()
            cursor = -1
            followees = set()
            followers = set()
            # Get the followees

            while cursor != 0:
                try:
                    response = json.loads(self.getFolloweesStream(user_id, cursor).text)
                    if 'error' in response.keys() and response['error'] == 'Not authorized.':
                        break
                    if 'errors' in response.keys():
                        if response['errors'][0]['code'] == 88:
                            sleep_min = 5
                            sys.stderr.write(json.dumps(response) + "\n")
                            sys.stderr.write("Limit rate reached. Wait for " + str(sleep_min) +
                                             " minutes.\n")
                            sleep_sec = sleep_min*60
                            time.sleep(sleep_sec)
                        continue
                    cursor = response['next_cursor']
                    followees = followees.union(set(response['ids']))
                except Exception, e:
                    print response
                    raise e
            cursor = -1
            # Get the followers
            while cursor != 0:
                try:
                    response = json.loads(self.getFollowersStream(user_id, cursor).text)
                    if 'error' in response.keys() and response['error'] == 'Not authorized.':
                        break
                    if 'errors' in response.keys():
                        if response['errors'][0]['code'] == 88:
                            sleep_min = 5
                            sys.stderr.write(json.dumps(response) + "\n")
                            sys.stderr.write("Limit rate reached. Wait for " + str(sleep_min) +
                                             " minutes.\n")
                            sleep_sec = sleep_min*60
                            time.sleep(sleep_sec)
                        continue
                    cursor = response['next_cursor']
                    followers = followers.union(set(response['ids']))
                except Exception, e:
                    raise e

            # Get the intersection between followers and followees
            friends = followees.intersection(followers)

            # Output the result
            with open(user_path, 'w') as f:
                for friend_id in friends:
                    f.write(str(friend_id) + "\n")

    def collectTweets(self, output_dir="./", count=3200):
        """
        Returns the 3200 last tweets of every user in user_ids.
        """
        for user_id in self.user_ids:
            user_path = os.path.join(output_dir, user_id)
            if os.path.isfile(user_path):  # friends list already exists for this user
                continue
            tweets = Tweets(user_path, 'a+')
            i = 0
            max_id = 0
            keep_try = True
            while keep_try:
                try:
                    r = self.getUserStream(user_id, max_id=max_id)
                    if not r.get_iterator().results:
                        keep_try = False
                    for item in r.get_iterator():
                        if 'message' in item.keys():
                            remaining = r.get_rest_quota()['remaining']
                            if not remaining:
                                sleep_min = 5
                                sys.stderr.write("Limit rate reached. Wait for " + str(sleep_min) +
                                                 " minutes.\n")
                                sleep_sec = sleep_min*60
                                time.sleep(sleep_sec)
                                break
                            else:
                                sys.stderr.write(str(item) + "\n")
                        elif 'errors' in item.keys():
                            continue
                        else:
                            max_id = item['id'] - 1
                            tweets.append(item)
                            i += 1
                            if count and i >= count:
                                keep_try = False
                                break
                except Exception, e:
                    if item:
                        sys.stderr.write(str(item) + "\n")
                    raise e

    def show(self):
        """
        Returns the user objects using the Twitter API for every user id.
        """
        extended = []
        user_ids = self.user_ids
        chunks = [user_ids[x:x+100] for x in xrange(0, len(user_ids), 100)]
        for uids in chunks:
            item = None
            try:
                r = self.getUserShow(uids)
                if not r.get_iterator().results:
                    keep_try = False
                for item in r.get_iterator():
                    if 'message' in item.keys():
                        remaining = r.get_rest_quota()['remaining']
                        if not remaining:
                            sleep_min = 5
                            sys.stderr.write("Limit rate reached. Wait for " + str(sleep_min) +
                                             " minutes.\n")
                            sleep_sec = sleep_min*60
                            time.sleep(sleep_sec)
                            break
                        else:
                            sys.stderr.write(str(item) + "\n")
                    elif 'errors' in item.keys():
                        continue
                    else:
                        extended.append(item)
            except Exception, e:
                if item:
                    sys.stderr.write(str(item) + "\n")
                raise e
        return extended

    def __displayUser(self, u, indent=0):
        udisplay = ""
        udisplay += indent*"\t"
        udisplay += "- name: " + u['name'].encode('ascii', 'ignore')
        udisplay += ", gender: " + u['gender']
        udisplay += ", location: " + u['location'].encode('ascii', 'ignore')
        udisplay += "\n"
        udisplay += indent*"\t"
        udisplay += "  statuses: " + str(u['statuses_count'])
        udisplay += ", followees: " + str(u['friends_count'])
        udisplay += ", followers: " + str(u['followers_count'])
        print udisplay

    def getMostSimilarFriend(self, user_dir, friends_dir):
        self.load(user_dir)
        self.loadFriends(friends_dir)
        males, females = self.getCensusNames()

        # only keep users that have a non empty location
        self.users = filter(lambda u: u['location'], self.users)

        for u in self.users:
            # label user and friends on gender
            self.labelGender(u, males, females)
            for f in self.friends[u['id']]:
                self.labelGender(f, males, females)

            # filter friends on gender
            self.friends[u['id']] = filter(lambda f: f['gender'] == u['gender'],
                                           self.friends[u['id']])

            # only keep friends that have a non empty location
            self.friends[u['id']] = filter(lambda f: f['location'],
                                           self.friends[u['id']])

        for u in self.users:
            self.__displayUser(u)
            for f in self.friends[u['id']]:
                self.__displayUser(f, 1)
        return None

    def labelGender(self, user, males, females):
        name = user['name'].lower().split()
        if len(name) == 0:
            name = ['']
        name = name[0]
        if name in males:
            user['gender'] = 'm'
        elif name in females:
            user['gender'] = 'f'
        else:
            user['gender'] = 'n'
        return user

    def getCensusNames(self):
        males_url = 'http://www.census.gov/genealogy/www/data/1990surnames/dist.male.first'
        females_url = 'http://www.census.gov/genealogy/www/data/1990surnames/dist.female.first'
        males = requests.get(males_url).text.split('\n')
        females = requests.get(females_url).text.split('\n')
        males_dict = {}
        females_dict = {}
        for m in males:
            if m:
                entry = m.split()
                males_dict[entry[0].lower()] = float(entry[1])
        for f in females:
            if f:
                entry = f.split()
                females_dict[entry[0].lower()] = float(entry[1])
        # Remove ambiguous names (those that appear on both lists)
        males = males_dict
        females = females_dict
        ambiguous = {n: (males[n], females[n]) for n in females.keys() + males.keys()
                     if n in males and n in females}
        males = [m for m in males if m not in ambiguous]
        females = [f for f in females if f not in ambiguous]
        eps = 0.1
        todel = []
        for n in ambiguous:
            scores = ambiguous[n]
            if scores[0] > scores[1]+eps:
                males.append(n)
                todel.append(n)
            elif scores[0]+eps < scores[1]:
                females.append(n)
                todel.append(n)
        for n in todel:
            del ambiguous[n]
        return set(males), set(females)
