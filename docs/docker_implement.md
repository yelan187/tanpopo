# 在 🐳 Docker 上部署 tanpopo

### 0. 前言

**本文假设读者已经安装docker并且已经熟悉docker的基本概念，否则请先参考相关教程学习** 

### 1. 获取项目源代码

```bash
git clone https://github.com/yelan187/tanpopo.git
```

### 2. 配置tanpopo

将 `template/config_template.yaml` 复制到项目根目录并命名为 `config.yaml`，至少修改以下字段：

```yaml
core_settings:
  host: "0.0.0.0"     # tanpopo Core adapter webhook
  port: 8080
  adapter_host: "127.0.0.1"

http_settings:
  host: "napcat"      # bot 容器内访问 napcat http api
  port: 3000

ws_settings:
  host: "0.0.0.0"     # 对 napcat 开放 ws 上报监听
  port: 3001

adapter_config:
  onebot:
    gateway:
      allowed_groups: [] # 填允许接入的群号
      allowed_private_users: [] # 填允许接入的私聊用户 QQ

agent_config:
  runtime: "openhands"
  openhands:
    model: "gpt-5.4"   # 按你的可用模型填写
    mcp_servers:
      qqio:
        transport: "stdio"
        command: ""
        args: ["-m", "src.mcp.qqio"]
        cwd: "."

llm_auth:
  api_key: "your_api_key"
  base_url: "http://host.docker.internal:7700/v1"
```

### 3. 构建镜像并启动容器

下方命令会一键完成 tanpopo 构建和启动，并同时启动 napcat。

**napcat 使用 ws 反向上报到 `tanpopo:3001`，http api 端口为 3000。**

```bash
NAPCAT_UID=$(id -u) NAPCAT_GID=$(id -g) docker-compose up -d --build
```

### 4. 登录QQ

通过napcat log返回的二维码，扫码登录QQ即可

```bash
docker logs napcat
```

### 5. 🆗开始和tanpopo对话吧

运行时默认启用 `qqio`、`workspace`、`fetch`、`capability`、`context` 和
`plugin_manager` MCP。Agent 自写的可复用 MCP 建议放在 `.agents/mcps/`，草稿、
缓存和临时文件放在 `agent_workspace/` 或 `tmp/`。
