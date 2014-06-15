"""
Usage: cli -h | --help
       cli mood benchmark <labeled_tweets> [-ump] [-s SW] [-e E] [-b] [--no-AH --no-DD --no-TA] [--min-df=M] 
       cli mood label <input_tweets> <labeled_tweets> [-l L] [--no-AH --no-DD --no-TA]
       cli tweets collect <settings_file> <output_tweets> <track_file> [<track_file>...] [-c C]
       cli tweets filter <input_tweets> <output_tweets> <track_file> [<track_file>...] [-c C] [--each] [--no-rt]
       cli users collect_tweets <settings_file> <user_ids_file> <output_dir> [-c C]
       cli users list_friends <settings_file> <user_ids_file> <output_dir>

Options:
    -h, --help              Show this screen.
    --each                  Filter C tweets for each of the tracked words
    --min-df=M              See min_df from sklearn vectorizers [default: 1]
    --no-AH                 Do not label tweets on Anger/Hostility dimension
    --no-DD                 Do not label tweets on Depression/Dejection dimension
    --no-TA                 Do not label tweets on Tension/Anxiety dimension
    --no-rt                 Remove retweets when filtering
    -b, --binary            No count of features, only using binary features.
    -c C, --count=C         Number of tweets to collect/filter [default: 3200]
    -e E, --emoticons=E     Path to file containing the list of emoticons to keep
    -l, --begin-line=L      Line to start labeling the tweets [default: 0]
    -s SW, --stopwords=SW   Path to file containing the stopwords to remove from the corpus
    -u                      Keep URLs when cleaning corpus
    -m                      Keep mentions when cleaning corpus
    -p                      Keep punctuation when cleaning corpus
"""
import sporty.sporty as sporty
from sporty.datastructures import *
from sporty.tweets import Tweets
from docopt import docopt
import sys
from sklearn.svm import SVC
from sklearn.multiclass import OneVsRestClassifier
import os.path


def main():
    args = docopt(__doc__)
    api = sporty.api()
    if args['tweets']:
        # Concatenate the words to track
        totrack = set()
        for i in args['<track_file>']:
            totrack = totrack.union(set(LSF(i).tolist()))

        if args['collect']:
            # Authenticate to the Twitter API
            api.tweets = sporty.tweets.api(settings_file=args['<settings_file>'])
            api.collect(totrack, args['<output_tweets>'], count=int(args['--count']))

        if args['filter']:
            api.load(args['<input_tweets>'])
            api.filter(int(args['--count']), totrack, each_word=args['--each'], output_file=args['<output_tweets>'], rt=args['--no-rt']==False)

    elif args['users']:
        # Authenticate to the Twitter API
        api.user = sporty.user.api(settings_file=args['<settings_file>'])
        if args['collect_tweets']:
            for uid in LSF(args['<user_ids_file>']).tolist():
                user_path = os.path.join(args['<output_dir>'], uid)
                if os.path.isfile(user_path):
                    continue
                api.user.user_id = int(uid)
                api.collectTweets(int(args['--count']), user_path)

        if args['list_friends']:
            for uid in LSF(args['<user_ids_file>']).tolist():
                user_path = os.path.join(args['<output_dir>'], uid)
                if os.path.isfile(user_path):
                    continue
                api.user.user_id = int(uid)
                with open(user_path, 'w') as f:
                    for friend_id in api.getFriends():
                        f.write(str(friend_id) + "\n")

    elif args['mood']:
        keys = ['AH', 'DD', 'TA']
        if args['--no-AH']:
            keys.remove('AH')
        if args['--no-DD']:
            keys.remove('DD')
        if args['--no-TA']:
            keys.remove('TA')

        labels = {x: [0, 1] for x in keys}

        if args['label']:
            api.load(args['<input_tweets>'])
            api.label(labels, args['<labeled_tweets>'], int(args['--begin-line']))

        elif args['benchmark']:
            if len(keys) > 1:
                api.mood.clf = OneVsRestClassifier(SVC(kernel='linear'))
            tweets = Tweets(args['<labeled_tweets>'])
            cleaner_options = {'stopwords': args['--stopwords'],
                               'emoticons': args['--emoticons'],
                               'rm_mentions': not args['-m'],
                               'rm_punctuation': not args['-p'],
                               'rm_unicode': not args['-u']}
            tfidf_options = {'min_df': int(args['--min-df']),
                             'binary': args['--binary'],
                             'ngram_range': (1, 2)}
            api.buildFeatures(tweets, cleaner_options=cleaner_options, labels=keys)
            api.buildVectorizer(options=tfidf_options)
            api.train()
            api.benchmark(cv=3)

if __name__ == "__main__":
    main()