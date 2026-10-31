# -*- coding: utf-8 -*-
"""接入 LangSmith 可观测性：写入 .env 并验证连通性。

用法：
    python langsmith_setup.py                       # 交互式
    python langsmith_setup.py --key lsv2_pt_xxx
    python langsmith_setup.py --key lsv2_pt_xxx --project my-research
    python langsmith_setup.py --check               # 只验证 .env 里现有配置

脚本只维护 .env 中一段带标记的配置块，不会改动模型或检索配置。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"

BLOCK_START = "# >>> langsmith config managed by langsmith_setup.py >>>"
BLOCK_END = "# <<< langsmith config managed by langsmith_setup.py <<<"

DEFAULT_ENDPOINT = "https://api.smith.langchain.com"
DEFAULT_PROJECT = "gpt-researcher-chinese"


def build_block(key: str, project: str, endpoint: str) -> str:
    lines = [BLOCK_START]
    # 新版 langsmith 用 LANGSMITH_*，旧版 LangChain 用 LANGCHAIN_*，两套都写。
    lines += [
        "LANGCHAIN_TRACING_V2=true",
        f"LANGCHAIN_API_KEY={key}",
        f"LANGCHAIN_PROJECT={project}",
        f"LANGCHAIN_ENDPOINT={endpoint}",
        "LANGSMITH_TRACING=true",
        f"LANGSMITH_API_KEY={key}",
        f"LANGSMITH_PROJECT={project}",
        f"LANGSMITH_ENDPOINT={endpoint}",
        BLOCK_END,
    ]
    return "\n".join(lines)


def write_block(block: str) -> None:
    text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    pattern = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END), re.S)
    if pattern.search(text):
        new_text = pattern.sub(block, text)
    else:
        new_text = text.rstrip() + "\n\n" + block + "\n"
    ENV_PATH.write_text(new_text, encoding="utf-8")
    print(f"已写入 {ENV_PATH}")


def read_current() -> tuple[str | None, str, str]:
    if not ENV_PATH.exists():
        return None, DEFAULT_PROJECT, DEFAULT_ENDPOINT
    from dotenv import dotenv_values

    values = dotenv_values(ENV_PATH)
    key = values.get("LANGSMITH_API_KEY") or values.get("LANGCHAIN_API_KEY")
    project = (
        values.get("LANGSMITH_PROJECT")
        or values.get("LANGCHAIN_PROJECT")
        or DEFAULT_PROJECT
    )
    endpoint = (
        values.get("LANGSMITH_ENDPOINT")
        or values.get("LANGCHAIN_ENDPOINT")
        or DEFAULT_ENDPOINT
    )
    return key, project, endpoint


def check(key: str, project: str, endpoint: str) -> bool:
    try:
        from langsmith import Client
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] 无法导入 langsmith：{exc}")
        print("       试试：pip install langsmith")
        return False

    print(f"正在连接 {endpoint} ……")
    try:
        client = Client(api_key=key, api_url=endpoint)
        projects = list(client.list_projects(limit=100))
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] 连接失败：{str(exc)[:300]}")
        return False

    names = [p.name for p in projects]
    print(f"[OK]   连接成功，账号下已有 {len(names)} 个项目")
    if project in names:
        print(f"[OK]   项目 {project} 已存在")
    else:
        print(f"[INFO] 项目 {project} 还没有，第一次上报 trace 时会自动创建")

    if names:
        print("       已有项目：" + "、".join(names[:10]))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="接入 LangSmith 可观测性")
    parser.add_argument("--key", help="LangSmith API Key（lsv2_pt_...）")
    parser.add_argument("--project", help="项目名，默认 gpt-researcher-chinese")
    parser.add_argument("--endpoint", help="API 地址，默认 https://api.smith.langchain.com")
    parser.add_argument("--check", action="store_true", help="只验证现有配置，不写入")
    args = parser.parse_args()

    key, project, endpoint = read_current()

    if args.check:
        if not key:
            print("[FAIL] .env 里没有 LANGSMITH_API_KEY / LANGCHAIN_API_KEY")
            return 1
        return 0 if check(key, project, endpoint) else 1

    key = args.key or key
    project = args.project or project
    endpoint = args.endpoint or endpoint

    if not key:
        print("LangSmith 接入向导")
        print("  1. 打开 https://smith.langchain.com 注册/登录")
        print("  2. 左下角 Settings → API Keys → Create API Key")
        print("  3. 复制以 lsv2_pt_ 开头的 Key")
        key = input("\n粘贴 API Key：").strip()
        if not key:
            print("Key 不能为空")
            return 1
        project = input(f"项目名（回车用 {project}）：").strip() or project

    if not key.startswith("lsv2_"):
        print("提示：LangSmith 的 Key 通常以 lsv2_pt_ 开头，请确认没有复制错。")

    write_block(build_block(key, project, endpoint))

    print("\n正在验证……")
    ok = check(key, project, endpoint)
    if not ok:
        print("\n写入已完成，但验证没通过。排查方向：")
        print("  - Key 是否有效、是否被删除")
        print("  - 网络能否访问 api.smith.langchain.com（国内可能需要代理）")
        print("  - 企业自托管地址是否正确")
        return 1

    print("\n接入完成。下一步：")
    print("  1. 重启服务：python -m uvicorn main:app --host 127.0.0.1 --port 8000")
    print("  2. 跑一次研究（Web 或 CLI）")
    print(f"  3. 打开 https://smith.langchain.com 查看项目 {project} 的 trace")
    return 0


if __name__ == "__main__":
    sys.exit(main())