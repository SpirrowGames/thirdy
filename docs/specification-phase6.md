---
id: thirdy:specification-phase6
title: Thirdy 現状仕様書 v1.0（Phase 6 完了時点）
product: thirdy
type: spec
status: archived
version: 1.0
created: 2026-03-16
last_verified: 2026-09-10
supersedes: []
related: [thirdy:concept, thirdy:architecture-and-roadmap]
keywords: [Thirdy, 仕様書, Phase6, 10ステップパイプライン, API, データモデル]
legacy_drive_id: [1k5dM8av5earDuxPyCF3Jjl9r2oWvJ9N3g_sP52kHx9o]
---

# Thirdy — Proactive AI Development Agent 仕様書

> Phase 6 完了時点 (2026-03-16) の現状仕様を網羅的にまとめたドキュメント。

---

## 1. プロダクト概要

Thirdy は、ソフトウェア開発プロセス全体を AI が主導的にサポートする **Proactive AI Development Agent**。
自然言語の会話からスタートし、仕様書抽出 → 設計分解 → 判断支援 → タスク生成 → コード生成 → PR 作成 → 音声入力 → Issue 管理 → 内部監査 → 外部監視 という **10 ステップパイプライン** を一気通貫で実行する。

---

## 2. アーキテクチャ

### 2.1 モノレポ構成

```
thirdy/
├── apps/
│   ├── api/          # FastAPI バックエンド (Python)
│   └── web/          # Next.js 15 フロントエンド (TypeScript)
├── packages/
│   ├── llm-client/   # LLM プロバイダー抽象化パッケージ (Lexora連携)
│   └── shared-schemas/ # Pydantic 共有スキーマ
├── docker-compose.yml
└── pyproject.toml     # uv ワークスペース
```

### 2.2 技術スタック

| レイヤー | 技術 |
|---------|------|
| フロントエンド | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, shadcn/ui |
| バックエンド | FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2 |
| データベース | PostgreSQL 16 |
| キャッシュ / キュー | Redis 7 + ARQ (非同期ワーカー) |
| LLM | Lexora 経由 (クラウド API プロキシ + モデルルーティング) |
| 認証 | Google OAuth 2.0 + JWT |
| デプロイ | Docker Compose (postgres / redis / api / web / worker) |

### 2.3 通信パターン

- **SSE (Server-Sent Events)**: LLM ストリーミング応答（チャット、仕様書抽出、設計分解、タスク生成、コード生成、PR作成、Issue構造化）
- **REST API**: CRUD 操作全般
- **SWR ポーリング**: バックグラウンドジョブの完了検知（Audit / Watch は `refreshInterval: 5000ms`）
- **ARQ ワーカー**: 非同期バックグラウンドジョブ（Audit、Watch）

---

## 3. 10 ステップパイプライン

### 3.1 パイプライン概要

```
Spec → Design → Decisions → Tasks → Code → PR → Voice → Issues → Audit → Watch
```

UI 上では PipelineProgress コンポーネントが各ステップの完了状態を視覚的に表示し、タブで切り替え可能。

### 3.2 各ステップ詳細

#### Step 1: Specification (仕様書抽出)
- **バックエンド**: `POST /conversations/{id}/specs/extract` (SSE)
- **機能**: 会話履歴から LLM が仕様書を自動抽出
- **状態**: draft → in_review → approved
- **CRUD**: GET/PATCH/DELETE `/specifications/{id}`

#### Step 2: Design (設計分解)
- **バックエンド**: `POST /conversations/{id}/designs/decompose` (SSE)
- **機能**: 承認済み仕様書を基に設計書を自動生成、同時に判断ポイントも検出
- **状態**: draft → in_review → approved
- **CRUD**: GET/PATCH/DELETE `/designs/{id}`

