import argparse

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="all")
    args = parser.parse_args()
    print(f"TODO: repair target={args.target}")

if __name__ == "__main__":
    main()
