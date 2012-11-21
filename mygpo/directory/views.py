from itertools import imap as map
from math import ceil

from django.http import HttpResponseNotFound
from django.shortcuts import render
from django.contrib.sites.models import RequestSite
from django.views.decorators.cache import cache_control
from django.views.decorators.vary import vary_on_cookie
from django.utils.decorators import method_decorator
from django.views.generic.base import View

from mygpo.core.proxy import proxy_object
from mygpo.directory.toplist import PodcastToplist, EpisodeToplist, \
         TrendingPodcasts
from mygpo.directory.search import search_podcasts
from mygpo.web.utils import process_lang_params, get_language_names, \
         get_page_list
from mygpo.directory.tags import Topics
from mygpo.users.models import User
from mygpo.db.couchdb.podcast import get_podcast_languages, podcasts_by_id, \
         random_podcasts, podcasts_to_dict
from mygpo.db.couchdb.directory import category_for_tag
from mygpo.db.couchdb.podcastlist import random_podcastlists, \
         podcastlist_count, podcastlists_by_rating


@vary_on_cookie
@cache_control(private=True)
def toplist(request, num=100, lang=None):

    lang = process_lang_params(request)

    toplist = PodcastToplist(lang)
    entries = toplist[:num]

    max_subscribers = max([p.subscriber_count() for (oldp, p) in entries]) if entries else 0
    current_site = RequestSite(request)

    languages = get_podcast_languages()
    all_langs = get_language_names(languages)

    return render(request, 'toplist.html', {
        'entries': entries,
        'max_subscribers': max_subscribers,
        'url': current_site,
        'language': lang,
        'all_languages': all_langs,
    })


class Carousel(View):
    """ A carousel demo """

    @method_decorator(cache_control(private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request):

        return render(request, 'carousel.html', {
            # evaluated lazyly, cached by template
            'topics': Topics(),
            })


class Directory(View):
    """ The main directory page """

    @method_decorator(cache_control(private=True))
    @method_decorator(vary_on_cookie)
    def get(self, request):

        return render(request, 'directory.html', {

            # evaluated lazyly, cached by template
            'topics': Topics(),
            'trending_podcasts': TrendingPodcasts(''),
            'podcastlists': self.get_random_list(),
            'random_podcasts': self.get_random_podcast(),
            })


    def get_random_list(self, podcasts_per_list=5):
        random_list = next(random_podcastlists(), None)
        list_owner = None
        if random_list:
            random_list = proxy_object(random_list)
            random_list.more_podcasts = max(0, len(random_list.podcasts) - podcasts_per_list)
            random_list.podcasts = podcasts_by_id(random_list.podcasts[:podcasts_per_list])
            random_list.user = User.get(random_list.user)

        yield random_list

    def get_random_podcast(self):
        random_podcast = next(random_podcasts(), None)
        if random_podcast:
            yield random_podcast.get_podcast()


@cache_control(private=True)
@vary_on_cookie
def category(request, category, page_size=20):
    category = category_for_tag(category)
    if not category:
        return HttpResponseNotFound()

    # Make sure page request is an int. If not, deliver first page.
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    entries = category.get_podcasts( (page-1) * page_size, page*page_size )
    podcasts = filter(None, entries)
    num_pages = len(category.podcasts) / page_size

    page_list = get_page_list(1, num_pages, page, 15)

    return render(request, 'category.html', {
        'entries': podcasts,
        'category': category.label,
        'page_list': page_list,
        })



RESULTS_PER_PAGE=20

@cache_control(private=True)
@vary_on_cookie
def search(request, template='search.html', args={}):

    if 'q' in request.GET:
        q = request.GET.get('q', '').encode('utf-8')

        try:
            page = int(request.GET.get('page', 1))
        except ValueError:
            page = 1

        results, total = search_podcasts(q=q, skip=RESULTS_PER_PAGE*(page-1))
        num_pages = total / RESULTS_PER_PAGE

        page_list = get_page_list(1, num_pages, page, 15)

    else:
        results = []
        q = None
        page_list = []

    max_subscribers = max([p.subscriber_count() for p in results] + [0])
    current_site = RequestSite(request)

    return render(request, template, dict(
            q= q,
            results= results,
            page_list= page_list,
            max_subscribers= max_subscribers,
            domain= current_site.domain,
            **args
            ))


@cache_control(private=True)
@vary_on_cookie
def episode_toplist(request, num=100):
    lang = process_lang_params(request)

    toplist = EpisodeToplist(language=lang)
    entries = list(map(proxy_object, toplist[:num]))

    # load podcast objects
    podcast_ids = [e.podcast for e in entries]
    podcasts = podcasts_to_dict(podcast_ids, True)
    for entry in entries:
        entry.podcast = podcasts.get(entry.podcast, None)

    current_site = RequestSite(request)

    # Determine maximum listener amount (or 0 if no entries exist)
    max_listeners = max([0]+[e.listeners for e in entries])

    languages = get_podcast_languages()
    all_langs = get_language_names(languages)

    return render(request, 'episode_toplist.html', {
        'entries': entries,
        'max_listeners': max_listeners,
        'url': current_site,
        'language': lang,
        'all_languages': all_langs,
    })


@cache_control(private=True)
@vary_on_cookie
def podcast_lists(request, page_size=20):

    # Make sure page request is an int. If not, deliver first page.
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    lists = podcastlists_by_rating(skip=(page-1) * page_size, limit=page_size)


    def _prepare_list(l):
        user = User.get(l.user)
        l = proxy_object(l)
        l.username = user.username
        return l

    lists = map(_prepare_list, lists)

    num_pages = int(ceil(podcastlist_count() / float(page_size)))

    page_list = get_page_list(1, num_pages, page, 15)

    return render(request, 'podcast_lists.html', {
        'lists': lists,
        'page_list': page_list,
        })
