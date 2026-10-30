# -*- coding: utf-8 -*-
"""切换 GPT Researcher 的大模型供应商，并写入项目根目录的 .env。

用法：
    python provider_setup.py                 # 交互式选择
    python provider_setup.py --list          # 列出支持的供应商
    python provider_setup.py --provider deepseek --key sk-xxxx
    python provider_setup.py --provider deepseek --key sk-xxxx --check
    python provider_setup.py --provider qwen --key sk-xxxx --dry-run

脚本只维护 .env 中一段带标记的配置块，不会改动其他配置（如 RETRIEVER、LANGUAGE）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"

BLOCK_START = "# >>> provider config managed by provider_setup.py >>>"
BLOCK_END = "# <<< provider config managed by provider_setup.py <<<"

# ---------------------------------------------------------------------------
# 供应商定义
#   env_key      : 写入 .env 的环境变量名（None 表示本地服务，无需 Key）
#   base_url     : 需要自定义 base_url 时写入 OPENAI_BASE_URL
#   llm_prefix   : FAST_LLM 等使用的前缀（项目内置 provider 名）
#   embedding    : 向量化模型；无 embedding 接口的供应商用 keyword 过滤
# ---------------------------------------------------------------------------
PROVIDERS = {
    "dashscope": {
        "label": "通义千问（阿里云百炼）",
        "env_key": "DASHSCOPE_API_KEY",
        "base_url": None,
        "llm_prefix": "dashscope",
        "fast_model": "qwen-flash",
        "smart_model": "qwen-plus",
        "embedding": "dashscope:text-embedding-v3",
        "context_filter": "auto",
        "check_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "doc": "https://bailian.console.aliyun.com/",
    },
    "deepseek": {
        "label": "DeepSeek 深度求索",
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": None,
        "llm_prefix": "deepseek",
        "fast_model": "deepseek-chat",
        "smart_model": "deepseek-chat",
        "embedding": "openai:text-embedding-3-small",
        "context_filter": "keyword",
        "check_base": "https://api.deepseek.com",
        "doc": "https://platform.deepseek.com/api_keys",
    },
    "openai": {
        "label": "OpenAI 官方",
        "env_key": "OPENAI_API_KEY",
        "base_url": None,
        "llm_prefix": "openai",
        "fast_model": "gpt-4o-mini",
        "smart_model": "gpt-4o",
        "embedding": "openai:text-embedding-3-small",
        "context_filter": "auto",
        "check_base": None,
        "doc": "https://platform.openai.com/api-keys",
    },
    "moonshot": {
        "label": "月之暗面 Kimi / Moonshot",
        "env_key": "OPENAI_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "llm_prefix": "openai",
        "fast_model": "moonshot-v1-8k",
        "smart_model": "moonshot-v1-32k",
        "embedding": "openai:text-embedding-3-small",
        "context_filter": "keyword",
        "check_base": "https://api.moonshot.cn/v1",
        "doc": "https://platform.moonshot.cn/console/api-keys",
    },
    "zhipu": {
        "label": "智谱 GLM",
        "env_key": "OPENAI_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "llm_prefix": "openai",
        "fast_model": "glm-4-flash",
        "smart_model": "glm-4-plus",
        "embedding": "openai:embedding-3",
        "context_filter": "auto",
        "check_base": "https://open.bigmodel.cn/api/paas/v4",
        "doc": "https://open.bigmodel.cn/usercenter/apikeys",
    },
    "minimax": {
        "label": "MiniMax",
        "env_key": "MINIMAX_API_KEY",
        "base_url": None,
        "llm_prefix": "minimax",
        "fast_model": "MiniMax-Text-01",
        "smart_model": "MiniMax-Text-01",
        "embedding": "openai:text-embedding-3-small",
        "context_filter": "keyword",
        "check_base": "https://api.minimax.io/v1",
        "doc": "https://platform.minimaxi.com/",
    },
    "siliconflow": {
        "label": "硅基流动 SiliconFlow",
        "env_key": "OPENAI_API_KEY",
        "base_url": "https://api.siliconflow.cn/v1",
        "llm_prefix": "openai",
        "fast_model": "Qwen/Qwen3-8B",
        "smart_model": "Qwen/Qwen3-32B",
        "embedding": "openai:BAAI/bge-m3",
        "context_filter": "auto",
        "check_base": "https://api.siliconflow.cn/v1",
        "doc": "https://cloud.siliconflow.cn/account/ak",
    },
    "volcengine": {
        "label": "火山方舟（豆包）",
        "env_key": "OPENAI_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "llm_prefix": "openai",
        "fast_model": "doubao-1-5-pro-32k-250115",
        "smart_model": "doubao-1-5-pro-32k-250115",
        "embedding": "openai:text-embedding-3-small",
        "context_filter": "keyword",
        "check_base": "https://ark.cn-beijing.volces.com/api/v3",
        "doc": "https://console.volcengine.com/ark",
    },
    "openrouter": {
        "label": "OpenRouter（聚合）",
        "env_key": "OPENROUTER_API_KEY",
        "base_url": None,
        "llm_prefix": "openrouter",
        "fast_model": "openai/gpt-4o-mini",
        "smart_model": "openai/gpt-4o",
        "embedding": "openai:text-embedding-3-small",
        "context_filter": "keyword",
        "check_base": "https://openrouter.ai/api/v1",
        "doc": "https://openrouter.ai/keys",
    },
    "groq": {
        "label": "Groq",
        "env_key": "GROQ_API_KEY",
        "base_url": None,
        "llm_prefix": "groq",
        "fast_model": "llama-3.3-70b-versatile",
        "smart_model": "llama-3.3-70b-versatile",
        "embedding": "openai:text-embedding-3-small",
        "context_filter": "keyword",
        "check_base": "https://api.groq.com/openai/v1",
        "doc": "https://console.groq.com/keys",
    },
    "ollama": {
        "label": "本地 Ollama（无需 Key）",
        "env_key": None,
        "base_url": "http://localhost:11434/v1",
        "llm_prefix": "ollama",
        "fast_model": "qwen2.5:7b",
        "smart_model": "qwen2.5:7b",
        "embedding": "ollama:nomic-embed-text",
        "context_filter": "auto",
        "check_base": "http://localhost:11434/v1",
        "doc": "https://ollama.com/download",
    },
}

ALIASES = {
    "qwen": "dashscope",
    "tongyi": "dashscope",
    "aliyun": "dashscope",
    "bailian": "dashscope",
    "kimi": "moonshot",
    "glm": "zhipu",
    "doubao": "volcengine",
    "ark": "volcengine",
}


def resolve(name: str) -> str:
    key = name.strip().lower()
    key = ALIASES.get(key, key)
    if key not in PROVIDERS:
        raise SystemExit(
            f"未知供应商：{name}\n可用：{', '.join(PROVIDERS)}（别名：{', '.join(ALIASES)}）"
        )
    return key


def build_block(name: str, key: str | None, model: str | None) -> str:
    cfg = PROVIDERS[name]
    fast = cfg["fast_model"]
    smart = model or cfg["smart_model"]

    lines = [BLOCK_START, f"PROVIDER={name}"]
    if cfg["env_key"] and key:
        lines.append(f'{cfg["env_key"]}={key}')
    if cfg["base_url"]:
        lines.append(f'OPENAI_BASE_URL={cfg["base_url"]}')

    lines += [
        f"FAST_LLM={cfg['llm_prefix']}:{fast}",
        f"SMART_LLM={cfg['llm_prefix']}:{smart}",
        f"STRATEGIC_LLM={cfg['llm_prefix']}:{smart}",
        f"EMBEDDING={cfg['embedding']}",
        f"CONTEXT_FILTER={cfg['context_filter']}",
        BLOCK_END,
    ]
    return "\n".join(lines)


def write_block(block: str, dry_run: bool) -> None:
    text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    pattern = re.compile(
        re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END), re.S
    )
    if pattern.search(text):
        new_text = pattern.sub(block, text)
    else:
        new_text = text.rstrip() + "\n\n" + block + "\n"

    if dry_run:
        print("\n--- 将要写入 .env 的内容（dry-run） ---")
        print(block)
        print("--- 结束 ---")
        return

    ENV_PATH.write_text(new_text, encoding="utf-8")
    print(f"\n已写入 {ENV_PATH}")


def check_provider(name: str, key: str | None, verbose: bool = True) -> bool:
    cfg = PROVIDERS[name]
    try:
        from openai import OpenAI
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"无法导入 openai：{exc}")
        return False

    kwargs = {"api_key": key or "ollama"}
    base = cfg["check_base"]
    client = OpenAI(**kwargs, base_url=base) if base else OpenAI(**kwargs)
    model = cfg["smart_model"]
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "回复 OK"}],
            max_tokens=8,
        )
        answer = (resp.choices[0].message.content or "").strip()
        if verbose:
            print(f"[OK]   {cfg['label']} · {model} · 返回：{answer[:30]}")
        return True
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"[FAIL] {cfg['label']} · {model} · {str(exc)[:200]}")
        return False


def list_providers() -> None:
    print("可用供应商：")
    for i, (name, cfg) in enumerate(PROVIDERS.items(), 1):
        key_hint = cfg["env_key"] or "无需 Key"
        print(f"  {i:>2}) {name:<12} {cfg['label']:<24} {key_hint}")
    print("\n别名：qwen→dashscope, kimi→moonshot, glm→zhipu, doubao/ark→volcengine")


def interactive() -> tuple[str, str | None, str | None]:
    list_providers()
    raw = input("\n请输入供应商名称或编号：").strip()
    if raw.isdigit():
        names = list(PROVIDERS)
        idx = int(raw) - 1
        if not 0 <= idx < len(names):
            raise SystemExit("编号超出范围")
        name = names[idx]
    else:
        name = resolve(raw)

    cfg = PROVIDERS[name]
    key = None
    if cfg["env_key"]:
        key = input(f"请输入 {cfg['label']} 的 API Key：").strip()
        if not key:
            raise SystemExit("Key 不能为空")

    default_model = cfg["smart_model"]
    model = input(f"主力模型（回车使用 {default_model}）：").strip() or None
    return name, key, model


def main() -> int:
    parser = argparse.ArgumentParser(description="切换 GPT Researcher 大模型供应商")
    parser.add_argument("--list", action="store_true", help="列出支持的供应商")
    parser.add_argument("--provider", help="供应商名称，如 deepseek / qwen / kimi")
    parser.add_argument("--key", help="API Key（ollama 可省略）")
    parser.add_argument("--model", help="主力模型，默认使用供应商推荐值")
    parser.add_argument("--check", action="store_true", help="写入后验证一次连通性")
    parser.add_argument("--dry-run", action="store_true", help="只打印配置，不写入 .env")
    args = parser.parse_args()

    if args.list:
        list_providers()
        return 0

    if args.provider:
        name = resolve(args.provider)
        key = args.key
        model = args.model
        if PROVIDERS[name]["env_key"] and not key and not args.dry_run:
            raise SystemExit(f"{name} 需要提供 --key")
    else:
        name, key, model = interactive()

    block = build_block(name, key, model)
    write_block(block, args.dry_run)

    if args.check and not args.dry_run:
        print("\n正在验证模型连通性……")
        ok = check_provider(name, key)
        if not ok:
            print("\n提示：Key 或模型名可能有误，可在 .env 中手动调整后重试。")
            return 1

    print("\n完成。下一步：")
    print("  .\\.venv\\Scripts\\python.exe selfcheck.py")
    print("  .\\.venv\\Scripts\\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())