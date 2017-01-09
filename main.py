import shelve, datetime, time

import requests

from author import Author, SpamProfile

# usage: python -u main.py |tee -a spambot.out
#    or: python -u main.py >> spambot.out &

def get_newest_posters(r):

    posters = set()

    subreddit = r.get_subreddit('all')
    for submission in subreddit.get_new():
        posters.add(getattr(submission, 'author'))

    return [p for p in posters if p]


def check_for_spammers(authordb, r):

    for author in get_newest_posters(r):

        saved_author = str(author.name) in authordb

        if saved_author:
            author = authordb.get(str(author.name))
        else:
            created = author.created
            author = Author(author)
            author.created = created
            authordb[str(author.username)] = author

        author.seen_at = datetime.datetime.now()

        print '+++ %s%s:' % (author.username, ' (seen)' if saved_author else ''),

        if saved_author and author.possible_spammer == False:
            print '%s has been seen already and cannot be a spammer (%s)' % (author.username, author.stats())
            continue

        confidence, spam_profile = author.get_spammer_confidence(r)

        if confidence > 0.5:
            print "%s IS A SPAMMER: %s (%s)" % (author.username, confidence, author.stats())
            try:
                author.submit(r)
            except Exception as e:
                print 'EXCEPTION', type(e)
                print str(e)

            with open('spammers/%s' % author.username, 'a') as f:
                f.write('%s|%s|%s\n' % (spam_profile.link_karma, spam_profile.comment_karma, spam_profile.domains))

        elif confidence == 0.5:
            print "%s is a POSSIBLE spammer: %s (%s)" % (author.username, confidence, author.stats())
            with open('possible-spammers.txt', 'a') as f:
                f.write('http://www.reddit.com/user/%s\n' % author.username)

        elif confidence < 0.5:
            print 'not a spammer (%s)' % author.stats()


if __name__=='__main__':

    authordb = shelve.open('reddit-spambot', writeback=True)

    # credentials stored here
    from prawutil import r

    LOOP_MINIMUM_SECONDS = 45

    try:
        while True:
            loop_start = time.time()

            print '\n%s\n' % datetime.datetime.now()
            try:
                check_for_spammers(authordb, r)
            except requests.exceptions.HTTPError as e:
                print 'REQUESTS EXCEPTION: %s' % str(e)

            authordb.sync()

            loop_duration = time.time() - loop_start
            sleep_duration = max(LOOP_MINIMUM_SECONDS - loop_duration, 0)
            print 'sleeping... (%s)' % sleep_duration
            time.sleep(sleep_duration)

    except (KeyboardInterrupt, SystemExit):
        authordb.close()
    except:
        authordb.close()
        raise
