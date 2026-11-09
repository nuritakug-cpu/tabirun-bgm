# TOP RUN AGUI 開発マスター v3（2026-11-10）

このファイルは、新しい会話の最初に必ず読むこと。ここに書いたことが、このプロジェクトの決まりと現状の正本。
主体は Claude、ChatGPT はサブ（指示は Claude が書き、結果を Claude が確認する）。

---

## 1. 目的・構想

- 本人はランニングを通して多くを教わり、人生の豊かさを実感している。中学時代に駅伝選手として練習したが膝の故障で本戦に出られなかった経験があり、その後マラソンから走りを再開した。ボランティアで関わる小学生クラブ、息子の活動を通して、地域のクラブ活動を支えたいという思いから始まった。
- TOP RUN AGUI（中学生中心・20〜40人規模）の連絡・大会運営・記録を、無料で、安全に回すための仕組み。
- **当初からの目的**：PORTAL と EVENT BASE の相互のデータ共有。
  - PORTAL でイベントを作成し、EVENT BASE を接続するのが基本。
  - PORTAL で出走登録 → EVENT BASE で記録保存 → PORTAL の個人記録（pastRecords）として保存。
  - 紐付けは PORTAL で行う。大会をプルダウンで選んで記録を閲覧できる。

## 2. 根本の方針（どの修正でも必ず照らし合わせる）

1. 無料で運営する（Firebase 無料枠：ダウンロード月10GB・保存1GB・同時接続100 の範囲）。
2. 中学生の個人情報を守る。漏洩・不正アクセスを防ぐ。
3. やめた人（過去の入会者）の登録を削除できるようにする（**未実装**）。
4. 競技記録は公開の大会結果でも得られるので扱ってよい。それ以外は守る。
5. 位置情報・チャット内容は、本人と結び付かないのが望ましい。

## 3. 進め方のルール（本人からのお願い）

- ファイルを作る前に、①何を ②どう直すか ③Firebase の通信量への影響 ④端末・他画面への影響、を短く出して確認を取る。小さな修正でも③は必ず書く。
- 通信量（Firebase）を抑えていない対応は NG。常時監視（onValue）を増やさない。
- 今の方式を置き換える極端な方針転換をしない。基本は残し、足りない部分を補う。
- 頼んでいない制限・機能を入れない。表示が正しく出ることが最優先。
- 分かっている問題は次の版に回さず、その場で直す。
- 修正はまとめて1つの版にする（GitHub Pages の公開が遅くなるため、細かく出しすぎない）。
- 本番用と試作用を分けて作らない。ZIP で渡さない。
- 渡すファイル名は記号なし・版数入り（例：TOPRUNPORTALv378.html）。ダウンロードするとアンダーバーが消えるため。
- 実機（iPhone）で確かめていないことは、確かめていないと明記する。見た目の変更は、5つのテーマ（オリジナル・マット・ウィンター・ブルー・さくら）で崩れないこと。
- 歯車の中の版表示（portalVersionPill）を毎回更新する。
- 画面操作の説明は、画面の順に具体的に書く。

## 4. 構成

### GitHub / 公開
- リポジトリ：nuritakug-cpu/tabirun-bgm（GitHub Pages）。同じリポジトリの旅ラン（tabirun）のファイルには触れない。
- 公開URLの基本：`https://nuritakug-cpu.github.io/tabirun-bgm/`
- 名前を自動で戻す仕組み（.github/workflows）
  - auto-rename-ekiden：`EVENTBASEEKIDENNEXTP*.html` → `EVENT_BASE_EKIDEN_NEXT_P<n>_<名前>.html`
  - auto-rename-portal：`TOPRUNPORTALv*.html` → `TOP_RUN_PORTAL.html`（上書き）
  - auto-rename-production：`EVENTBASEPRODUCTION*.html` → `EVENT_BASE_PRODUCTION.html`（上書き）
