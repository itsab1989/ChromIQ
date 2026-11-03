import argparse,json
from .client import Instrument


def main():
    parser=argparse.ArgumentParser(description='Read-only independent FD-9 protocol candidate; disconnect other clients first')
    parser.add_argument('host');parser.add_argument('--output',required=True)
    args=parser.parse_args();instrument=Instrument(args.host)
    # Validate the output destination before acquiring an instrument session.
    from pathlib import Path
    if Path(args.output).exists():parser.error('Output directory already exists')
    try:
        with instrument:print(json.dumps(instrument.status(),indent=2))
    finally:instrument.save_transcript(args.output)


if __name__=='__main__':main()
