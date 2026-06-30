# Horizon Practice — 測試手冊

> 按照順序執行，每個步驟都有預期結果和錯誤排查。

---

## 前置確認

在開始任何測試前，確認以下環境：

```powershell
# 確認 Python 版本（需要 3.11+）
python --version

# 確認 uv 已安裝
uv --version

# 確認工作目錄正確（應顯示 horizonpratice）
pwd
```

---

## Test 1 — Ollama 連線健檢

**目的**：確認本地 Ollama 在線且 llama3.1 模型已安裝。

```powershell
# 步驟 1：確認 Ollama 服務在跑
curl http://localhost:11434

# 步驟 2：確認 llama3.1 模型存在
ollama list

# 步驟 3：用 Python 測試連線
uv run python -c "from scripts.utils.ollama_client import is_available; print('Ollama online:', is_available())"
```

**預期結果**：
```
Ollama online: True
```

**如果失敗**：
- `Ollama online: False` → 執行 `ollama serve` 啟動服務
- `ollama list` 看不到 llama3.1 → 執行 `ollama pull llama3.1`
- `ModuleNotFoundError` → 確認你在專案根目錄，先執行 `uv sync`

---

## Test 2 — ollama_client 功能測試

**目的**：確認 `generate()` 和 `generate_json()` 正常運作。

```powershell
uv run python -c "
from scripts.utils.ollama_client import generate, generate_json

# 測試基本生成
print('=== Test generate() ===')
result = generate('Say hello in one sentence.', timeout=30)
print(result[:200])
print()

# 測試 JSON 生成
print('=== Test generate_json() ===')
result = generate_json('Output ONLY valid JSON: {\"status\": \"ok\", \"value\": 42}', timeout=30)
print(result)
"
```

**預期結果**：
```
=== Test generate() ===
Hello! I'm here to help you with any questions or tasks you may have.

=== Test generate_json() ===
{'status': 'ok', 'value': 42}
```

**如果失敗**：
- `generate()` 回傳空字串 → Ollama timeout，嘗試加大 timeout 或重啟 Ollama
- `generate_json()` 回傳 `{}` → 模型沒有輸出有效 JSON，屬正常（fallback 機制生效）

---

## Test 3 — Cache 資料確認

**目的**：確認 `data/cache.json` 有有效文章資料。

```powershell
uv run python -c "
import json
with open('data/cache.json', encoding='utf-8') as f:
    data = json.load(f)
articles = data.get('articles', [])
print(f'Total articles: {len(articles)}')
for a in articles[:3]:
    print(f'  [{a.get(\"score\", 0)}/10] {a.get(\"title\", \"\")[:60]}')
"
```

**預期結果**：
```
Total articles: 15
  [8/10] Qwen 3.6 27B is the sweet spot for local development
  [7/10] ...
  [6/10] ...
```

**如果失敗**：
- `Total articles: 0` → 需要先執行 pipeline 抓取文章（見 Test 5）
- `FileNotFoundError` → `data/cache.json` 不存在，先執行 `uv run python -m scripts.pipeline`

---

## Test 4 — 單獨測試 vocus.py

**目的**：確認 vocus.py 能呼叫 Ollama 並產出深度文章。

```powershell
uv run python -m scripts.vocus
```

**觀察重點**：
1. 終端機應顯示每篇文章的生成進度
2. 最後一行顯示生成的文章數和總字數

**預期輸出（終端機）**：
```
  Generating article 1/5: Qwen 3.6 27B is the sweet spot for lo...
  Generating article 2/5: ...
  ...
VOCUS GENERATED ✔ (5 articles, ~3200 words)
```

**然後檢查輸出品質**：

```powershell
uv run python -c "
with open('output/vocus.md', encoding='utf-8') as f:
    content = f.read()
words = len(content.split())
import re
articles = re.findall(r'^## .+', content, re.MULTILINE)
print(f'Articles: {len(articles)}')
print(f'Total words: {words}')
print(f'Has LLM fallback: {\"[LLM Unavailable\" in content}')
print()
print('--- First 500 chars ---')
print(content[:500])
"
```

**品質驗收標準**：
- `Articles: 5`（或你 cache 裡有幾篇）
- `Total words:` ≥ 2000（平均每篇 400+ 字）
- `Has LLM fallback: False`（Ollama 正常時應該是 False）

**如果 Ollama 離線**：
```
⚠️  Ollama unavailable — using fallback templates
VOCUS GENERATED ✔ (5 articles, ~350 words)
```
這是預期行為，fallback 模式仍會產出檔案。

---

## Test 5 — 單獨測試 generate_threads.py

**目的**：確認中文貼文生成品質。

```powershell
uv run python -m scripts.generate_threads
```

**預期輸出（終端機）**：
```
  Generating thread 1/3: Qwen 3.6 27B is the sweet spot for lo...
  Generating thread 2/3: ...
  Generating thread 3/3: ...
THREADS GENERATED ✔ (3 posts)
```

**然後檢查貼文內容**：

```powershell
type output\threads.txt
```

**品質驗收標準**（人工判斷）：
- [y ] 每則貼文第一句不是「這篇文章說...」或「根據最新報導...」
- [ y] 有台灣口語感（不像機器翻譯）
- [ x] 結尾有問句或互動 CTA
- [x ] 有 hashtag（如 `#AI #科技`）
- [ x] 每則字數在 100–300 字之間

**字數快速檢查**：

```powershell
uv run python -c "
with open('output/threads.txt', encoding='utf-8') as f:
    content = f.read()
posts = [p.strip() for p in content.split('---') if p.strip()]
print(f'Posts: {len(posts)}')
for i, p in enumerate(posts, 1):
    print(f'Post {i}: {len(p)} chars')
    print(p[:100])
    print()
"
```

---

