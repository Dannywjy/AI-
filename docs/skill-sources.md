# 技能来源记录

核查日期：2026-10-20。当前仓库是新建项目，没有需要迁移的 agent 或 skills 配置。本机已有 Codex 的系统/插件技能；本次只增加项目级配置。

| 请求项 | 来源与身份 | 本次固定 commit | 许可信息 |
| --- | --- | --- | --- |
| HyperFrames | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes)，[HeyGen 官方文档](https://hyperframes.heygen.com/quickstart) | `a8a80323f69f055bab9f7985b2c3398b9688aecb` | [Apache-2.0](https://github.com/heygen-com/hyperframes/blob/a8a80323f69f055bab9f7985b2c3398b9688aecb/LICENSE) |
| video-use | [browser-use/video-use](https://github.com/browser-use/video-use)，[官网](https://video-use.com/)交叉链接 | `43cfc566833548093455c9d4a46bd69913b7e552` | [MIT](https://github.com/browser-use/video-use/blob/43cfc566833548093455c9d4a46bd69913b7e552/LICENSE) |
| Remotion Skills | [remotion-dev/skills](https://github.com/remotion-dev/skills)，[Remotion 官网直接推荐](https://www.remotion.dev/docs/ai/skills) | `039e8a2fc78b67efc228d5645367838b85818a1c` | 该 commit 没有 LICENSE；[上游问题 #28](https://github.com/remotion-dev/skills/issues/28)讨论授权。按官网安装供本地使用，PR 不包含其源码。 |
| Generative Media Skills | [calesthio/generative-media-skills](https://github.com/calesthio/generative-media-skills)，社区作者维护的集合 | `8c85352d5d75d4dcbe58480bd138e37b9742bab1` | [MIT](https://github.com/calesthio/generative-media-skills/blob/8c85352d5d75d4dcbe58480bd138e37b9742bab1/LICENSE) |
| Seedance2 Skill | [dexhunter/seedance2-skill](https://github.com/dexhunter/seedance2-skill)，社区提示词项目，非 ByteDance 官方连接器 | `516284d5bab58361bfdfed3cc96cee3e837d4c44` | [MIT](https://github.com/dexhunter/seedance2-skill/blob/516284d5bab58361bfdfed3cc96cee3e837d4c44/LICENSE) |

## 安装方式核对

- Codex [官方技能文档](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)指定项目 `.agents/skills/`。使用系统 Skill Installer 的 `--repo`、`--ref`、`--path`、`--dest`、`--method download` 下载目录；`--name` 处理根目录和中文子目录的名称映射。
- HyperFrames 的 [core manifest](https://github.com/heygen-com/hyperframes/blob/a8a80323f69f055bab9f7985b2c3398b9688aecb/packages/cli/src/utils/skillsManifest.ts)列出 10 个核心技能，另选择 `general-video` 作为通用制作工作流。保留各技能的 references/scripts。上游 [skills update 实现](https://github.com/heygen-com/hyperframes/blob/a8a80323f69f055bab9f7985b2c3398b9688aecb/packages/cli/src/commands/skills.ts)会更新全局位置，因此本项目使用固定 commit 下载。其他创作工作流暂未安装。
- video-use 的 [安装说明](https://github.com/browser-use/video-use/blob/43cfc566833548093455c9d4a46bd69913b7e552/install.md)要求根 `SKILL.md` 配合同级 `helpers/`。安装根路径 `.` 并命名为 `video-use`，保留完整目录。
- Remotion 官网推荐 `npx skills add remotion-dev/skills`。本项目采用固定 commit 的同一来源，只下载 `skills/remotion-best-practices/`；它包含总入口及其他能力的内嵌参考资源，必须整体保留。
- Generative Media 没有根 `SKILL.md`；[SKILL_INDEX.md](https://github.com/calesthio/generative-media-skills/blob/8c85352d5d75d4dcbe58480bd138e37b9742bab1/SKILL_INDEX.md)列出独立技能。默认选用 6 个视频制作常用目录，精确路径见锁定清单。这里保留本地原目录，不运行上游打包器或脚本，也不将 EVAL/tests 等本地参考文件发布到 Git。
- Seedance2 的 `zh/SKILL.md` 名称为 `seedance-prompt-zh`，因此显式设置目标名。英文版本及其他同名第三方 API 项目未混装。技能中的模型规格可能随产品更新，实际生成前以当前服务文档为准。

## 已处理的配置差异

HyperFrames 上游包含自动升级、渲染后 feedback 指令。项目 AGENTS 要求固定版本并取消自动反馈；包装器设置官方支持的 [HYPERFRAMES_NO_TELEMETRY](https://github.com/heygen-com/hyperframes/blob/a8a80323f69f055bab9f7985b2c3398b9688aecb/packages/cli/src/telemetry/policy.ts)。上游技能可以指导任务，但不能覆盖用户明确选择 Remotion 等工具的要求。

包装器还按上游 [plugin-cli.mjs](https://github.com/heygen-com/hyperframes/blob/a8a80323f69f055bab9f7985b2c3398b9688aecb/skills/hyperframes/scripts/plugin-cli.mjs)设置 `HYPERFRAMES_SKIP_SKILLS=1`、`HYPERFRAMES_NO_UPDATE_CHECK=1` 及两个版本变量，防止 `init` 内部更新全局技能。单独传 `--skip-skills` 在这个版本无效。包装器拒绝 `skills`、`upgrade`、`feedback` 入口；更新通过本项目的版本清单和 PR 管理。

下载技能不建立服务连接。video-use [转录助手](https://github.com/browser-use/video-use/blob/43cfc566833548093455c9d4a46bd69913b7e552/helpers/transcribe.py)会调用 ElevenLabs 并上传音频；Generative Media 网关可能调用 fal.ai、Replicate 等服务。安装验证不执行这些操作，也不读取任何凭据。

许可证记录只描述所选 skill 仓库；Remotion 运行时、媒体服务、素材和具体模型的条款分别适用。更新时重新核查来源及运行依赖。
