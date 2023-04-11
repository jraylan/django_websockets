import asyncio
import django
import django_websockets.server.arguments as arguments
import django_websockets.server.main as main
import os

if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", arguments.parser.settings[0])
    django.setup()
    asyncio.run(main.main(arguments.args.bind[0]))