- 片付けの仕組み（cleanup-old-eventbase / cleanup-step2 / cleanup-step3）は **Disabled（絶対に有効にしない）**。過去にこれで本番用が消えた。

### アプリ
| 名前 | GitHub上のファイル | 役割 |
|---|---|---|
| PORTAL | TOP_RUN_PORTAL.html | クラブの唯一の入口。登録・出欠・チャット・お知らせ・出走登録・個人記録・管理 |
| EVENT BASE（本番用） | EVENT_BASE_PRODUCTION.html | 普通の大会（記録会など）の運営。保存版モードあり |
| 駅伝BASE | EVENT_BASE_EKIDEN_NEXT_P149_COURSEMAP.html | 駅伝の運営（コース図・計測・成績表） |
| 保存版データ | TOPRUNARCHIVE<日付>v<n>.json | 終わった大会の保存版（EVENT BASE の保存版モードで表示） |

- PORTAL・EVENT BASE・駅伝BASE は、同じ Firebase（匿名認証）・同じ本人ID（uid / profileId）を使う。新しい本人IDを作らない。
- 通知は Cloudflare Worker（top-run-notify）。

### Firebase の主な保存場所
- PORTAL：`portalCommon/topRun/…`（memberAccess, memberRequests, nameBook, eventItems, practices, practiceResponses, eventResponses, chat, rooms, chatImages, chatImageThumbs, chatImageIndex, chatImageQuota, pastRecords, clubRoster, familyOf, bindings など）
- プロフィール：`profiles/<uid>/portalSelf/basicProfile`（性別・学年・ゼッケン・ふりがな）
- EVENT BASE / 駅伝：`events/<大会ID>/…`（config, players, timingRecords, notices, …）、資料PDF：`eventFiles/<大会ID>/…`、`eventEkiden/<大会ID>/state`
- Rules：**Firebase に入っている現行版が正本**（Firebase コンソール →「構築」→「Realtime Database」→「ルール」から全文コピーで出す）。2026-11-10 に確認したところ、v370（DNF・写真の枚数制限 chatImageQuota）は入っていなかった。v370 の手元ファイルはない。最新は **TOPRUNRULESv371.json**（現行版＋イベントの archive 1項目）。

## 5. データの流れ（記録）

- **記録の正本は PORTAL の個人記録（portalCommon/topRun/pastRecords/<uid>/<記録ID>）**。本人・保護者（familyOf）・管理者が読める（Rules で確認済み）。
- 駅伝BASE P149：「EVENT BASEへ結果を渡す」で、本人とつながっている選手の記録を pastRecords に自動保存（記録ID＝`local-flow-claim-<大会ID>-<出走カードID>`）。
- 本人とつながっていない人（旧 EVENT BASE から登録・PORTAL未登録）は、PORTAL の「記録の紐付け」で後から付ける。そのため **Firebase の過去大会の EVENT BASE データ（events/<id>）は消さない**。
- PORTAL v376：開発者の端末で、P149より前の大会の取り込み漏れを1回だけ自動で埋める。
- 公認の判定：PORTAL のイベントの「公認記録の区分」。豊川（eventbase_mu4ujce3_xxx1）は定数で公認扱い（v368）。駅伝（半田・第75回）は非公認。
- 駅伝のタイム表記：60分以上は「時:分:秒」（1:05:05）、差は分秒（+1:20）。

## 6. 大会の流れ（これからの基本）

1. PORTAL でイベントを作成（区分：大会、公認/非公認、接続：EVENT BASE を使用、リンク：`…/EVENT_BASE_PRODUCTION.html?event=<大会ID>`）
2. PORTAL から出走登録、EVENT BASE（または駅伝BASE）で運営・記録
3. 結果を渡す → PORTAL の個人記録へ（駅伝BASE は自動）
4. 終わったら、PORTAL のイベントから EVENT BASE を開き、HOME の一番下「この大会を保存版にする」→「保存版を作る」→ JSON を GitHub にアップロード
5. PORTAL の管理画面でイベントを修正し、正式大会URLの下の「保存版（大会が終わったら）」に保存版のURLを貼って保存する（PORTAL v384〜）。**正式大会URLは変えない**（記録の紐付け・本人確認・カレンダーが大会IDを使うため）。保存版が入った大会は「EVENT BASEを開く」で保存版が開く。空欄にすると元に戻る。

