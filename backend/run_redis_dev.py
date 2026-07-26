"""Development Redis server using fakeredis TCP mode.
Usage: python run_redis_dev.py
Starts an in-memory Redis-compatible server on port 6379.
No external Redis installation needed.
"""
import signal
import sys
from fakeredis import TcpFakeServer


def main():
    server = TcpFakeServer(("localhost", 6379))
    print("FakeRedis server started on localhost:6379")
    print("Press Ctrl+C to stop")

    def shutdown(sig, frame):
        print("\nShutting down...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