#### Step 3: Decisions (判断支援)
- **バックエンド**: `POST /conversations/{id}/decisions/detect` (SSE)
- **機能**: 設計書中の判断ポイントを検出、オプション＋推奨案を提示
- **状態**: pending → resolved / dismissed
- **投票機能**: 分散投票 (VoteSession) + 公開リンク共有 (`/vote/{shareToken}`)
- **カレンダー連携**: Google Calendar API 連携、プリセットミーティング (15/30/60分)
- **CRUD**: GET/PATCH/DELETE `/decision-points/{id}`

#### Step 4: Tasks (タスク生成)
- **バックエンド**: `POST /conversations/{id}/tasks/generate` (SSE)
- **機能**: 承認済み設計からタスクを自動分解、依存関係解決
- **状態**: pending → in_progress → done / skipped
- **優先度**: low / medium / high / critical
- **CRUD**: GET/PATCH/DELETE `/tasks/{id}`

#### Step 5: Code (コード生成)
- **バックエンド**: `POST /conversations/{id}/codes/generate` (SSE)
- **機能**: タスクに基づいてコードを自動生成
- **状態**: draft → approved / rejected
- **UI**: ファイル単位表示 (CodeFileViewer)
- **CRUD**: GET/PATCH/DELETE `/codes/{id}`

#### Step 6: Pull Requests (PR 作成)
- **バックエンド**: `POST /conversations/{id}/prs/create` (SSE)
- **機能**: 承認済みコードから GitHub PR を自動作成
- **状態**: creating → created → merged / closed / failed
- **UI**: PR URL リンク、ステータス遷移ボタン
- **CRUD**: GET/PATCH `/pull-requests/{id}`

#### Step 7: Voice (音声入力)
- **バックエンド**: `POST /conversations/{id}/voice/transcribe` (SSE, multipart)
- **機能**: 音声ファイルから faster-whisper で文字起こし + LLM 分類
- **状態**: processing → completed / failed
- **UI**: ドラッグ＆ドロップアップロード、リアルタイムセグメントストリーミング
- **CRUD**: GET/DELETE `/voice/transcripts/{id}`

#### Step 8: Issues (GitHub Issue 管理)
- **バックエンド**: `POST /conversations/{id}/issues/structure` (SSE), `POST /conversations/{id}/issues/create` (SSE)
- **機能**: 自然言語 → LLM で構造化 → GitHub Issue 作成 (2ステップ)
- **状態**: draft → creating → created / closed / failed
- **UI**: 自然言語入力、インライン編集プレビュー、ラベル表示
- **CRUD**: GET/PATCH/DELETE `/issues/{id}`

#### Step 9: Audit (内部監査)
- **バックエンド**: `POST /conversations/{id}/audit` (REST, 202 Accepted)
- **処理**: ARQ バックグラウンドジョブ → LLM が全エンティティを横断的に品質検査
- **結果**: AuditReport (summary + findings)
  - **summary**: overall_score (0-100), quality_badge (excellent/good/needs_improvement/poor), findings_by_severity
  - **findings**: severity (info/warning/error/critical), category (consistency/completeness/quality/dependency/redundancy), suggestion
- **UI**: "Run Audit" ボタン、品質バッジ色分け、スコア表示、展開可能な findings リスト
- **CRUD**: GET/DELETE `/audits/{id}`

#### Step 10: Watch (外部監視)
- **バックエンド**: `POST /conversations/{id}/watch` (REST, 202 Accepted)
- **処理**: ARQ バックグラウンドジョブ → LLM が外部リスクを分析
- **結果**: WatchReport (summary + findings)
  - **summary**: highest_impact (none/low/medium/high/critical), requires_action, findings_by_impact, findings_by_source
  - **findings**: source_type (dependency/api_change/security/competitor/ecosystem), impact_level, recommendation
- **UI**: "Run Watch" ボタン、impact 色分け、"Action needed" フラグ、展開可能な findings リスト
- **CRUD**: GET/DELETE `/watches/{id}`

---

## 4. API エンドポイント一覧

### 4.1 認証
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/auth/google` | Google OAuth ログイン |
| GET | `/auth/me` | 現在のユーザー情報 |

### 4.2 会話
| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/conversations` | 会話一覧 |
| POST | `/conversations` | 会話作成 |
| GET | `/conversations/{id}` | 会話取得 |
| PATCH | `/conversations/{id}` | 会話更新 |
| DELETE | `/conversations/{id}` | 会話削除 |