- 保存版は GitHub で**誰でも見られる**。そのため、入れてよいものだけを選んで入れる（v180〜、形式 eb-archive-v2）。
  - 入れる：大会情報（大会名・開催日・時刻・状態・会場・駐車場・お知らせの題名と本文・配色）、資料は大会公式のリンクだけ（PDF は入れない）、選手は名前と記録（種目・タイム・正式/速報・DNS）だけ。
  - 入れない：本人ID・運営者名・性別・学年・コメント・目標タイム・日時・組/レーン/時刻・PDF・大会ID。
  - 記録のない選手は入れない。選手は出走順に並べて保存する。
- 作り方：歯車 →「設定・管理」→「保存版を作る」（大会結果一覧の下、運営者だけ）。資料は先に「その他資料」へ公式の外部リンクとして登録しておく。
- 保存版モード：Firebase に接続しない。番号入力なし。見るだけ（HOME・MAP）。予定・LIVE・CHAT・設定は出さない。右上に「結果一覧」（男女別にしない・出走順）。
- EVENT BASE を直すときは、保存版モードでも崩れないかを必ず確認する。保存版データ（eb-archive-v2）の項目の名前・意味は変えない。項目を増やすときは、公開してよいものかを必ず確かめる。
- 駅伝の保存版は未対応（駅伝BASE に同じ仕組みを作る予定）。

## 7. 現在の版（2026-11-10 時点で Claude が渡した最新）

| 対象 | 版 | 渡したファイル | 主な内容 |
|---|---|---|---|
| PORTAL | v384 | TOPRUNPORTALv384.html | イベントに「保存版」（archive）を追加。土台は GitHub の v383。※v379〜v383 は Claude 以外で作られた見た目だけの版（文字・Android の表示。動作・Firebase は変更なしと記載） |
| PORTAL（旧） | v378 | TOPRUNPORTALv378.html | プロフィール必須化（名前・ふりがな・性別・学年）、通信量削減第1段階（v376）、モック用書き出し（v377）、Android軽量化（v375）、下タブ固定（v373）、管理者の選手一覧（v364/v374）、SB表示（v372）など |
| Rules | v371 | TOPRUNRULESv371.json | Firebase の現行版に、イベントの archive（TOPRUNARCHIVE…の名前だけ）を追加。※v370（写真の制限・DNF）は入っていない |
| EVENT BASE | v180 | EVENTBASEPRODUCTIONv4.html | 保存版を公開してよいものだけの形（eb-archive-v2）に変更、結果一覧は出走順、保存版を作るは管理画面へ、「PORTALへ戻る」削除 |
| 保存版（豊川） | v2 | TOPRUNARCHIVE20261004v2.json | v180 と同じ形。資料は大会要項・スタートリストの公式リンク。※v1 は個人情報を含むため使わない（GitHub から削除） |
| 駅伝BASE | P149 | EVENTBASEEKIDENNEXTP149COURSEMAP.html | 結果を渡すと PORTAL の個人記録へ自動保存（P148 は保存先の誤りあり、使わない） |

- GitHub に実際に入っている版は、PORTAL は歯車の中、EVENT BASE は HOME の一番下、駅伝BASE はマップエディタ上部で確認する。

## 8. 決まった仕様・デザイン

