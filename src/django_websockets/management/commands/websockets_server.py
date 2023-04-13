import asyncio
from django.core.management import BaseCommand
from django_websockets.server.arguments import BindType
from django_websockets.server.main import main


class Command(BaseCommand):

    help = 'Websockets Server'

    def add_arguments(self, parser):
        parser.add_argument('-b', '--bind',
                            dest='bind',
                            required=True,
                            type=BindType(),
                            help='Bind address')
        
    def execute(self, *args, **options):
        asyncio.run(main(options['bind']))