### 4.3 チャット
| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/conversations/{id}/messages` | メッセージ一覧 |
| POST | `/conversations/{id}/chat` | SSE チャット送信 |

### 4.4 仕様書
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/conversations/{id}/specs/extract` | SSE 仕様書抽出 |
| GET | `/conversations/{id}/specs` | 仕様書一覧 |
| GET | `/specifications/{id}` | 仕様書取得 |
| PATCH | `/specifications/{id}` | 仕様書更新 |
| DELETE | `/specifications/{id}` | 仕様書削除 |

### 4.5 設計
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/conversations/{id}/designs/decompose` | SSE 設計分解 |
| GET | `/conversations/{id}/designs` | 設計一覧 |
| GET | `/designs/{id}` | 設計取得 |
| PATCH | `/designs/{id}` | 設計更新 |
| DELETE | `/designs/{id}` | 設計削除 |

### 4.6 判断ポイント
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/conversations/{id}/decisions/detect` | SSE 判断ポイント検出 |
| GET | `/conversations/{id}/decisions` | 判断ポイント一覧 |
| GET | `/decision-points/{id}` | 判断ポイント取得 |
| PATCH | `/decision-points/{id}` | 判断ポイント更新 |
| DELETE | `/decision-points/{id}` | 判断ポイント削除 |

### 4.7 投票
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/decision-points/{id}/vote-sessions` | 投票セッション作成 |
| GET | `/decision-points/{id}/vote-sessions` | 投票セッション一覧 |
| POST | `/vote-sessions/{id}/close` | 投票セッション終了 |
| GET | `/vote/{shareToken}` | 公開投票ページ |
| POST | `/vote/{shareToken}/cast` | 投票実行 |
| POST | `/vote/{shareToken}/subscribe` | SSE リアルタイム集計 |
| POST | `/vote-sessions/{id}/calendar-event` | カレンダーイベント作成 |

### 4.8 タスク
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/conversations/{id}/tasks/generate` | SSE タスク生成 |
| GET | `/conversations/{id}/tasks` | タスク一覧 |
| GET | `/tasks/{id}` | タスク取得 |
| PATCH | `/tasks/{id}` | タスク更新 |
| DELETE | `/tasks/{id}` | タスク削除 |

### 4.9 コード
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/conversations/{id}/codes/generate` | SSE コード生成 |
| GET | `/conversations/{id}/codes` | コード一覧 |
| GET | `/codes/{id}` | コード取得 |
| PATCH | `/codes/{id}` | コード更新 |
| DELETE | `/codes/{id}` | コード削除 |

### 4.10 プルリクエスト
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/conversations/{id}/prs/create` | SSE PR 作成 |
| GET | `/conversations/{id}/prs` | PR 一覧 |
| GET | `/pull-requests/{id}` | PR 取得 |
| PATCH | `/pull-requests/{id}` | PR 更新 |

### 4.11 音声
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/conversations/{id}/voice/transcribe` | SSE 音声文字起こし |
| GET | `/conversations/{id}/voice/transcripts` | 文字起こし一覧 |
| DELETE | `/voice/transcripts/{id}` | 文字起こし削除 |

### 4.12 Issue
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/conversations/{id}/issues/structure` | SSE Issue 構造化 |
| POST | `/conversations/{id}/issues/create` | SSE Issue GitHub 作成 |
| GET | `/conversations/{id}/issues` | Issue 一覧 |
| PATCH | `/issues/{id}` | Issue 更新 |
| DELETE | `/issues/{id}` | Issue 削除 |

### 4.13 監査
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/conversations/{id}/audit` | 監査ジョブ投入 (202) |
| GET | `/conversations/{id}/audits` | 監査レポート一覧 |
| GET | `/audits/{id}` | 監査レポート取得 |
| DELETE | `/audits/{id}` | 監査レポート削除 |

### 4.14 監視
| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/conversations/{id}/watch` | 監視ジョブ投入 (202) |
| GET | `/conversations/{id}/watches` | 監視レポート一覧 |
| GET | `/watches/{id}` | 監視レポート取得 |
| DELETE | `/watches/{id}` | 監視レポート削除 |

