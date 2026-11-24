import argparse

DEFAULT_PORT = 47631


def main():
    parser = argparse.ArgumentParser(prog="r1999-engine")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--test-image")
    args = parser.parse_args()
    if args.test_image:
        from .selftest import run

        run(args.test_image, args.fake)
        return
    from .server import Host, serve

    host = Host(fake=args.fake)
    host.preload = not args.fake
    serve(host, args.port)


if __name__ == "__main__":
    main()
