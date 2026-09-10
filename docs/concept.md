---
id: thirdy:concept
title: Thirdy — Proactive AI Development Agent Concept Document
product: thirdy
type: spec
status: active
version: 1.0
created: 2026-03-14
last_verified: 2026-09-10
supersedes: []
related: [thirdy:architecture-and-roadmap, thirdy:specification-phase6]
keywords: [Thirdy, コンセプト, Proactive AI, ミーティング, パイプライン, 分散投票]
legacy_drive_id: [1LDEz8G6hVoMzf_BzxCGXOjV6Bqvj6A-BsvuXlHpbuqU]
---

# Thirdy - Proactive AI Development Agent: Concept Document

## Vision
ミーティングから実装開始までの手作業をAIエージェントが圧縮する。「ミーティングが終わった時点で開発に着手できる状態」の実現。

## Core Concept
- 参加者AI: 会話をリアルタイムで「確定仕様 / 要検討 / 雑談」に仕分け。グレーゾーンのみ能動的に確認。
- Knowledge-Powered Decision Support: 選択肢+メリデメ+推薦を提示。人間は判断だけ。

## Pipeline: Meeting → PR (7 Phases)
1. Real-time Meeting Participation (音声文字起こし、仕様仕分け)
2. Specification Generation (仕様書ドラフト自動生成)
3. Design Document Decomposition (設計書分解、技術判断支援)
4. Task Decomposition (タスクリスト自動生成)
5. Branch Creation & Code Generation (Claude Code実装)
6. Test & Validation (仕様ベーステスト自動生成)
7. Pull Request Creation (全トレーサビリティ付きPR)

## Proactive Interaction Design
- 9割黙って1割の価値ある一言
- Intervention Levels: L0(ログ) → L1(バッジ) → L2(インライン) → L3(能動通知)

## Distributed Decision & Meeting Orchestration
- 分散投票 → 全員一致ならfix、割れたらミーティング設定
- Meeting Scale Presets: Quick(10min) / Standard(30min) / Deep Dive(無制限)
- Google Calendar連携で空き時間照合、レジュメ自動生成

## Client Types
- Voice Client (ミーティング用)
- Chat Client (個人/非同期用)
- Non-Engineer Client (自然言語→GitHub Issue)

## Sub-Agent Architecture (3層)
- Top: Pipeline Agent (Meeting→PR)
- Sub (Inward): Internal Audit Agent (仕様・設計定期レビュー)
- Sub (Outward): External Watch Agent (技術スタック変更追跡)

## Use Cases & Effectiveness
- High Impact: REST API, ゲームプロトタイピング, CRUD, CI/CD, テスト自動化
- Medium: ゲーム機能本番実装, プラットフォーム連携, UI/UX
- Lower: 新規アーキテクチャ, パフォーマンスチューニング, ゲームフィール

## Non-Engineer Mode
- ドメイン言語→仕様言語への翻訳。出口はGitHub Issue作成。
- エンジニアがapproveした時点でパイプラインに合流。

## Market Positioning
- 議事録AI / タスク管理 / 設計書の間を繋ぐプロダクトは不在
- 差別化: 能動的に聞いてくるUX、人間とAIの協調ポイント設計
- 競合: Read AI (MCP), Kiro (spec-driven), Proactor AI (meeting agent) - いずれもパイプライン全体はカバーせず

## 移行時の注記（2026-09-10）

Drive 原本（`1LDEz8G6hVoMzf_BzxCGXOjV6Bqvj6A-BsvuXlHpbuqU`）の逐語移行。

**この repo には移行前 Markdown が `apps/web/README.md` 1 本しか無く、`docs/` ディレクトリも
存在しなかった**（[[platform:reconciliation-small-projects]] §2）。∴ 本書を含む Drive の 3 件は
全件が移行対象で、`docs/` はこの移行で新設した。

**`status: active` の理由: 本書はビジョンと UX 原則であり、実装フェーズの進行では古びない。**
「9 割黙って 1 割の価値ある一言」「選択肢+メリデメ+推薦を提示、人間は判断だけ」
「Intervention Levels L0〜L3」は、どの機能を作るかではなく**どう振る舞うか**の規定である。

ただし §Pipeline の 7 Phases は初期構想で、実装は 10 ステップに増えている
（[[thirdy:specification-phase6]] §3）。さらにその後も伸びているので、
**パイプラインの段数を本書から読まないこと。**