- 保存ボタン：PORTAL 全体で共通の形（高さ40・丸み・細身・テーマ色）。保存したら必ず「✓ 保存しました」を上に表示。
- プロフィール：必須＝名前・ふりがな（姓・名）・性別・学年/保護者。任意＝ゼッケンNo・チャット名。未入力の必須欄へ移動して赤枠で示す。そろったら欄を閉じる。未入力の人は開いた状態で「基本プロフィールを入力してください」。
- チャットの写真：1日10枚・1回5枚（Firebase 側で制限）。30日で削除。
- リアクション：LINE スタンプが手本。正方形を基本、4文字以上は2行。書体は太字を含め使い分け（Dela Gothic One・Reggae One・RocknRoll One・明朝・筆文字）。ロゴ＋絵文字は、ロゴはそのまま、絵文字だけなめらかな白縁。
- 記録推移：グラフが主役。下に小さく SB・直近・差。下がっているときは控えめ、SB更新・PB更新・大幅更新（800m 2秒・1000m 3秒・1500m以上 5秒）・10秒以上の5段階。更新時はグラフを描き終えてから演出。年度は4/1〜翌3/31、SBは同年度、PBは全記録。
- 公認ベスト：金の枠・★OFFICIAL。自己ベストが公認なら日付の横に小さく「公認」。
- 下のメニュー：JS で位置を動かさない（bottom:0 固定・safe-area）。
- Android：背景ぼかし（backdrop-filter）を使わない。今後のテーマ差し替えでも、ぼかしに頼らない作りにする。
- PORTAL のテーマ（背景デザイン）は今後差し替える予定。

## 9. 消してはいけないもの

- GitHub：TOP_RUN_PORTAL.html、EVENT_BASE_PRODUCTION.html、現在の駅伝BASE（P149）、TOPRUNARCHIVE*.json（保存版）、.github/workflows の auto-rename 3つ
- Firebase：過去大会の EVENT BASE データ（events/<大会ID>、eventFiles）、pastRecords、profiles
- 「PORTALへ戻る」ボタンは不要（v180 で削除）。
- 古い EVENT BASE のホーム画面アイコンは使えない（メンバーには「アイコンを削除し、PORTAL のイベントから開く」と案内）。

## 10. 残っている課題（優先順の目安）

1. 豊川：Rules v371 を公開 → PORTAL v384 をアップロード → 豊川のイベントの「保存版」に v2 の URL を入れて保存 → 開いて確認。GitHub の TOPRUNARCHIVE20261004v1.json を削除（個人情報を含む。履歴に残る件の対応を決める）。EVENT BASE v180・PORTAL v384 の実機確認。
2. 半田（第2回・駅伝）と第75回：駅伝BASE に保存版の仕組みを作る（駅伝用の表示：チーム・区間）。EVENT BASE と同じく、公開してよいものだけを入れる。
3. 通信量 第2段階：開くたびの約0.5MB の読み込み（練習の回答・イベント・チャットなど）を、更新があったものだけ読む形にする（Rules 追加が必要）。v376 の効果を通信量メーターで確認してから。
4. やめた人の登録削除（未実装）。
5. 位置情報・チャットと本人の結び付きの扱いを決める（方針5）。
6. 写真だけのチャットで通知が来ない件（未解決。文字だけなら届くかの確認待ち）。
7. Rules v370 の内容（写真 1日10枚・1回5枚の制限 chatImageQuota、DNF）が Firebase に入っていない。手元に v370 のファイルもない。PORTAL のコードと照らして作り直すかを決める（写真の制限は今、Firebase 側で効いていない）。
8. メンバーのプロフィールの性別の入力をそろえる（男女別表示に必要）。
9. 見た目の設定の整理（PORTAL に style が約200か所・影が約230か所たまっている。動作の重さの原因）。

## 11. 新しい会話の始め方

1. このマスターを読む。
2. 作業する対象の最新ファイル（PORTAL / EVENT BASE / 駅伝BASE / Rules のうち必要なもの）を、最初に1回だけアップロードする。
3. 決まったこと・版が進んだことは、Claude がこのマスターを更新して渡す（ファイル名の版数を上げる）。
