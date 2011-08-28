from itertools import islice
from django.core.management.base import BaseCommand
from mygpo.core import models as newmodels
from mygpo.api import models
from mygpo.directory.toplist import PodcastToplist
from mygpo.data import feeddownloader
from optparse import make_option
import datetime

UPDATE_LIMIT = datetime.datetime.now() - datetime.timedelta(days=15)

class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('--toplist', action='store_true', dest='toplist', default=False, help="Update all entries from the Toplist."),
        make_option('--update-new', action='store_true', dest='new', default=False, help="Update all podcasts with new Episodes"),
        make_option('--list-only', action='store_true', dest='list', default=False, help='Don\'t download/update anything, just list the podcasts to be updated'),

	make_option('--max', action='store', dest='max', type='int', default=-1, help="Set how many feeds should be updated at maximum"),

        make_option('--random', action='store_true', dest='random', default=False, help="Update random podcasts, best used with --max option"),
        )


    def handle(self, *args, **options):

        fetch_queue = []

        if options.get('toplist'):
            toplist = PodcastToplist()
            for oldindex, obj in toplist[:100]:
                obj = obj.get_old_obj()
                if isinstance(obj, models.Podcast):
                    fetch_queue.append(obj)
                elif isinstance(obj, models.PodcastGroup):
                    for p in obj.podcasts():
                        fetch_queue.append(p)

        if options.get('new'):
            podcasts = self.get_podcast_with_new_episodes()
            fetch_queue.extend(list(podcasts))

        if options.get('random'):
            fetch_queue = models.Podcast.objects.all().order_by('?')

        for url in args:
           try:
                fetch_queue.append(models.Podcast.objects.get(url=url))
           except:
                pass

        if len(fetch_queue) == 0 and not options.get('toplist') and not options.get('new'):
            fetch_queue = models.Podcast.objects.filter(last_update__lt=UPDATE_LIMIT).order_by('last_update')

        max = options.get('max', -1)
        if max > 0:
            fetch_queue = fetch_queue[:max]

        if options.get('list'):
            print '%d podcasts would be updated' % len(fetch_queue)
            print '\n'.join([p.url for p in fetch_queue])

        else:
            print 'Updating %d podcasts...' % len(fetch_queue)
            feeddownloader.update_podcasts(fetch_queue)


    def get_podcast_with_new_episodes(self):
        db = newmodels.Podcast.get_db()
        res = db.view('maintenance/episodes_need_update',
                group_level = 1,
                reduce      = True,
            )

        for r in res:
            podcast_id = r['key']
            podcast = newmodels.Podcast.get(podcast_id)
            if podcast:
                try:
                    yield podcast.get_old_obj()
                except:
                    pass
