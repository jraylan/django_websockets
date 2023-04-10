import asyncio
from django.core.management import BaseCommand
from .utils.arguments import WebsocketBindAddress
from .utils.main import main


class Command(BaseCommand):

    help = 'Check Models'

    def add_arguments(self, parser):
        parser.add_argument('-b', '--bind',
                            dest='bind',
                            required=True,
                            parser=WebsocketBindAddress(),
                            help='Bind address')
        
    def execute(self, *args, **options):
        asyncio.run(main(options['bind']))
