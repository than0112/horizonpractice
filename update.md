# Horizon Practice — Upgrade Plan

> 逐步升級指南。每個 Phase 可獨立執行，完成後打勾。

---

## 現況診斷（重要）

| 腳本 | 問題 | 影響 |
|------|------|------|
| `vocus.py` | **完全沒呼叫 Ollama**，Why/Takeaway 是硬編碼字串 | 每篇文章都一樣，毫無洞察 |
| `generate_threads.py` | **完全沒呼叫 Ollama**，固定模板套摘要 | 讀起來像機器，不像人 |
| `ollama_score.py` | 有呼叫 Ollama，但 prompt 太簡單，無受眾篩選 | 分數無法反映讀者喜好 |

---

## Phase 1 — 輸出品質升級（Week 1–2）⬅ 現在執行

### 目標
- vocus.md：每篇 600+ 字，有真實洞察，不是摘要轉貼
- threads.txt：中文貼文像台灣 AI 創作者寫的，有鉤子、有觀點、有互動 CTA

---

### Task 1.1 — 重寫 `scripts/vocus.py`

**做什麼**：加入兩階段 Ollama 呼叫，生成真正的深度文章

**新的輸出格式**（每篇）：
```markdown
# [吸引人的標題，不是原文標題]

> [一句話：為什麼這件事值得你花 3 分鐘讀]

## What Happened
[2-3 段說清楚發生什麼，有背景]

## Why It Matters
[分析影響，有具體數字或例子]

## The Bigger Picture
[連結到更大的 AI/科技趨勢]

## What To Watch
[給讀者的具體行動建議或觀察點]

---
*Source: [原文連結] | Score: X/10*
```

**實作步驟**：
1. 新增 `ollama_generate(prompt: str, timeout: int = 60) -> str` 函數
2. 新增 `build_skeleton(article: dict) -> dict` — Pass 1，產骨架 JSON
3. 新增 `expand_article(skeleton: dict, article: dict) -> str` — Pass 2，展開全文
4. 失敗時 fallback：輸出原始摘要 + `[LLM Unavailable]` 標記

**Prompt 範本**：

```
SKELETON_PROMPT:
You are a senior tech journalist writing for an AI-savvy audience.
Analyze this article and output ONLY valid JSON:
{
  "headline": "compelling rewritten title",
  "hook": "one sentence why readers should care",
  "key_development": "what specifically happened",
  "impact": "concrete consequence with numbers if possible",
  "trend": "how this connects to a larger pattern",
  "action": "what readers should watch or do"
}
Article title: {title}
Summary: {summary}

EXPAND_PROMPT:
You are a tech journalist. Using this skeleton, write a 600-800 word article.
Rules: engaging prose (no bullet points in body), specific examples, your own analytical voice.
Skeleton: {skeleton_json}
```

**驗收標準**：
- [ ] 每篇文章 ≥ 500 字
- [ ] "Why It Matters" 段落有具體分析，不是通用句
- [ ] Ollama 連不上時，不 crash，輸出 fallback 內容

---

### Task 1.2 — 重寫 `scripts/generate_threads.py`

**做什麼**：用 Ollama 生成真正的中文社群貼文，不是套模板

**新的輸出格式**（每則）：
```
[鉤子句——反直覺/問題/驚訝，讓人想讀下去]

[核心洞察，2-3 段，口語化繁體中文，有個人觀點]

[一個具體的數字、例子或比較，讓內容可信]

你怎麼看？[或其他互動問題]

#AI #科技 #[自動生成相關標籤]
```

**實作步驟**：
1. 新增 `generate_thread_post(article: dict) -> str` 函數
2. 使用台灣 AI 評論員 persona prompt
3. 加入字數後處理：超過 300 字截斷到最近的句號
4. Fallback：Ollama 失敗時用現有模板（保留舊邏輯為 fallback）

**Prompt 範本**：
```
THREADS_PROMPT:
你是一位在 Threads 上有影響力的台灣 AI 科技評論員。
你的寫作風格：
- 第一句一定讓人想繼續讀（用問題、驚訝數字、或反直覺觀點開頭）
- 口語化繁體中文，像跟朋友說話
- 有你自己的觀點，不只是轉述新聞
- 結尾一定有互動問題或請讀者分享

把這則 AI 新聞寫成一篇 Threads 貼文（150-250 字）：
標題：{title}
重點：{summary}

只輸出貼文內容，不要任何前言或說明。
```

**驗收標準**：
- [ ] 每則 150-280 字
- [ ] 第一句不是「這篇文章說...」開頭
- [ ] 結尾有問句或 CTA
- [ ] Ollama 連不上時，fallback 到舊模板

---

### Task 1.3 — 新增 `scripts/utils/ollama_client.py`

**做什麼**：把 Ollama HTTP 呼叫抽成共用 client，vocus.py 和 threads.py 共用

