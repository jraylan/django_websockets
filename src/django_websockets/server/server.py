import django_websockets.server.arguments as arguments
import django_websockets.server.main as main

if __name__ == '__main__':
    main.main(arguments.args.bind[0])
