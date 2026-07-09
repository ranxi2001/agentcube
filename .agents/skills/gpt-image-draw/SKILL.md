---
name: gpt-image-draw
description: AI 绘图技能，使用 api.ai.tosky.top 图片 API 的 gpt-image-2 原生生成/编辑图片。当用户明确要求“gpt-image-2”、GPT 系列绘图、带文字图片、中文信息图、GitHub banner、海报、封面、插画、参考图改图时使用。gpt-image-2 文字生成能力强，必须优先直接原生生成包含标题/文案的最终图片；不要绕路用 SVG、HTML/CSS、canvas、本地贴字、后期叠字或先画背景再拼文字，除非用户明确要求矢量/代码资产。当前 gpt-image-2 输出固定为 1.5K 档，不再支持 1~4K 自定义尺寸；按比例使用官方固定分辨率，quality 参数无效。
---

# GPT Image Draw - gpt-image-2 原生图文生成技能

使用 `https://api.ai.tosky.top/v1` 图片 API 调用 `gpt-image-2` 原生生成/编辑图片。适合带文字图片、中文信息图、GitHub banner、投研图、社媒海报、封面图、插画和参考图改图。

## 核心原则

- **直接生成最终图**：需要标题、Logo 字样、海报文案、信息图文字、README banner 标题时，把文字写进 prompt，让 `gpt-image-2` 原生生成带文字的图片。
- **不要绕路**：不要用 SVG、HTML/CSS、canvas、Pillow、本地字体贴字、后期叠字、先生成无字背景再拼文字等替代方案。
- **不要预设文字会变形**：`gpt-image-2` 的图中文字能力足够强，默认信任模型直接出图。若文字或设计不满意，调整 prompt 后重新生成/编辑，而不是改用代码贴字。
- **只在用户明确要求时使用代码/矢量方案**：例如用户指定 SVG、可编辑矢量、HTML/CSS 组件、纯代码图形，才离开原生图片生成路径。

## 什么时候用

- 用户明确说：`gpt-image-2`、`GPT 图片`、`用 gpt-image 画`
- 用户要带文字图片、GitHub 项目 banner、README 顶图、标题图、封面、商业海报、中文信息图、投研汇报图
- 用户提供参考图，希望基于参考图做风格迁移、局部改图、IP 延展
- `banana-draw` 的 Gemini 风格不合适，或用户指定 GPT 图像模型

如果用户只是泛泛说“画图”，可在 `banana-draw` 与本技能之间选择：
- 便宜快速、Gemini 风格：`banana-draw`
- GPT 图像、中文信息图、用户点名模型：`gpt-image-draw`

## API 配置

- **Base URL:** `https://api.ai.tosky.top/v1`
- **图片生成:** `POST /images/generations`
- **图片编辑:** `POST /images/edits`
- **默认模型:** `gpt-image-2`
- **鉴权:** `Authorization: Bearer <API_KEY>`
- **Key 来源:** `OPENAI_API_KEY` 或 `IMAGE_API_KEY`，支持环境变量、当前目录 `.env`、仓库 `.env`、`~/.hermes/.env`

安全要求：不要把 API Key、token、cookie 写入技能文档、命令行历史、Git 提交或最终回复。`draw.py` 会读取环境变量和 `.env`，但不会打印 key。

## API 请求规范

图片生成：

```json
{"model":"gpt-image-2","prompt":"图片描述","n":1,"size":"1254x1254"}
```

图片编辑使用同一模型和 `size` 参数，通过 `--ref` 传入参考图；脚本会调用 `/v1/images/edits`。

响应字段：优先读取 `data[0].b64_json`，解码后保存为 `.png`。

## 尺寸与长宽比边界

`gpt-image-2` 官方侧已把输出固定到 **1.5K 档**：不再支持 `1~4K` 自定义尺寸，`quality` 参数也不会改变输出质量/分辨率。现在只按长宽比选择对应固定分辨率。

当前固定分辨率：

| 比例 | 实际 size |
|:--|:--|
| `1:1` / `square` | `1254x1254` |
| `2:3` | `1024x1536` |
| `3:2` | `1536x1024` |
| `3:4` | `1086x1448` |
| `4:3` | `1448x1086` |
| `4:5` | `1122x1402` |
| `5:4` | `1402x1122` |
| `16:9` / `landscape` | `1672x941` |
| `9:16` / `portrait` | `941x1672` |
| `21:9` | `1915x821` |
| `9:21` | `821x1915` |

边界注意：

- 不要再提示或尝试 `1536x512`、`2048x2048`、`3840x2160`、`1K/2K/4K` 等自定义尺寸；官方侧会忽略、拒绝或降级到固定档。
- 不要使用 `quality` 参数；当前对 `gpt-image-2` 无效。
- GitHub README banner 优先使用 `21:9`（`1915x821`）生成宽横幅构图，再按平台需要裁切；不要依赖原生 `3:1` 自定义画布。
- 如果用户介意 1.5K 限制，可建议改用“绘画分组上架 | gpt-image-2”、官方优惠或官方原价分组，而不是在当前 default 分组硬传更大尺寸。
- `draw.py` 会把 `-s` 的比例别名映射为上述固定分辨率；直接传实际尺寸时也应只传表内值。

## 文件

```text
gpt-image-draw/
├── SKILL.md
└── draw.py
```

## 安装依赖

```bash
pip install openai
```

如果仓库已有虚拟环境，优先使用项目环境：

```bash
python -m pip install openai
```

## 基础用法

```bash
python gpt-image-draw/draw.py "画一只在月球上喝咖啡的猫，赛博朋克风格" -o /tmp/cat.png
```

指定尺寸：

