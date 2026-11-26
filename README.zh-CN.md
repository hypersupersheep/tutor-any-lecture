# Tutor Any Lecture

**用你自己的课做成的家教:它考你,引用老师的原话,替你安排复习。**

先考你,再按老师原话讲,标到分钟和课件页,讲完再考,错题进 Anki。

[English](README.md)

Tutor Any Lecture 由一个 agent skill 和一个命令行工具组成,两者都叫 `tutor-any-lecture`。agent 负责读课、写笔记、出题提问;命令负责取转写、在你看到笔记之前检查它、记录你的作答,并算出哪些复习到期了。

## 一节课会变成什么

每节课对应一个单元,也就是文件夹 `<workspace>/courses/<course>/<unit>/`;工作区默认是 `~/TutorAnyLecture`,可以改。

| 文件 | 是什么 |
|---|---|
| `explanation.md` | 讲解笔记,按讲课顺序写。凡是说老师讲了什么,都标出处 `(slide N)` 或 `(mm:ss)`;来自视频链接的课,每个时间都链到视频的那一秒。笔记里有前测部分、带折叠答案的小练习、课上没讲到的课件页,以及字幕误听的勘误表。 |
| `items.json`、`assignment.json` | 题库:每个跟踪概念有三道平行变体,随机分给前测、讲后测验和第 7 天的复习。 |
| `cards.json`、`cards.tsv` | Anki 卡片。`cards.tsv` 用 Anki 的"文件 > 导入"(File, Import)导入。 |
| `map.json`、`overview.mmd` 或 `overview-<view>.mmd` | 概念图:五种节点(definition、theorem、method、example、pitfall),每条边都有动词,每个视图最多 12 个节点,导出成 GitHub 能直接显示的 Mermaid。 |
| `verify.json` | 门禁的检查结果。 |
| `sources/` | 转写、课件文字,以及材料从哪里来。 |
| 工作区里的 `progress/<course>.jsonl`、`progress/<course>.md` | 每一次作答记录,以及进度页。 |

笔记用什么语言写由 `note_language` 设置决定,默认是你和 agent 对话所用的语言。`outputs` 设置决定一个单元产出上面哪几样;讲解笔记总是其中之一。

## 内置样例节选

下面是内置合成样例笔记的一部分。这个样例是一段十四分钟的复利小讲座,配三页课件,`tutor-any-lecture selftest` 会把它完整跑过门禁。完整笔记见 [src/tutor_any_lecture/data/sample/explanation.md](src/tutor_any_lecture/data/sample/explanation.md)。同一节课的中文笔记,运行 `tutor-any-lecture selftest --keep DIR --sample zh` 就能生成。

> The lecturer starts from one idea that "sits under almost every price in finance" (0:40). A bank pays a yearly rate on a deposit, and slide 1 gives two ways to work out the payment, which differ only in what the rate is paid on (1:04, 2:54).
>
> Under compound interest "last year's interest is now part of the balance, and this year it earns interest too": interest on interest (2:02–2:24). So the first year pays the same both ways, and from the second year compound interest also pays on last year's interest: "The rate is the same, the base is bigger" (3:06–3:54, 4:18).

## 工作流程

1. **检查**:skill 的第 0 步运行 `tutor-any-lecture doctor --json --skill <skill folder> --vision-word WORD`(WORD 是 agent 从 skill 自带的一张小图里读到的词,看不了图时写 none),第一次使用时再运行 `tutor-any-lecture selftest`。
2. **取材料**:把转写和课件放进单元文件夹。先用字幕,没有可用字幕才用语音识别。
3. **规划**:agent 写 plan.json,选出五个跟踪概念(不足五个就全选)。
4. **写作**:agent 先写题目,再写笔记,时间出处先写成不带链接的普通形式;来自视频链接的课,`tutor-any-lecture cite link --unit DIR` 会把它们变成链接。最后写卡片和概念图。
5. **门禁**:`tutor-any-lecture verify --unit DIR` 跑九项检查:citations、coverage、terms、numbers、structure、items、cards、map 和 banned phrases。有一项 FAIL 就不交付;agent 改好文件再跑,直到结果是 PASS。每项检查查什么,见 [skills/tutor-any-lecture/references/gate.md](skills/tutor-any-lecture/references/gate.md)。
6. **前测**:你看到笔记之前,agent 先在对话里做前测,一次问一道;判对错之前先问你有多大把握。
7. **讲后测验**:你读完笔记后,它用同样的方式做讲后测验。答错的题会变成 Anki 卡片。
8. **复习**:第一次讲后测验之后的第 1、7、21 天各复习一次(第 1 天和第 21 天可选),`tutor-any-lecture progress render --course C` 生成进度页。