## Test 6 — 執行 validate_output.py

**目的**：自動驗證輸出品質。

```powershell
uv run python -m scripts.validate_output
```

**預期結果（全部通過）**：
```
✅ Output validation passed
```

**如果有警告**：
```
⚠️  Output validation warnings:
   • vocus: only 2 articles (expected ≥ 3)
   • threads: post 1 too short (45 chars)
```

每個警告對應的排查方式：

| 警告訊息 | 原因 | 解法 |
|---------|------|------|
| `vocus: only N articles` | cache 文章太少或 LLM 全部失敗 | 重跑 pipeline 補充文章 |
| `vocus: only N words total` | LLM 沒有生成內容 | 確認 Ollama 在線並重跑 |
| `vocus: contains old hardcoded boilerplate` | vocus.py 還是舊版本 | 確認已儲存新版 vocus.py |
| `threads: only N posts` | cache 文章不足 3 篇 | 重跑 pipeline |
| `threads: post N too short` | LLM 生成失敗用了 fallback | 檢查 Ollama 狀態 |
| `threads: all posts are identical` | LLM 卡住重複輸出 | 重啟 Ollama 再跑 |

---

## Test 7 — 完整 Pipeline 端對端測試

**目的**：模擬 GitHub Actions 的完整執行流程。

> ⚠️ 這個測試會重新抓 RSS 並覆蓋 cache.json，需要網路連線。

```powershell
# 完整流程（依序執行）
uv run python -m scripts.pipeline
uv run python -m scripts.generate_threads
uv run python -m scripts.vocus
uv run python -m scripts.dashboard_builder
uv run python -m scripts.validate_output
```

**每步預期輸出**：

```
# pipeline
STEP 1: fetching RSS...
RSS articles: 15
STEP 2: loading cache...
TOTAL articles: 15
STEP 3: scoring + processing...
STEP 4: saving output...
STEP 5: generating outputs...
PIPELINE DONE ✔

# generate_threads
  Generating thread 1/3: ...
THREADS GENERATED ✔ (3 posts)

# vocus
  Generating article 1/5: ...
VOCUS GENERATED ✔ (5 articles, ~XXXX words)

# validate_output
✅ Output validation passed
```

**全部成功後，確認輸出檔案**：

```powershell
# 確認檔案都存在且不是空的
uv run python -c "
import os
files = ['output/vocus.md', 'output/threads.txt', 'data/cache.json', 'dashboard/data.json']
for f in files:
    size = os.path.getsize(f) if os.path.exists(f) else 0
    status = '✅' if size > 100 else '❌'
    print(f'{status} {f} ({size} bytes)')
"
```

---

## Test 8 — Ollama 離線 Fallback 測試

**目的**：確認 Ollama 離線時系統不會 crash。

```powershell
# 先停止 Ollama（如果在跑的話）
# Windows: 在工作管理員結束 ollama.exe
# 或者直接跳過停止，改用環境變數模擬

# 測試 vocus fallback
uv run python -m scripts.vocus
```

**預期結果**：
```
⚠️  Ollama unavailable — using fallback templates
  Generating article 1/5: ...
  Generating article 2/5: ...
VOCUS GENERATED ✔ (5 articles, ~350 words)
```

**關鍵確認**：程式沒有噴出 Exception，vocus.md 有正常產出（雖然是 fallback 內容）。

---

## 快速煙霧測試（只想確認基本功能正常）

```powershell
# 一次跑完關鍵路徑（約 2 分鐘，需要 Ollama 在線）
uv run python -c "from scripts.utils.ollama_client import is_available; print('Ollama:', is_available())"
uv run python -m scripts.vocus
uv run python -m scripts.generate_threads
uv run python -m scripts.validate_output
type output\threads.txt
```

---

## 常見問題排查

### ImportError: No module named 'scripts'

```powershell
# 確認在專案根目錄
pwd  # 應顯示 d:\horizonpratice

# 確認有 __init__.py（如果沒有就建立）
ls scripts\
ls scripts\utils\
```

如果 `scripts/__init__.py` 不存在：
```powershell
echo "" > scripts\__init__.py
echo "" > scripts\utils\__init__.py
```

### pipeline.py ImportError（from ollama_score import score）

pipeline.py 用的是舊的 import 路徑，直接執行時會失敗：

```powershell
# 正確執行方式（用 -m 模組模式）
uv run python -m scripts.pipeline

# 不要用這個（會 ImportError）
# uv run python scripts/pipeline.py
```

### Ollama 生成太慢或 Timeout

編輯 `scripts/utils/ollama_client.py`，調低 timeout 或換輕量模型：

```python
# 改用更輕量的模型加速
result = generate(prompt, model="llama3.2:1b", timeout=60)
```

### vocus.md 輸出全是 fallback 內容

確認 Ollama 在線且模型正確：

```powershell
ollama list  # 確認有 llama3.1
curl http://localhost:11434/api/generate -d "{\"model\":\"llama3.1\",\"prompt\":\"hi\",\"stream\":false}"
```

---

## 測試結果記錄

每次測試後，可以在這裡記錄結果：

| 日期 | Test | 結果 | 備註 |
|------|------|------|------|
| | Test 1 Ollama 健檢 | ⬜ Pass / ⬜ Fail | |
| | Test 2 ollama_client | ⬜ Pass / ⬜ Fail | |
| | Test 3 Cache 資料 | ⬜ Pass / ⬜ Fail | |
| | Test 4 vocus.py | ⬜ Pass / ⬜ Fail | 字數：___ |
| | Test 5 threads.py | ⬜ Pass / ⬜ Fail | 品質：_/5 |
| | Test 6 validate | ⬜ Pass / ⬜ Fail | |
| | Test 7 端對端 | ⬜ Pass / ⬜ Fail | |