```bash
# 正方形
python gpt-image-draw/draw.py "极简科技 logo" -s 1:1 -o /tmp/logo.png

# 横版 16:9
python gpt-image-draw/draw.py "AI 数据中心横版海报" -s 16:9 -o /tmp/poster.png

# GitHub README banner，使用 21:9 宽横幅
python gpt-image-draw/draw.py "GitHub README banner：OfferPilot，AI Interview Diagnosis Agent，21:9 宽横幅构图" -s 21:9 -o /tmp/banner.png

# 竖版 9:16，适合小红书/手机海报
python gpt-image-draw/draw.py "中文信息图：AI 时代存储行业重估" -s 9:16 -o /tmp/infographic.png

# 4:3
python gpt-image-draw/draw.py "课堂讲义风格知识图" -s 4:3 -o /tmp/slide.png
```

支持的尺寸：

| 参数 | 实际 size | 用途 |
|:-----|:----------|:-----|
| `1:1` / `square` | `1254x1254` | 头像、方图、封面 |
| `2:3` | `1024x1536` | 竖版封面、海报 |
| `3:2` | `1536x1024` | 横版封面 |
| `3:4` | `1086x1448` | 竖版内容图 |
| `4:3` | `1448x1086` | 课堂讲义、横版知识图 |
| `4:5` | `1122x1402` | 社媒竖图 |
| `5:4` | `1402x1122` | 近方形横图 |
| `16:9` / `landscape` | `1672x941` | 横版海报、报告封面 |
| `9:16` / `portrait` | `941x1672` | 小红书、手机竖图 |
| `21:9` | `1915x821` | README banner、超宽横幅 |
| `9:21` | `821x1915` | 超长竖图 |

也可直接传表内实际尺寸，例如：`1254x1254`、`1024x1536`、`1536x1024`、`1448x1086`、`1672x941`、`941x1672`、`1915x821`。

## 从文件读取提示词

长提示词不要直接塞命令行，写入文件更稳。需要图片中出现的文字必须原样写进提示词：

```bash
cat > /tmp/prompt.md <<'EOF'
生成一张 GitHub README 横幅图。
图片中必须出现标题文字：OfferPilot
图片中可以出现副标题：AI Interview Diagnosis Agent
画布：21:9 宽横幅，当前固定输出 1915x821。
要求：标题清晰、可读、作为画面主体；不要无关 logo；不要乱码；不要 16:9 构图；不要左右补边。
EOF

python gpt-image-draw/draw.py --prompt-file /tmp/prompt.md -s 21:9 -o /tmp/offerpilot-banner.png
```

## API 路径

`gpt-image-2` 不走 `chat.completions`。脚本规则是：

- 无参考图：调用 `/v1/images/generations`（`client.images.generate`）
- 有参考图：调用 `/v1/images/edits`（`client.images.edit`）

## 参考图 / 图片编辑

传一张参考图：

```bash
python gpt-image-draw/draw.py \
  "参考这张线条小狗 IP，画它在咖啡店喝咖啡，保持同样简笔画风格和角色特征" \
  --ref /absolute/path/dog.png \
  -s 1:1 \
  -o /tmp/dog-cafe.png
```

传多张参考图：

```bash
python gpt-image-draw/draw.py \
  "参考这两张角色设定图，生成同一角色在海边冲浪的场景，保持脸型、配色和服装一致" \
  --ref /absolute/path/front.png \
  --ref /absolute/path/side.png \
  -s 16:9 \
  -o /tmp/character-surf.png
```

## Python 调用

```python
from pathlib import Path
import sys

sys.path.append("/path/to/Onefly-Content-Skills/gpt-image-draw")
from draw import draw_image

out = draw_image(
    prompt="中文信息图：AI 如何改变存储行业供需结构",
    output="/tmp/storage-infographic.png",
    size="9:16",
)
print(out)
```

## 信息图提示词模板

```text
生成一张中文竖版信息图，主题《标题》。

风格：高端商业信息图，深色科技背景，清晰中文字体，模块化卡片，图标、箭头、流程线。
比例：9:16。
文字：所有标题和模块文字都直接由 gpt-image-2 原生生成在图片里，不要后期贴字。

内容模块：
1. 核心结论：一句话说明。
2. 背景：3 个关键词。
3. 机制：用箭头流程表达 A → B → C。
4. 影响：列出 3 个受益方 / 风险点。
5. 底部总结：一句判断条件。

要求：中文清晰可读；避免过多小字；不要乱码；不要无关 logo；整体专业、适合投研汇报。
```

## 关键注意事项

- 用户明确指定 `gpt-image-2` 时，直接使用本技能，不要误改 Hermes 全局模型配置。
- 遇到 banner、封面、海报、信息图、标题图时，直接生成包含文字的最终图片；不要建议或执行 SVG/HTML/CSS/canvas/本地贴字/后期叠字方案。
- 遇到 GitHub README banner 时，优先使用原生 `1536x512`；不要使用 `1600x480`，因为比例超过 `3:1` 会被 API 拒绝。
- 输出路径建议用绝对路径，尤其是要通过 Telegram/企业系统上传时。
- 图片中的文字要在 prompt 中逐字指定；如果第一次不满意，保留同一方向调整 prompt 重新生成或用参考图编辑。
- 如果生成失败，先检查：API Key、base_url、模型名、size 参数、响应中的 `data[0].b64_json`。
- 失败可自动重试一次；第二次仍失败再汇报错误。

## 常见命令

```bash
# 帮助
python gpt-image-draw/draw.py --help

# 使用本机环境变量生成图片
python gpt-image-draw/draw.py "中文信息图：AI 时代的存储行业重估" -s 9:16 -o /tmp/storage-ai.png
```