## 安装

**需要**:一个能加载 skill、能运行 shell 命令的 agent(Claude Code、Codex 等);[uv](https://docs.astral.sh/uv/) 或 Python 3.10+;git,方式三克隆仓库要用,方式一和方式四第一次使用时安装命令也要用;只有用 `npx skills add` 时才需要 Node.js。支持 macOS、Linux 和 x64 的 Windows。

### 方式一:npx skills add(推荐)

```bash
npx skills add hypersupersheep/tutor-any-lecture
```

这条命令把 skill 复制到 agent 的 skills 文件夹。怎样算成功:agent 列出的 skill 里有 `tutor-any-lecture`。命令行工具在第一次使用时安装:skill 的第 0 步运行 `tutor-any-lecture doctor --json --skill <skill folder> --vision-word WORD`,找不到命令时,它会提出运行 skill 自带的安装脚本 `skills/tutor-any-lecture/scripts/install.sh`(Windows 上是 `skills/tutor-any-lecture/scripts/install.ps1`),并加上 `--cli-only`(`-CliOnly`),因为 skill 已经装好了。

### 方式二:Claude Code 插件

```text
/plugin marketplace add hypersupersheep/tutor-any-lecture
/plugin install tutor-any-lecture@tutor-any-lecture
```

怎样算成功:`/plugin` 里显示 `tutor-any-lecture` 已安装。命令行工具同样在第一次使用时安装,和方式一一样。

### 方式三:让 agent 替你安装

把下面这段话粘贴给 agent:

```text
帮我安装 tutor-any-lecture。每做完一步就检查结果;检查没通过就停下,告诉我你看到了什么。

1. 把 https://github.com/hypersupersheep/tutor-any-lecture 克隆到你选的文件夹。
   检查:文件夹里有 install.sh 和 install.ps1。
2. 在这个文件夹里运行安装脚本:macOS 或 Linux 上是 `bash install.sh --yes`,Windows 上是 `powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Yes`(在 Git Bash 里也这样运行;`bash install.sh` 不能用于 Windows)。不要把下载的内容直接交给 shell 执行。安装可能要几分钟。
   检查:退出码是 0,而且它打印的最后一行是运行 selftest 的命令,里面带着命令的完整路径。退出码是 3 时,把它打印的内容给我看,然后停下。
3. 运行最后一行里的那条命令(Windows 上在 PowerShell 里运行)。
   检查:退出码是 0。同一个完整路径也记在文件 ${XDG_CONFIG_HOME:-$HOME/.config}/tutor-any-lecture/cli-path 里(Windows 上是 %APPDATA%\tutor-any-lecture\cli-path),以后的会话用它。
4. 在你自己的 skills 文件夹里(例如 ~/.claude/skills/ 或 ~/.codex/skills/)找 tutor-any-lecture/SKILL.md。
   检查:文件存在。不存在的话,重新运行安装脚本,加上 `--agents`,后面写 claude、codex 或 agents(Windows 上是 `-Agents`)。
```

有 uv 时,安装脚本用 `uv tool install`;没有时,它在 `~/.tutor-any-lecture/venv`(Windows 上是 `%LOCALAPPDATA%\tutor-any-lecture\venv`)建一个独立的环境。它不往系统 Python 里装任何东西,也不会下载脚本来执行。装好以后,它把命令的完整路径记在 `cli-path` 文件里,把 skill 复制给找到的 agent(`~/.claude`、`~/.codex`、`~/.agents`),对自己所在的 skill 文件夹运行 `tutor-any-lecture doctor --json --skill <skill folder>`,最后一行打印运行 selftest 的命令。退出码:0 表示就绪,1 表示失败或被取消,2 表示参数有误,3 表示需要你处理(它会打印该怎么做)。加上 `--dry-run`(`-DryRun`)可以只看计划,不做任何改动;加上 `--cli-only`(`-CliOnly`)只装命令,不复制 skill。

语音识别是附加组件,只有没有字幕的音频或视频才需要。它的下载很大(几百 MB,Apple Silicon 上更大),所以安装脚本默认不装,要装就加 `--with-asr`(`-WithAsr`);以后再带上它重新运行安装脚本也可以。字幕、转写稿和课件不需要它。

### 方式四:Claude 网页版上传

把文件夹 `skills/tutor-any-lecture` 打成 ZIP,在 Claude 网页版里作为 skill 上传。怎样算成功:Claude 网页版列出的 skill 里有 `tutor-any-lecture`。网页版处理不了本地的大视频,这种方式只能用课件、字幕和转写稿。第 0 步在那里照样运行;doctor 无法就绪时,改用你自己电脑上的 agent。

## 快速开始

用方式三安装的,运行安装脚本最后一行打印的 selftest 命令。用方式一、二、四安装的,agent 第一次使用时会自己运行 selftest。命令已经在 PATH 上时,下面这条效果相同:

```bash
tutor-any-lecture selftest
```

它把内置样例从导入转写一直跑到门禁。不需要联网,也不需要语音识别模型;退出码是 0 就说明装好了。然后把一节课交给 agent:"把这节课讲给我:<文件、文件夹或链接>"。

## 怎么提要求

用平常的话跟 agent 说就行,命令由它来选。

| 你说 | 会发生什么 |
|---|---|
| "把这节课讲给我:week4.mp4" | 本地的视频或音频文件,用语音识别附加组件在你的电脑上转写。旁边放着字幕或转写文件时,改为导入那个文件。没有课件的视频会抽出关键帧,笔记把它们当作课件页引用。 |
| "把这个文件夹里的课讲给我" | `acquire route` 整理文件夹里的文件、规划步骤;agent 只问它判断不了的事。 |
| "把这个视频讲给我:<YouTube 或 B 站链接>" | 先用字幕。只有打开了音频开关,才会下载音频(见"安全和隐私")。 |
| "用这份转写:lecture.vtt" | 导入 SRT、VTT、JSON 或带时间戳的 TXT 转写、Zoom 的 TXT 转写,或 Teams 导出的 DOCX 转写。 |
| "根据这份课件做笔记:slides.pdf" | 只有课件 PDF 或 PowerPoint(.pptx)课件时,做成只有课件的单元,笔记只标课件页,不标时间。 |
| "把这段 Panopto 录像讲给我" | 从 Panopto 播放页读转写。需要带浏览器工具的 agent。 |
| "考考我 <课程>" | agent 先问到期的题;没有到期的,就出练习题。 |
| "今天有什么要复习?" | `progress due` 列出到期的讲后测验和复习。 |
| "看看我的进度" | `progress render` 生成这门课的进度页。 |

每种来源的适配说明在有真实运行记录之前,都标为实验性(experimental):见 `skills/tutor-any-lecture/references/adapters/` 下每个文件的 "Verified by" 一节。

## 可选的附加产出

附加产出都是可选的,从不属于门禁。

- **语音课**:实验性功能,只支持 Apple Silicon,规则用中文写。只有你要的时候才做:agent 写一份适合听的讲稿,用装了 `mlx-audio` 和 numpy 的 Python 运行 `skills/tutor-any-lecture/scripts/tts_synthesize.py`,还需要 PATH 上有 ffmpeg 和 ffprobe。
- **手写复习版和手绘图**:两个独立的配套 skill。`skills/handwritten-notes-pdf/` 把一份简化标记的文件排成网格纸 PDF;`skills/excalidraw-concept-map/` 把一份 Mermaid 文件变成 Obsidian 用的 `.excalidraw.md`,还可以另出一份 `.excalidraw` 文件和一张 PNG。它们的说明用中文写。`npx skills add` 会列出全部三个 skill 供你选,Claude Code 插件会把三个都带上;而方式三的安装脚本只复制 `skills/tutor-any-lecture`,不会复制这两个。所以用方式三安装后,或者用别的 agent 时,请自己把 `skills/handwritten-notes-pdf/` 和 `skills/excalidraw-concept-map/` 复制到 agent 的 skills 文件夹。它们需要一个手动装了 `websocket-client` 的 Python,还需要 Chrome 或 Chromium:按顺序找 `CHROME_PATH`、macOS 上 Chrome 的默认位置,以及 PATH 上的 `google-chrome`、`google-chrome-stable`、`chromium` 或 `chromium-browser`;所以在 Windows 上请设置 `CHROME_PATH`。它们每次渲染都要联网加载库和字体。

## 安全和隐私

- **不碰密码**:从不输入、保存或索要密码。遇到登录页或"Verify you are human"检查就停下,交给你处理。
- **不读浏览器 cookie**。
- **在所有平台上只读**:不提交、不发帖、不预约。在 Panopto 里从不点 Edit、Cuts、Streams、Download 或 Share。
- **下载听 `downloads` 设置**:默认的 `ask` 会在平台本身提供的每一次下载之前先问你;`allow` 允许这些下载,不再询问。从不绕过 DRM。
- **视频的音频听 `public_video_audio`**:默认关闭。打开时会显示一段说明,并记下你同意的日期。此后,视频没有可用字幕时,只下载音轨,在你的电脑上转写,转写完就删除。对你给出的每个地址,下不下载由你决定、由你负责。需要登录才能看的录像拿不到,因为工具从不使用你的登录。
- **什么留在本地**:没有遥测。工具把转写、题目和进度都存在你的电脑上。agent 读这些文件,就像读你给它的任何文件一样,所以它们会按那个 agent 的条款发给它的模型提供方。工具只在这些时候联网:访问你给的地址、安装、第一次转写时下载一次语音模型;附加产出还要第一次下载语音合成模型,配套页面还要加载库和字体。
- **只用于个人学习**:不要传播录像,也不要传播根据受版权保护的课程做的笔记。

## 常见问题

### 支持哪些 agent?

能加载 skill、能运行 shell 命令的 agent 都行。skill 在 `skills/tutor-any-lecture/references/agents/` 下给 Claude Code 和 Codex 各写了说明,其他 agent 有一份通用说明。只有 Panopto 和 Moodle 页面需要浏览器工具。

### 能读哪些材料?

本地的视频和音频文件、整个材料文件夹、YouTube 和 B 站链接、转写文件(SRT、VTT、Whisper 格式的 JSON、带时间戳的 TXT、Zoom 的 TXT 转写,或 Teams 导出的 DOCX)、课件 PDF、PowerPoint(.pptx)课件,以及通过带浏览器工具的 agent 读取的 Panopto 录像。课件照片(三张以上,JPEG 或 PNG)在 agent 能看图时也能用;skill 会先检查这一点。

### 有什么会离开我的电脑?

没有遥测,工具把转写、题目和进度都存在你的电脑上。agent 读这些文件,就像读你给它的任何文件一样,所以它们会按那个 agent 的条款发给它的模型提供方。工具联网只为访问你给的地址、安装,以及第一次转写时下载一次语音模型;附加产出另外要下载一次语音合成模型,渲染时还要加载库和字体。

### 笔记能用英文或别的语言写吗?

能。笔记用 `note_language` 设置的语言写,默认是你和 agent 对话所用的语言。想固定下来,运行 `tutor-any-lecture profile set note_language en`,把 en 换成你要的语言代码。

### 一定要 Mac 吗?

不用。语音识别在 Apple Silicon 上用 mlx-whisper,在别的机器上用 faster-whisper,其余部分在 macOS、Linux 和 Windows 上都能跑。只有语音课需要 Apple Silicon。

### 卡片怎么导入 Anki?

用 Anki 的"文件 > 导入"(File, Import)导入 `cards.tsv`。卡片的 id 是固定的,所以再次导入会更新卡片,不会丢掉复习记录。

### 复习什么时候到期?

对每个单元,第一次讲后测验之后的第 1、7、21 天;第 1 天和第 21 天的复习可选。可以问 agent "今天有什么要复习?",也可以运行 `tutor-any-lecture progress due --course C`。

### 能关掉测验吗?

能:`tutor-any-lecture profile set outputs "[explanation, cards, map]"` 去掉前测和测验。讲解笔记总会保留。

### Windows 需要什么?

x64 的 Windows;用 Windows PowerShell 5.1 或 PowerShell 7 运行 `install.ps1`(`bash install.sh` 不能用于 Windows,Git Bash 里也不行);uv 或 Python 3.10+;方式三,以及方式一和方式四第一次使用时安装命令,还需要 git。

## 升级和卸载

### 升级

方式三:在克隆下来的文件夹里运行 `git pull`,再运行一次安装脚本(`bash install.sh --yes`,Windows 上是 `powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Yes`),它会重新构建命令、重新复制 skill。方式一、二、四:重新获取 skill,也就是再运行一次 `npx skills add hypersupersheep/tutor-any-lecture`、在 Claude Code 的 `/plugin` 菜单里更新,或者上传新的 ZIP。这样更新只换了 skill,命令还是旧的;所以 skill 的第 0 步发现命令和 skill 版本不一致时(`tutor-any-lecture doctor --json --skill <skill folder>` 的 `skill_version` 检查),会提出带 `--cli-only`(Windows 上是 `-CliOnly`)重新运行 skill 自带的安装脚本。你的设置和单元都会保留。

### 卸载

- 命令:用 uv 装的,运行 `uv tool uninstall tutor-any-lecture`;否则删除文件夹 `~/.tutor-any-lecture`(Windows 上是 `%LOCALAPPDATA%\tutor-any-lecture`)。
- 配置文件夹 `${XDG_CONFIG_HOME:-$HOME/.config}/tutor-any-lecture`(Windows 上是 `%APPDATA%\tutor-any-lecture`),里面有 `cli-path` 和 `profile.yaml`。
- skill 的副本:`~/.claude/skills/tutor-any-lecture`、`~/.codex/skills/tutor-any-lecture` 和 `~/.agents/skills/tutor-any-lecture`。方式一和方式二装的,用当初添加它的工具删除。
- 工作区 `~/TutorAnyLecture` 里是你的单元和进度:确定不再需要时才删。

## 参与贡献

[CONTRIBUTING.md](CONTRIBUTING.md) 写了怎么搭建测试环境、每个改动要遵守哪些规则,并建议从一个平台适配说明开始贡献。安全问题请按 [SECURITY.md](SECURITY.md) 的说明私下报告,不要发在公开的 issue 里。

## 致谢

- [PyYAML](https://github.com/yaml/pyyaml)、[pdfplumber](https://github.com/jsvine/pdfplumber)、[yt-dlp](https://github.com/yt-dlp/yt-dlp),以及自带 [FFmpeg](https://ffmpeg.org) 的 [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)。
- 语音识别用的 [mlx-whisper](https://github.com/ml-explore/mlx-examples) 和 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)。
- [anki-card-forge](https://github.com/FrostySL/anki-card-forge),卡片规则改编自它;它的许可声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
- [Agent Skills](https://github.com/anthropics/skills) 格式。
- 附加产出用到的 [mlx-audio](https://github.com/Blaizzy/mlx-audio) 和 Qwen3-TTS、[Excalidraw](https://github.com/excalidraw/excalidraw)、[mermaid-to-excalidraw](https://github.com/excalidraw/mermaid-to-excalidraw)、[KaTeX](https://katex.org),以及配套页面加载的 Patrick Hand、小赖(Xiaolai SC)和 Excalifont 字体。

## 许可

[MIT](LICENSE)。配套页面在渲染时加载的库和字体遵循各自的许可。
