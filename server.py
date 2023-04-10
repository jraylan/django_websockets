import asyncio
import django
import management.commands.utils.arguments as arguments
import management.commands.utils.main as main
import os


if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", arguments.parser.settings[0])
    django.setup()
    asyncio.run(main.main(arguments.args.bind[0], arguments.args.settings[0]))
