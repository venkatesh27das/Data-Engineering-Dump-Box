"""Redis/RQ worker boundary.

The MVP runs jobs in-process for a zero-configuration local experience. This module is kept as the
stable command target for replacing the executor with RQ without changing API or domain services.
"""


def main() -> None:
    print("Workbook Agent uses the built-in worker. Start the API with `make backend`.")


if __name__ == "__main__":
    main()
