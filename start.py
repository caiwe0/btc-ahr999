import argparse
from ahr999 import run_pipeline


def run_pages(force_refresh=False):
    df = run_pipeline(force_refresh=force_refresh)

    # 如果你原来有生成 _site/ 的逻辑，保留在这里。
    # 下面只是最小示例，避免导入失败。
    os.makedirs("_site", exist_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BTC AHR999 定投指标工具")
    parser.add_argument("--pages", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    if args.pages:
        run_pages(force_refresh=args.force_refresh)
    else:
        run_pipeline(force_refresh=args.force_refresh)