import asyncio
from django.core.management import BaseCommand
from django_websockets.server.arguments import BindType, workers
from django_websockets.server.main import main


class Command(BaseCommand):

    help = 'Websockets Server'

    def add_arguments(self, parser):
        parser.add_argument('-b', '--bind',
                            dest='bind',
                            required=True,
                            type=BindType(),
                            help='Bind address')
        parser.add_argument('-w', '--workers',
                            dest='workers',
                            required=True,
                            type=workers,
                            help='Num of workers')
        
    def execute(self, *args, **options):
        asyncio.run(main(options['bind'], settings=options.get('settings'), workers=options['workers']))
