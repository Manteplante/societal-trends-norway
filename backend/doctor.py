"""Check the configuration and say what is wrong.

    make doctor

Prints which credential source was used and what failed about it. Safe to paste
anywhere — it reports setting and field *names*, never secret values. See the
rule documented above `diagnose()` in storage.py.
"""

from . import storage


def main() -> None:
    print("\n".join(storage.diagnose()))


if __name__ == "__main__":
    main()