### 4.15 ジョブ / ヘルス
| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/health` | ヘルスチェック |
| GET | `/jobs/{job_id}` | ジョブステータス |

---

## 5. フロントエンド構成

### 5.1 ページ

| パス | 説明 |
|------|------|
| `/` | ランディング |
| `/login` | Google OAuth ログイン |
| `/auth/callback` | OAuth コールバック |
| `/auth/calendar-callback` | カレンダー OAuth コールバック |
| `/chat` | 会話一覧 + 新規作成 |
| `/chat/[conversationId]` | メインチャット + 10タブパイプラインパネル |
| `/vote/[shareToken]` | 公開投票ページ (認証不要) |

### 5.2 コンポーネント構成

```
components/
├── audits/        # AuditPanel
├── chat/          # MessageList, ChatInput
├── codes/         # CodePanel, CodeCard, CodeFileViewer
├── decisions/     # DecisionPanel, DecisionCard
├── designs/       # DesignPanel, DesignCard
├── issues/        # IssuePanel, IssueCard
├── pipeline/      # PipelineProgress (10ステップバー)
├── pull-requests/ # PRPanel, PRCard
├── sidebar/       # Sidebar (会話一覧)
├── specs/         # SpecPanel, SpecCard
├── tasks/         # TaskPanel, TaskCard
├── ui/            # shadcn/ui コンポーネント
├── voice/         # VoicePanel, VoiceTranscriptCard
├── votes/         # VoteSessionCard, VoteTally, VoteForm, MeetingSuggestion
└── watches/       # WatchPanel
```

### 5.3 SWR Hooks

| フック | データソース | 特記事項 |
|-------|------------|---------|
| `useChat` | SSE `/chat` | ストリーミング + メッセージ管理 |
| `useSpecs` | `/specs` | 仕様書 CRUD |
| `useDesigns` | `/designs` | 設計 CRUD |
| `useDecisions` | `/decisions` | 判断ポイント CRUD |
| `useTasks` | `/tasks` | タスク CRUD |
| `useCodes` | `/codes` | コード CRUD |
| `usePullRequests` | `/prs` | PR CRUD |
| `useVoiceTranscripts` | `/voice/transcripts` | SSE アップロード |
| `useGitHubIssues` | `/issues` | SSE 構造化 + 作成 |
| `useAudits` | `/audits` | 5秒ポーリング |
| `useWatches` | `/watches` | 5秒ポーリング |
| `useVoteSessions` | `/vote-sessions` | 投票管理 |
| `usePublicVote` | `/vote/{token}` | SSE リアルタイム集計 |

---

## 6. データモデル (主要テーブル)

| テーブル | 主な列 | 関連 |
|---------|-------|------|
| users | id, email, name, google_calendar_connected | — |
| conversations | id, user_id, title | → users |
| messages | id, conversation_id, role, content | → conversations |
| specifications | id, conversation_id, title, content, status | → conversations |
| designs | id, conversation_id, specification_id, title, content, status | → specifications |
| decision_points | id, conversation_id, design_id, question, status | → designs |
| decision_options | id, decision_point_id, label, pros, cons | → decision_points |
| vote_sessions | id, decision_point_id, status, share_token, deadline | → decision_points |
| votes | id, vote_session_id, option_id, voter_name | → vote_sessions |
| generated_tasks | id, conversation_id, design_id, title, priority, status, dependencies | → designs |
| generated_codes | id, conversation_id, task_id, content, status | → generated_tasks |
| pull_requests | id, conversation_id, code_id, pr_number, pr_url, branch_name, status | → generated_codes |
| voice_transcripts | id, conversation_id, filename, transcript, segments, classification, status | → conversations |
| github_issues | id, conversation_id, title, body, labels, issue_number, issue_url, status | → conversations |
| audit_reports | id, conversation_id, job_id, summary, findings, status | → conversations |
| watch_reports | id, conversation_id, job_id, summary, findings, watch_targets, status | → conversations |
| background_jobs | id, job_id, job_type, status, result, error | — |

---

## 7. 開発フェーズ履歴

| フェーズ | タスク | 内容 | 完了日 |
|---------|-------|------|--------|
| Phase 1 | T01 | プロジェクト概要設定 | 2026-03-14 |
| MVP | T02-T08 | Lexora拡張、FastAPI基盤、Chat、Spec Extractor、Decision Support、Next.js UI、Docker Compose | 2026-03-14 ~ 03-15 |
| Phase 2 | T09-T11 | Design Decomposer、Task Generator、フロントエンド統合 | 2026-03-15 |
| Phase 3 | T12-T14 | Code Generator、PR Creator、フロントエンド統合 | 2026-03-15 |
| Phase 4 | T15-T17 | Distributed Voting、カレンダー連携、フロントエンド統合 | 2026-03-15 |
| Phase 5 | T18-T20 | Voice Client、Non-Engineer Client、フロントエンド統合 | 2026-03-15 |
| Phase 6 | T21-T24 | Redis+ARQ基盤、Internal Audit Agent、External Watch Agent、フロントエンド統合 | 2026-03-15 ~ 03-16 |

**全 7 フェーズ、24 タスク完了。**

---

## 8. デプロイ構成

```yaml
# docker-compose.yml
services:
  postgres:    # PostgreSQL 16
  redis:       # Redis 7 Alpine
  api:         # FastAPI (uvicorn)
  web:         # Next.js 15 (standalone)
  worker:      # ARQ ワーカー (audit/watch ジョブ)
