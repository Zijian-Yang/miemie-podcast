# Miemie Podcast

Miemie Podcast 是一个面向小宇宙单集链接的播客内容处理平台。

用户输入一条小宇宙分享页链接后，系统会自动提取音频，调用百炼上的 ASR 与大模型能力，生成：

- 总结
- 知识沉淀
- 逐字稿
- 单集问答
- 脑图预览与导出

## 功能特性

- 支持小宇宙单集分享页导入
- 支持小宇宙音频直链解析
- 支持百炼 `qwen3-asr-flash-filetrans` 异步转写
- 支持百炼 `qwen3.5-plus` 进行分层总结与知识提炼
- 支持超长逐字稿分块分析，不一次性把全文塞给模型
- 支持总结、知识沉淀、逐字稿、脑图、单集问答模块
- 支持历史记录、搜索、删除
- 支持桌面端和移动端响应式布局
- 架构已预留多模型接入、Postgres + Redis、多用户系统扩展边界

## 技术栈

- 前端：Next.js 15 + TypeScript
- 后端：FastAPI
- 后台任务：Python Worker
- 默认存储：SQLite + 本地文件
- 当前模型：
  - `qwen3-asr-flash-filetrans`
  - `qwen3.5-plus`

## 项目结构

- `apps/web`：前端页面与交互
- `backend`：API、任务编排、领域模型、provider/source adapter
- `scripts`：部署、运维、脑图渲染等脚本
- `deploy/systemd`：Ubuntu 服务模板

## 推荐部署方式

推荐直接运行交互式管理脚本 [`scripts/manage.sh`](scripts/manage.sh)。

该脚本已经切换为菜单模式，执行后会进入主菜单，并自动识别当前系统：

- Ubuntu：使用 `systemd` 方式部署和管理
- macOS：使用本地后台进程方式部署和管理

菜单内可完成：

- 环境检查
- 安装部署
- 启动服务时选择开发模式或生产模式
- 停止、重启、查看生产服务
- 查看服务状态与日志
- 更新项目
- 重建前端
- 修改端口、监听地址、域名、密码、百炼 Key 等配置

## 快速开始

### 1. 克隆仓库

```bash
git clone git@github.com:Zijian-Yang/miemie-podcast.git
cd miemie-podcast
```

### 2. 准备配置文件

```bash
cp .env.example .env
```

至少填写：

```bash
APP_ADMIN_PASSWORD=你的管理密码
DASHSCOPE_API_KEY=你的百炼 Key
```

并发提速相关配置默认已开启，可按机器资源调整：

```bash
WORKER_PROCESS_COUNT=2
ANALYSIS_CHUNK_EXTRACT_CONCURRENCY=4
```

### 3. 运行管理脚本

```bash
./scripts/manage.sh
```

进入菜单后，按编号选择操作即可。

推荐顺序：

1. `环境检查`
2. `配置管理`
3. `安装部署`
4. `启动服务`
5. `查看状态`

## 菜单说明

主菜单包含：

- 环境检查
- 安装部署
- 启动服务（选择开发/生产模式）
- 停止生产服务
- 重启生产服务
- 查看生产状态
- 查看生产状态(JSON)
- 查看生产日志
- 更新项目
- 重建前端
- 配置管理
- 退出

启动服务后可选择：

- 生产模式启动：用于守护运行
- 开发模式一键启动：同时启动 Web、API、Worker，并在当前终端聚合查看日志

配置子菜单支持：

- 查看当前配置摘要
- 修改 `APP_HOST`
- 修改 `APP_PORT`
- 修改 `API_HOST`
- 修改 `API_PORT`
- 修改 `APP_DOMAIN`
- 修改 `APP_ADMIN_PASSWORD`
- 修改 `DASHSCOPE_API_KEY`
- 读取任意配置键
- 写入任意配置键

说明：

- 可以直接通过菜单自定义前端端口 `APP_PORT` 和后端端口 `API_PORT`
- 修改 `APP_HOST` / `APP_PORT` / `API_HOST` / `API_PORT` 时，脚本会自动同步 `WEB_ORIGIN` 和 `NEXT_PUBLIC_API_BASE_URL`

## 适用环境

- 支持环境：
  - Ubuntu：`systemd` 管理模式
  - macOS：本地进程管理模式
- Ubuntu 安装依赖：`apt-get`、`systemd`、`sudo`
- macOS 安装依赖：Homebrew
- Web 反代：请自行使用 Nginx 反代到 `APP_PORT`

说明：

- `APP_DOMAIN` 仅用于生成外部访问链接
- 项目不负责自动生成 Nginx 配置
- Web 运行推荐使用 Node 22 / 24 LTS；脚本已对较新的 Node 版本自动加兼容参数

## 日志与交互说明

- 选择 `查看生产日志` 后会进入日志跟随模式
- 开发模式会同时启动 Web、API、Worker，并显示当前 URL、端口和日志文件位置
- 在日志模式或开发模式运行中，按 `Ctrl+C` 可停止当前前台进程并返回菜单
- 如果在非交互式终端中运行脚本，脚本会直接报错退出

## 本地开发

管理脚本优先服务服务器部署场景。

如果你只是本地开发或联调，可以先运行：

```bash
./scripts/manage.sh
```

再通过菜单执行 `环境检查` 和 `配置管理`。

如果你需要手动运行开发环境：

```bash
npm install
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ./backend
python -m miemie_podcast.api.app
python -m miemie_podcast.worker.main
npm run dev:web
```

说明：

- `WORKER_PROCESS_COUNT` 控制 Worker supervisor 拉起的子进程数，适合按 CPU / 模型限流能力调整到 `2-4`
- `ANALYSIS_CHUNK_EXTRACT_CONCURRENCY` 控制单个 episode 在 `chunk_extract` 阶段的并发请求数

## 当前范围

当前版本聚焦于单用户工作台和核心播客处理流程，暂不包含：

- 正式多用户账号体系
- 跨历史统一问答
- 关键词高亮
- clips / snippets
- 翻译能力

## 备注

- 后续能力扩展会优先保持 provider、存储、队列、鉴权层的接口稳定