```python
# scripts/utils/ollama_client.py
import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.1"

def generate(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 90) -> str:
    """呼叫 Ollama，失敗回傳空字串"""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": model,
            "prompt": prompt,
            "stream": False
        }, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception:
        return ""

def is_available() -> bool:
    """檢查 Ollama 是否在線"""
    try:
        requests.get("http://localhost:11434", timeout=3)
        return True
    except Exception:
        return False
```

---

### Task 1.4 — 輸出驗證

**做什麼**：在 pipeline 最後加驗證，確認輸出有效

新增 `scripts/validate_output.py`：
- 檢查 `output/vocus.md`：至少 3 篇文章，每篇 ≥ 300 字
- 檢查 `output/threads.txt`：至少 3 則貼文
- 失敗時印出警告（不要讓 CI 因此失敗，只是警告）

---

## Phase 2 — 穩定化與累積（Week 3–6）

### Task 2.1 — 每日輸出備份
- `pipeline.py` 執行後，複製 vocus.md → `output/archive/vocus_YYYY-MM-DD.md`
- threads.txt 同理
- Git commit 會自動保存歷史，archive 是額外的本地快照

### Task 2.2 — 累積式 Cache（不覆蓋）
- 現況：每次 pipeline 執行覆蓋整個 `data/cache.json`
- 升級：用文章 URL 作為 key，只新增不存在的文章
- 加入 `"fetched_at": "YYYY-MM-DD"` 欄位
- 保留最近 30 天的文章（超過清除）

### Task 2.3 — 防重複發佈
- 記錄已生成過內容的文章 URL 到 `data/published.json`
- 生成腳本跳過已發佈的文章

### Task 2.4 — Scoring 升級
擴充 `ollama_score.py` 的評分維度：
```json
{
  "score": 8,
  "reason": "...",
  "audience_fit": 7,
  "trending_potential": 6,
  "content_type": "breakthrough|product|research|opinion"
}
```

---

## Phase 3 — 自動化發佈（Month 2–3）

### Task 3.1 — RSS 源管理
- 新增更多 RSS 源到 `data/config.json`（目前只有 3 個）
- 推薦加入：MIT Tech Review, The Verge AI, AI News
- 每個源加入 `enabled: true/false` 開關

### Task 3.2 — Vocus 自動發佈
- 研究 Vocus API（或用 Playwright 模擬登入）
- 自動將生成的文章發佈為草稿
- 人工審核後手動發佈（不全自動，保留品質控制）

### Task 3.3 — 評分回流機制
- 手動記錄 Vocus 文章閱讀數到 `data/feedback.json`
- 用閱讀數調整未來的 scoring prompt 偏好

---

## Phase 4 — 平台化（Month 3+）

- Web UI：讓用戶設定 RSS 源、關鍵字偏好
- 多用戶：每個用戶有自己的 cache 和輸出
- SaaS：月費 $9.9，提供托管版本
- API：把評分引擎包成 REST API

---

## 執行順序建議

```
立刻做（今天）：
  [x] 讀完 update.md
  [ ] 實作 Task 1.3（ollama_client.py）
  [ ] 實作 Task 1.1（vocus.py 重寫）
  [ ] 本地測試：python -m scripts.vocus
  [ ] 實作 Task 1.2（generate_threads.py 重寫）
  [ ] 本地測試：python -m scripts.generate_threads
  [ ] 實作 Task 1.4（validate_output.py）
  [ ] commit + push，觀察 GitHub Actions 輸出

本週內：
  [ ] 調整 prompt（根據實際輸出品質迭代）
  [ ] Phase 2 Task 2.1（每日備份）

下週：
  [ ] Phase 2 剩餘 Tasks
```

---

## 技術注意事項

### GitHub Actions 相容性
- CI 環境**沒有 Ollama**，所以生成腳本必須有 fallback
- `is_available()` 回傳 False 時，使用舊模板邏輯輸出
- 不要讓 LLM 不可用導致 workflow 失敗

### Prompt 長度控制
- llama3.1 context window 有限，每次呼叫的 prompt + response 控制在 2000 tokens 以內
- summary 過長時截斷到前 500 字再傳入

### 執行時間
- 兩階段生成 × 5 篇文章 = 最多 10 次 Ollama 呼叫
- 每次約 10-30 秒，總計最多 5 分鐘
- 加入 `timeout=90` 防止單次卡死

---

## 成功標準

| 指標 | 現況 | Phase 1 目標 |
|------|------|-------------|
| vocus 文章平均字數 | ~100 字（純摘要） | ≥ 500 字 |
| threads 貼文是否有鉤子 | 否（固定開頭） | 是 |
| LLM 實際被呼叫 | 否（vocus/threads 完全沒呼叫） | 是 |
| 輸出需要手動修潤 | 大量修潤 | 小幅潤稿即可 |
