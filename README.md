# AI视频

为 Codex 配置 HyperFrames、video-use、Remotion Skills、Generative Media Skills 和 Seedance2 中文提示词技能。上游版本记录在 [media-skills.lock.json](media-skills.lock.json)。

## 安装

需要 Python 3.11+、网络连接和 Codex 自带的 Skill Installer。先在本项目目录运行：

```sh
python3 scripts/install_media_skills.py --dry-run
python3 scripts/install_media_skills.py
python3 scripts/install_media_skills.py --check
```

如果未找到 Codex 安装器，可显式指定其位置：

```sh
python3 scripts/install_media_skills.py --installer /实际路径/skill-installer/scripts/install-skill-from-github.py
```

安装器从 GitHub 下载锁定 commit 的完整技能目录，不执行上游代码。生成文件保存在被 Git 忽略的 `.agents/skills/`，不会修改全局 Codex 配置或覆盖已有技能。同一版本可以重复运行，内容有变化时会报错并保留现有文件。

若 macOS 的 Python 报证书路径缺失，可使用系统证书库：

```sh
SSL_CERT_FILE=/etc/ssl/cert.pem python3 scripts/install_media_skills.py
```

在 Codex 中打开本项目并开始下一轮对话即可使用；若技能列表未刷新，重启 Codex。[Codex 技能目录说明](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)

## 已接入的能力

| 来源 | 默认范围 | 调用示例 |
| --- | --- | --- |
| HeyGen HyperFrames | 10 个核心技能和 `general-video` 工作流 | `$hyperframes` 制作一个多场景视频 |
| Browser Use video-use | 视频编辑入口、helpers 和内嵌参考文件 | `$video-use` 剪辑我的素材 |
| Remotion | `remotion-best-practices` 及完整参考目录 | `$remotion-best-practices` 用 React 制作动画 |
| Generative Media Skills | 图像/视频网关、镜头、分镜、FFmpeg 收尾、质量检查，共 6 项 | `$storyboard-previsualization` 规划分镜 |
| Seedance2 Skill | 社区作者 dexhunter 的中文提示词技能 | `$seedance-prompt-zh` 为即梦写视频提示词 |

默认共 20 个顶层技能。Generative Media 上游目前有 153 项独立技能，本项目选择视频创作所需的 6 项；更多工作流通过修改锁定清单、检查来源并提交 PR 增加。Seedance2 这一项是提示词指南，不连接字节跳动账号或视频生成 API。

## 运行视频工具

技能安装和实际渲染分开进行。下面的软件只在对应任务需要时安装：

| 用途 | 运行依赖 |
| --- | --- |
| HyperFrames | Node.js 22+；使用 `sh scripts/hyperframes.sh <命令>`，固定 CLI 0.8.181，关闭遥测、自动更新和初始化时的全局技能安装 |
| video-use | FFmpeg/ffprobe；独立 Python 虚拟环境；按上游 `pyproject.toml` 安装运行依赖 |
| Remotion | Node.js、Git，以及具体视频项目的 npm 依赖 |
| Generative Media 助手 | Python 3.11+；FFmpeg 收尾另需 ffmpeg/ffprobe；部分图像示例需要 Pillow |
| Seedance2 提示词 | 无额外依赖 |

HyperFrames 包装器首次运行会由 npm 下载指定版本。实际媒体生成、转录和云渲染可能需要单独的服务账号或付费额度。只有用户选择相关服务后才配置凭据；空白变量见 `.env.example`，真实 `.env` 不进入 Git。video-use 的 ElevenLabs 转录会上传音频，需在具体编辑任务中明确这一点。

下载的技能目录保持只读使用。虚拟环境放在项目根 `.venv/`，凭据放项目根 `.env` 或环境变量，输出与缓存放 `outputs/`。运行 Python 助手时设置 `PYTHONDONTWRITEBYTECODE=1` 并指定项目输出目录；不要在 `.agents/skills/` 内执行 `uv sync` 或创建环境文件，否则完整性校验会报告变化。

## 来源、维护与验证

[来源记录](docs/skill-sources.md)列出官方/社区归属、精确版本、许可信息及安装差异。所有上游内容保留在本地忽略目录；本仓库不重新发布第三方技能源码。

更新时先审阅新 commit 的技能、脚本和许可，再修改清单并提交 PR。安装器不会覆盖旧版本；在新的项目检出目录中安装并验证新清单。不得直接运行上游的全局技能更新来替代这个流程。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/install_media_skills.py --check
```

自动测试验证固定版本、路径限制、失败回滚、重复安装和内容完整性，不调用付费服务。`--check` 验证本地文件和安装记录，不代表已测试视频渲染或云 API。
