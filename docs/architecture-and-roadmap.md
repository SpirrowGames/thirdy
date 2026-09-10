---
id: thirdy:architecture-and-roadmap
title: Thirdy — Architecture & Roadmap
product: thirdy
type: spec
status: active
version: 1.0
created: 2026-03-14
last_verified: 2026-09-10
supersedes: []
related: [thirdy:concept, thirdy:specification-phase6]
keywords: [Thirdy, アーキテクチャ, ロードマップ, 技術スタック, LLMルーティング, Lexora]
legacy_drive_id: [14qriNswKAblgdmRRaeZfc2BNKhGUaMkyEFE4kl3tet0]
---

# Thirdy - Architecture & Roadmap

## 技術スタック
- Backend: Python / FastAPI
- Frontend: TypeScript / Next.js
- LLMゲートウェイ: Lexora（拡張）- OpenAI互換API
- LLMプロトコル: OpenAI互換 /v1/chat/completions
- DB: PostgreSQL
- リアルタイム: SSE (FastAPI native)
- 認証: Google OAuth 2.0
- インフラ: {{HOST_SERVICES}} (RTX 5090, 256GB RAM)
- CI/CD: GitHub Actions

## LLMルーティング戦略
- トリアージ → Qwen 1.5B (ローカル)
- 仕様抽出/設計分解/判断支援 → Claude Sonnet/Opus (クラウド)
- コード生成 → Claude Code (クラウド)
- 内部監査/外部監視 → Qwen 14B / DeepSeek (ローカル)

## モジュールアーキテクチャ (3層×12モジュール)
### 入力層: Chat Client, Voice Client, Non-Engineer Client
### コアパイプライン: Spec Extractor, Design Decomposer, Task Generator, Code Generator, PR Creator
### 支援層: Decision Support, Distributed Voting, Internal Audit Agent, External Watch Agent

## MVP: Chat + Spec + Decision
- Chat Client (Web) + Spec Extractor + Decision Support (inline)
- Google OAuth, Lexora (ローカル+Claude proxy), PostgreSQL
- Exit Criteria: チャット→仕様書出力、能動的明確化、仕様保存、モデルルーティング

## ロードマップ (6フェーズ)
- Phase 1: MVP (Chat→Spec) - 3モジュール
- Phase 2: パイプライン拡張 (Design Decomposer, Task Generator) - 2モジュール
- Phase 3: Code→PR (Code Generator, PR Creator) - 2モジュール
- Phase 4: チームコラボレーション (Distributed Voting, Calendar) - 1モジュール
- Phase 5: 音声&非エンジニア (Voice Client, Non-Engineer Client) - 2モジュール
- Phase 6: バックグラウンドインテリジェンス (Audit, Watch Agents) - 2モジュール

## リポジトリ構成: thirdy/ (モノレポ)
- apps/ (web, api)
- modules/ (spec-extractor, decision-support, etc.)
- packages/ (shared-schemas, llm-client)
- infra/, docs/

## Spirrow Platform統合
Lexora, Prismind, Cognilens, MagicKit, Watchdog, Phanthand, RAG Server

## 移行時の注記（2026-09-10）

Drive 原本（`14qriNswKAblgdmRRaeZfc2BNKhGUaMkyEFE4kl3tet0`）の移行。
`docs/` はこの移行で新設した（[[platform:reconciliation-small-projects]] §2）。

**逐語からの逸脱が 1 箇所ある。** §技術スタック の「インフラ」行に書かれていた実ホスト名を
`{{HOST_SERVICES}}` に置換した。document conventions §3.1 による。実値は
[[platform:infra-registry]] にある。

### 技術スタックは今も合っている

| 本書 | repo |
|---|---|
| Backend: Python / FastAPI | `apps/api/` |
| Frontend: TypeScript / Next.js | `apps/web/` |
| モノレポ `packages/` | `packages/llm-client` / `packages/shared-schemas` |

`modules/` と `infra/` は本書の構想どおりには作られておらず、`apps/` と `packages/` の 2 つに
落ち着いている。

### ロードマップは大きく追い越されている

本書は **6 フェーズ**の計画だが、repo の最終コミットは **Phase 19**（2026-03-21、
"Proactive Tech Watch Agent (Phase 19)"）。本書が予定していなかった router が
`apps/api/src/api/routers/` に 8 本ある:

`activities` / `costs` / `dashboard` / `github_repos` / `metrics` / `notifications` /
`spec_reviews` / `teams`

∴ **§ロードマップ と §モジュールアーキテクチャ の「3層×12モジュール」を現状として読まないこと。**
本書の価値は **§LLMルーティング戦略**（どの処理をローカル小型モデルに、どれをクラウドに振るか）と
**§Spirrow Platform統合**（どのサービスに依存する設計か）にある。この 2 つは repo のコードを
読んでも意図が出てこない。
