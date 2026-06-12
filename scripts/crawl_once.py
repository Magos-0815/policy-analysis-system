#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy_index.crawler import PolicyCrawler
from policy_index.runtime_guard import assert_policy_project_isolated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="gov_cn_policy")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offline-sample", action="store_true", help="Use configured sample items instead of network fetch.")
    args = parser.parse_args()

    assert_policy_project_isolated()
    crawler = PolicyCrawler()
    result = crawler.crawl_offline_sample(args.source) if args.offline_sample else crawler.crawl_public_source(args.source, limit=args.limit)
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0 if result.status in {"completed", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
