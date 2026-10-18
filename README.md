# Bangumi_Auto_Rename

为 **Jellyfin** 设计的动漫 / 剧集 / 电影自动整理工具。
动漫元数据优先来自 **Bangumi（bgm.tv）**，失败时回退 TMDB；根据元数据自动生成 Jellyfin 规范的目录结构与文件名。支持 qBittorrent 下载完成后自动整理，默认使用 **硬链接**，不影响做种。

[![Python](https://img.shields.io/badge/Python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0--or--later-green.svg)](LICENSE)
[![Jellyfin](https://img.shields.io/badge/Jellyfin-first-00A4DC.svg)](https://jellyfin.org/)
[![Bangumi](https://img.shields.io/badge/Metadata-Bangumi-F09199.svg)](https://bgm.tv/)

> 本项目是 [KimigaiiWuyi/Bangumi_Auto_Rename](https://github.com/KimigaiiWuyi/Bangumi_Auto_Rename) 的修改版，由 [EunoiaCody](https://github.com/EunoiaCody/Bangumi_Auto_Rename) 维护。原始版权归 KimigaiiWuyi 所有，修改版同样以 GPL-3.0-or-later 发布，详见 [NOTICE](NOTICE)。

## 特性

- **Jellyfin 优先**：`Series (Year)/Season 01/Series (Year) S01E01 - Title.ext`，特典进入 `Season 00`，OP/ED/PV 等进入 `extras/`。
- **Bangumi 元数据优先**：支持搜索、季度关系链（前传 / 续集）、章节标题、SP / OP / ED 分类。
- **TMDB 兜底**：Bangumi 不可用或无结果时自动回退 TMDB；非动漫内容始终使用 TMDB。
- **qBittorrent 自动整理**：完成时触发 `/sendTask`，默认硬链接，绝不移动 / 删除做种文件。
- **硬链接安全**：同盘直接硬链接；跨盘按配置复制 / 软链接 / 跳过，`copy` 为默认。
- **重复触发抑制**：按 infohash + 路径去重，避免重复整理。
- **复杂合集支持**：多季合集、剧场版、OVA、特典、外挂字幕。
- **AI 辅助（可选）**：OpenAI 兼容 API / Google Gemini，用于 BD 分集与元数据分季不一致的情况。
- **不生成 NFO / 图片**：本项目只负责“用元数据把文件放到正确位置、起正确名字”，刮削交给 Jellyfin。

## 元数据 → 文件布局

| 元数据 | 输出 |
|---|---|
| `series.name` / `series.year` | `Series Name (Year)/` |
| `season.season_number` | `Season 00`、`Season 01`、`Season 02` … |
| `episode.episode_number` | `S01E01`、`S01E02` … |
| `episode.title` | 文件名末尾 ` - 标题`（可配置语言 / 关闭） |
| `episode.type = special` | `Season 00/Series (Year) S00E01 - 特典.ext` |
| `episode.type = op/ed/pv/other` | `extras/` |
| `movie.name` / `movie.year` | `Movie Name (Year)/Movie Name (Year).ext` |
| 多文件电影（CD1/CD2） | `Movie Name (Year) - cd1.ext`、`- part1.ext` |
| 外挂字幕 / 音轨 | 与新视频同名，保留 `.zh.ass`、`.en.srt` 等后缀 |

示例：

```text
Anime/
└── 葬送的芙莉莲 (2023)/
    ├── Season 00/
    │   └── 葬送的芙莉莲 (2023) S00E01 - OVA.mkv
    ├── Season 01/
    │   ├── 葬送的芙莉莲 (2023) S01E01 - 冒险的结束.mkv
    │   ├── 葬送的芙莉莲 (2023) S01E01 - 冒险的结束.zh.ass
    │   └── 葬送的芙莉莲 (2023) S01E02 - 未必是魔法.mkv
    └── extras/
        └── NCOP.mkv

Movies/
└── 铃芽之旅 (2022)/
    └── 铃芽之旅 (2022).mkv
```

## 工作原理

```text
本地路径
  ↓ 清理发布组标签 / 年份 / 季集号
Bangumi 搜索（动画，type=2）
  ↓ 命中：读取条目 + 前传/续集关系链 + 章节
  ↓ 未命中/不可用：TMDB 搜索与季度/剧集
统一元数据（Series / Season / Episode）
  ↓
Jellyfin 命名（目录 + Season NN + SxxExx + 标题）
  ↓
硬链接（默认）/ 复制 / 剪切
```

- **季号**：Bangumi 一个 subject 通常只对应一季，程序沿 `前传` / `续集` 关系链推导完整季度顺序。
- **集号**：使用条目章节的 `ep`；`4.5` 等非整数集归入特典 / extras。
- **标题来源**：`naming_title_source=auto` 时，若 TMDB 可用则优先使用 Jellyfin 更容易识别的 TMDB 标题，否则使用 Bangumi 中文名；可改为 `bangumi` 或 `tmdb`。

## Jellyfin 配置

1. 新建 **Shows** 库，指向 `anime_path`（动漫剧集）和 `bangumi_path`（真人剧集）。
2. 新建 **Movies** 库，指向 `anime_movie_path`（动漫电影）和 `movie_path`（真人电影）。
3. 目录结构无需手动整理，程序会生成 `Series (Year)/Season NN/`。
4. 特典放在 `Season 00`；OP/ED/PV/CM 放在 `extras/`，Jellyfin 会自动识别为 extras。
5. **不生成 NFO**。若希望 Jellyfin 显示 Bangumi 的标题 / 简介，推荐安装第三方插件 [kookxiang/jellyfin-plugin-bangumi](https://github.com/kookxiang/jellyfin-plugin-bangumi)；未安装时 Jellyfin 默认刮 TMDB，建议保持 `naming_title_source=tmdb` 或 `auto`。

## 安装

### 方式一：Python Web 版（推荐）

要求 Python `>=3.10` 与 Git。

```bash
git clone https://github.com/EunoiaCody/Bangumi_Auto_Rename.git -b web
cd Bangumi_Auto_Rename

# Linux / macOS
pip install -r requirements_docker.txt

# Windows
pip install -r requirements.txt

# 或使用 PDM
pdm install
```

启动：

```bash
python -m src.start
# 或
pdm start
```

打开 `http://127.0.0.1:5999`。

### 方式二：Docker

```bash
docker build -t bangumi-auto-rename .

docker run -d --name bangumi-auto-rename \
  -p 5999:5999 \
  -v /host/media:/media \
  -v /host/bangumi-data:/Bangumi_Auto_Rename/data \
  bangumi-auto-rename
```

- 将下载目录与媒体库挂载到容器内，建议都放在 `/media` 下，便于硬链接。
- `data/` 保存配置、任务记录、日志与缓存，务必持久化。
- 容器内 `docker_mnt` 默认为 `/media`，可在配置页修改。

## 配置

启动后点击右上角 **配置**。配置保存在 `data/config.json`，旧配置会自动补齐新键。

### 基础

| 键 | 默认值 | 说明 |
|---|---|---|
| `api_key` | 空 | TMDB API Key，用于兜底与非动漫内容 |
| `anime_path` | 空 | 动漫剧集库路径 |
| `bangumi_path` | 空 | 真人剧集库路径 |
| `anime_movie_path` | 空 | 动漫电影库路径 |
| `movie_path` | 空 | 真人电影库路径 |
| `mode` | `链接` | `链接` / `复制` / `剪切` |
| `metadata_source` | `bangumi` | `bangumi` 优先，或 `tmdb` |
| `naming_title_source` | `auto` | `auto` / `bangumi` / `tmdb` |
| `rename_style` | `jellyfin` | `jellyfin` 或兼容旧格式的 `legacy` |
| `filename_title_language` | `zh` | `zh` / `ja` / `none` |
| `docker_mnt` | `/media` | Docker 文件选择器根目录 |
| `log_level` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

### Bangumi

| 键 | 默认值 | 说明 |
|---|---|---|
| `bangumi_access_token` | 空 | 可选；公开数据无需令牌 |
| `bangumi_base_url` | `https://api.bgm.tv` | API 地址 |
| `bangumi_user_agent` | 空 | 可选；留空使用内置 UA |

### qBittorrent

| 键 | 默认值 | 说明 |
|---|---|---|
| `qb_safe_mode` | `true` | 强制硬链接，禁止剪切，保护做种 |
| `qb_link_fallback` | `copy` | 跨盘时 `copy` / `symlink` / `skip` |
| `qb_category_anime` | `anime` | qB 分类映射为动漫 |
| `qb_category_movie` | `movie` | qB 分类映射为电影 |
| `qb_category_ignore` | `no_process` | 忽略的分类 |

### AI（可选）

- `ai_enabled`：启用 AI 识别。
- `ai_provider`：`openai` 或 `gemini`。
- OpenAI：`ai_api_key`、`ai_base_url`、`ai_model`、`ai_temperature`、`openai_output_format`。
- Gemini：`gemini_api_key`、`gemini_base_url`、`gemini_model`、`gemini_temperature`。
- `ai_confidence_threshold`：`High` / `Medium` / `Low`。
- `ai_auto_save`：保存分析 JSON 到 `data/ai_analysis/`。

> ⚠️ AI 识别为实验性功能，**不要在 `剪切` 模式下启用**；qBittorrent 安全模式会强制 `链接`。

## 使用

1. 打开 Web UI，先完成配置。
2. 点击 **添加任务**，选择下载完成的目录或单个视频。
3. 任务进入队列；表格显示“排队中 / 处理中 / 成功 / 失败”。
4. 失败任务可 **重试**；也可 **编辑** 识别名称、季度、Bangumi 条目 ID 后重新处理。
5. 删除任务只删除 `data/task` 与 `data/record` 记录，不会删除媒体文件。

### 手动指定 Bangumi 条目

如果自动匹配错误，可在任务编辑页填写 **Bangumi 条目 ID**（`https://bgm.tv/subject/XXXX` 中的数字），重新处理即可强制使用该条目。

## qBittorrent 自动整理

qBittorrent → **工具 → 设置 → 下载 → Torrent 完成时运行**：

```bash
curl -s --data-urlencode "path=%F" \
     --data-urlencode "tags=%G" \
     --data-urlencode "category=%L" \
     --data-urlencode "hash=%I" \
     --data-urlencode "name=%N" \
     "http://127.0.0.1:5999/sendTask"
```

- `%F`：种子内容路径（文件或根目录）。
- `%G`：标签；包含 `anime`、`动漫`、`动画`、`bangumi` 时按动漫处理，`movie`、`电影`、`剧场版` 按电影处理。
- `%L`：分类；可在配置页映射。
- `%I`：infohash，用于重复触发去重。
- `%N`：种子名称，作为 `path` 缺失时的兜底。
- 需要忽略某个种子时，加 `no_process` 标签。

**做种安全**：

- 默认 `qb_safe_mode=true`，即使全局模式是 `剪切`，qB 触发也强制 `链接`。
- 源文件只读，不会被重命名或删除。
- 同盘硬链接；跨盘按 `qb_link_fallback` 回退，默认复制。
- 目标已存在时跳过，不覆盖。
- 过滤 `.part`、`.!qB`、`_____padding_file_` 等未完成 / 临时文件。
- 多个种子同时完成时进入单线程队列，避免同一剧集目录竞争。

## AI 识别说明

- 支持 OpenAI 兼容接口与 Google Gemini。
- 推荐模型：`deepseek-reasoner`（OpenAI 兼容）或 `gemini-2.5-flash`（Gemini）。
- OpenAI 输出格式：`function_calling`（最稳定）/ `json_object` / `structured_output` / `text`。
- AI 结果字段已统一为 `season` / `episode`，旧版 `tmdb_season` / `tmdb_episode` 分析文件仍可读取。
- 低置信度结果会记录到日志；AI 失败或无有效映射时自动回退传统流程。

## 常见问题

**Q：需要 TMDB Key 吗？**
A：只看动漫时，Bangumi 公开接口即可工作；建议仍配置 TMDB Key，用于兜底、动漫电影标题与非动漫内容。

**Q：Jellyfin 显示的标题和文件名不一致？**
A：本项目不生成 NFO。Jellyfin 默认使用 TMDB 刮削；可将 `naming_title_source` 设为 `tmdb`/`auto`，或安装 Bangumi 插件。若使用插件，设为 `bangumi`。

**Q：硬链接失败 / 跨盘？**
A：硬链接要求源与目标在同一文件系统。跨盘时按 `qb_link_fallback` 处理，默认复制；也可改为 `symlink` 或 `skip`。建议把下载目录和媒体库放在同一磁盘。

**Q：Bangumi 搜索不到 / 匹配错误？**
A：在任务编辑页填写 Bangumi 条目 ID 强制指定；或把 `metadata_source` 改为 `tmdb`。日志级别设为 `DEBUG` 可查看候选打分。

**Q：qBittorrent 重复触发怎么办？**
A：程序按 infohash + 路径去重，已成功任务直接跳过；需要强制重跑时在请求中加 `force=1`。

**Q：会生成 NFO / 海报吗？**
A：不会。只创建目录、视频与同名外挂字幕/音轨的硬链接或副本。

**Q：旧版本目录会被覆盖吗？**
A：不会覆盖已存在目标。默认 `rename_style=jellyfin` 会生成新命名；需要旧格式时切换为 `legacy`。

## 开发与测试

```bash
python -m compileall src
pytest tests -q
python -m src.start
```

- 测试用例：`tests/test_naming.py`、`tests/test_bangumi_provider.py`、`tests/test_resolver.py`、`tests/test_qbittorrent_payload.py`、`tests/test_transfer.py`、`tests/test_process_layout.py`。
- AI 手动测试：`python tests/test_ai_recognition.py --mode manual --path ...`，详见 [tests/README_AI_Testing.md](tests/README_AI_Testing.md)。
- 开发说明：[AGENTS.md](AGENTS.md)。

## 版权与致谢

- 原始项目：[KimigaiiWuyi/Bangumi_Auto_Rename](https://github.com/KimigaiiWuyi/Bangumi_Auto_Rename)
- 原始作者：**KimigaiiWuyi** <444835641@qq.com>
- 修改版维护：[EunoiaCody](https://github.com/EunoiaCody/Bangumi_Auto_Rename)
- 许可证：[GPL-3.0-or-later](LICENSE)（`LICENSE` 原文未修改）
- 修改说明见 [NOTICE](NOTICE)。

本项目仅供学习与个人媒体库整理使用，请勿用于商业用途。
