import datetime, time, math

from HTMLParser import HTMLParser
from bs4 import BeautifulSoup
from urlparse import urlparse

SAFE_DOMAINS = {'imgur.com','i.imgur.com','en.wikipedia.org'}
BAD_DOMAINS  = {'adultsexdating.worldoftanksmody097.ru'}


class SpamProfile(object):

    def __init__(self, domains, link_karma, comment_karma):
        self.domains = domains
        self.link_karma = link_karma
        self.comment_karma = comment_karma


class Author(object):

    def __init__(self, author):
        self.author = author
        self.username = str(author.name)
        self.possible_spammer = None
        self.spammer_confidence = None
        self.seen_at = None
        self.checked_at = None
        self.submitted_at = None
        self.link_karma = None
        self.comment_karma = None

        self.created = None

        self.unique_domain_submissions = None
        self.total_link_submissions = None

    def __getstate__(self):
        d = dict(self.__dict__)
        del d['author']
        return d

    def __setstate__(self, d):
        self.__dict__.update(d)
        self.author = None

    def __str__(self):
        return '%s (confidence: %s) (possible: %s) (%s)' % (self.username, self.spammer_confidence, self.possible_spammer, self.checked_at)

    def stats(self):
        return '%s/%s/%s/%s/%s' % (self.link_karma,
                                   self.comment_karma,
                                   '-' if self.total_link_submissions is None else self.total_link_submissions,
                                   '-' if self.unique_domain_submissions is None else self.unique_domain_submissions,
                                   '-' if not hasattr(self, 'created') else self.days_old())

    def reload_author(self, r):
        self.author = r.get_redditor(self.username)

    def days_old(self):
        seconds_old = time.time() - self.created
        days_old = seconds_old / 86400.0
        return max(int(math.floor(days_old)), 0)

    def get_unique_domain_submissions(self, submissions):
        self.unique_domain_submissions = len(set(s.domain for s in submissions))
        return self.unique_domain_submissions

    def get_unique_domains_all(self, link_submissions, self_submissions):

        def get_domains_from_html(html):

            domains = set()
            soup = BeautifulSoup(html)
            for link in soup.findAll('a'):
                href = link.get('href')
                if href:
                    u = urlparse(href)
                    domain = u.netloc.split(':')[0]
                    if domain:
                        domains.add(domain.lower())

            return domains

        domains = set(s.domain for s in link_submissions)

        h = HTMLParser()

        for s in self_submissions:
            if s.selftext_html:
                html = h.unescape(s.selftext_html)
                domains.update(get_domains_from_html(html))

        return domains


    def get_total_link_submissions(self, submissions):
        self.total_link_submissions = len(submissions)
        return self.total_link_submissions

    def safe_domains(self, submissions):
        domains = set(s.domain for s in submissions)
        return domains & SAFE_DOMAINS == domains

    def get_spammer_confidence(self, r):

        self.checked_at = datetime.datetime.now()

        if self.submitted_at is not None:
            print 'ALREADY SUBMITTED'
            return 0, None

        if self.author is None:
            self.reload_author(r)

        self.link_karma = self.author.link_karma
        self.comment_karma = self.author.comment_karma
        self.created = int(self.author.created)

        if self.link_karma > 100:
            self.possible_spammer = False
            self.spammer_confidence = 0
            return self.spammer_confidence, None

        if self.comment_karma > 100:
            self.possible_spammer = False
            self.spammer_confidence = 0
            return self.spammer_confidence, None

        submissions = list(self.author.get_submitted())
        self_submissions = [s for s in submissions if s.domain.startswith('self.')]
        link_submissions = [s for s in submissions if not s.domain.startswith('self.')]
        link_submissions = [s for s in link_submissions if not s.domain.endswith('reddit.com')]

        if len(link_submissions) > 0 and link_submissions[0].domain in BAD_DOMAINS:
            return 1, SpamProfile([link_submissions[0].domain], self.link_karma, self.comment_karma)

        comments = list(self.author.get_comments())
        comment_words = sum(len(c.body.split()) for c in comments)

        total_link_submissions = self.get_total_link_submissions(link_submissions)
        unique_domains = self.get_unique_domain_submissions(link_submissions)
        unique_domains_all = self.get_unique_domains_all(link_submissions, self_submissions)

        # exclude accounts that post comments
        if comment_words > 100:
            self.possible_spammer = False
            self.spammer_confidence = 0
        elif total_link_submissions < 2:
            self.possible_spammer = True
            self.spammer_confidence = 0

        # exclude accounts that make self posts
        elif len(self_submissions) >= 10:
            self.possible_spammer = False
            self.spammer_confidence = 0

        elif unique_domains == 1:
            self.possible_spammer = True
            if self.safe_domains(link_submissions):
                self.spammer_confidence = 0.5
            else:
                self.spammer_confidence = 1

        return self.spammer_confidence, SpamProfile(list(set(s.domain for s in submissions)), self.link_karma, self.comment_karma)


    def submit(self, r):
        r.submit('spam', 'overview for %s' % self.username, url='http://www.reddit.com/user/%s?sort=new' % self.username)
        self.submitted_at = datetime.datetime.now()