```

環境変数は `.env` で管理。Alembic マイグレーションは API コンテナ起動時に自動実行。

---

## 9. テスト

- バックエンド: pytest (73 テスト通過)
- フロントエンド: TypeScript コンパイルチェック (`tsc --noEmit`) + Next.js ビルド (`npm run build`)

## 移行時の注記（2026-09-10）

Drive 原本（`1k5dM8av5earDuxPyCF3Jjl9r2oWvJ9N3g_sP52kHx9o`）の逐語移行。
`docs/` はこの移行で新設した（[[platform:reconciliation-small-projects]] §2）。

**`status: archived` の理由: 本書は 2026-03-16 の点在スナップショットで、repo は 13 フェーズ
先へ進んでいる。** 冒頭が自ら「Phase 6 完了時点 (2026-03-16) の現状仕様」と宣言しているとおり。

repo の最終コミットは **2026-03-21 "feat: Proactive Tech Watch Agent (Phase 19)"**。
本書の 5 日後で、Phase 6 → Phase 19。

### 本書が知らない router が 8 本ある

`apps/api/src/api/routers/` の実際:

| 本書にある | 本書に無い |
|---|---|
| audits / chat / codes / conversations / decisions / designs / github_issues / health / jobs / pull_requests / specifications / tasks / voice / votes / watches | **activities / costs / dashboard / github_repos / metrics / notifications / spec_reviews / teams** |

alembic も本書の想定を超えて `021_add_watch_trigger_type` まで進んでいる
（本書の範囲は `013_add_watch_reports_table` 相当まで）。

∴ **§4 API 一覧・§5 フロントエンド構成・§6 データモデルを現状として読まないこと。**
実装を知りたいなら `apps/api/src/api/routers/` と `apps/api/alembic/versions/` を直接見る方が速く、正確。

### それでも残す理由

**本書は「Phase 6 の時点で 10 ステップが一気通貫で動いていた」ことの証拠である。**
その後 8 本の router が足されたが、それらは横断機能（コスト・メトリクス・通知・チーム・
ダッシュボード）で、パイプライン本体ではない。∴ 本書の §3 は**パイプラインの完成形が
どこだったか**を示す基準点として今も使える。

§9 の「pytest 73 テスト通過」も、Phase 6 時点のテスト規模を記録した唯一の数字。
