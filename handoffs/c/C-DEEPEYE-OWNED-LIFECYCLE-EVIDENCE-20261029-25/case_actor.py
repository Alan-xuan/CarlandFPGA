"""Two fixed C25 actors, no child creation or product imports."""
import sys
import time


def main():
    if sys.argv[1:] == ['primary']:
        sys.stdout.buffer.write(b'C25_PRIMARY\n')
        sys.stdout.buffer.flush()
        return 0
    if sys.argv[1:] == ['owned-residual']:
        sys.stdout.buffer.write(b'C25_OWNED_RESIDUAL\n')
        sys.stdout.buffer.flush()
        time.sleep(15.0)
        return 0
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
