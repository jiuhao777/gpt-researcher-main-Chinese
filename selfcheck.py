# -*- coding: utf-8 -*-
"""GPT Researcher 本地自检脚本。

用法（在项目根目录执行）：
    .\\.venv\\Scripts\\python.exe selfcheck.py            # 全量检查（会发一次模型/搜索请求）
    .\\.venv\\Scripts\\python.exe selfcheck.py --offline  # 只查配置、依赖和文件
"""
import argparse
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

PASS = 0
FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [OK]   {name}" + (f"  {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f"  {detail}" if detail else ""))
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="跳过网络请求")
    args = parser.parse_args()

    print("=" * 64)
    print("GPT Researcher 自检")
    print("=" * 64)

    print("\n[1/5] 环境变量")
    for key in ("DASHSCOPE_API_KEY", "BOCHA_API_KEY"):
        value = os.getenv(key, "")
        check(f"{key} 已配置", bool(value), f"长度 {len(value)}")
    check("RETRIEVER=bocha", os.getenv("RETRIEVER") == "bocha", os.getenv("RETRIEVER", ""))
    check("LANGUAGE 已配置", bool(os.getenv("LANGUAGE")), os.getenv("LANGUAGE", ""))
    check("SMART_LLM", bool(os.getenv("SMART_LLM")), os.getenv("SMART_LLM", ""))

    print("\n[2/5] Python 依赖")
    for module in ("fastapi", "uvicorn", "langchain_openai", "docx", "htmldocx", "dashscope", "ddgs"):
        try:
            __import__(module)
            check(f"import {module}", True)
        except Exception as exc:  # noqa: BLE001
            check(f"import {module}", False, str(exc)[:70])

    print("\n[3/5] 前端与样式文件")
    for rel in (
        "frontend/index.html",
        "frontend/scripts.js",
        "frontend/styles.css",
        "backend/styles/pdf_styles.css",
        "backend/utils.py",
    ):
        check(rel, (ROOT / rel).exists())

    print("\n[4/5] 模型与搜索连通性")
    if args.offline:
        print("  [SKIP] --offline 模式下跳过")
    else:
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=os.environ["DASHSCOPE_API_KEY"],
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            response = client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": "回复 OK"}],
                max_tokens=5,
            )
            check("百炼 qwen-plus", True, response.choices[0].message.content.strip()[:20])
        except Exception as exc:  # noqa: BLE001
            check("百炼 qwen-plus", False, str(exc)[:140])

        try:
            import requests

            resp = requests.post(
                "https://api.bochaai.com/v1/web-search",
                headers={
                    "Authorization": f"Bearer {os.environ['BOCHA_API_KEY']}",
                    "Content-Type": "application/json",
                },
                json={"query": "AI Agent", "count": 3},
                timeout=20,
            )
            check("博查搜索", resp.status_code == 200, f"HTTP {resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            check("博查搜索", False, str(exc)[:140])

    print("\n[5/5] 本地服务")
    with socket.socket() as sock:
        busy = sock.connect_ex(("127.0.0.1", 8000)) == 0
    if busy:
        print("  [INFO] 8000 端口已占用（服务可能已在运行）→ http://127.0.0.1:8000")
    else:
        print("  [INFO] 8000 端口空闲，启动命令：")
        print("         python -m uvicorn main:app --host 127.0.0.1 --port 8000")

    print("\n" + "=" * 64)
    print(f"结果：{PASS} 项通过，{FAIL} 项失败")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())