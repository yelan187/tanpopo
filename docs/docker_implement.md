# 在 🐳 Docker 上部署 tanpopo

### 0. 前言

**本文假设读者已经安装docker并且已经熟悉docker的基本概念，否则请先参考相关教程学习** 

### 1. 获取项目源代码

```bash
git clone https://github.com/yelan187/tanpopo.git
```

### 2. 配置tanpopo

将tamplate/config.yaml复制到项目根目录并命名为config.yaml，修改其中的配置项，具体配置项含义请参考配置说明

### 3. 构建镜像并启动容器

下方命令会一键完成tanpopo的构建和启动，并启动napcat和mongodb服务

**napcat默认使用ws正向代理，端口为3001**

**mongodb默认使用27017端口。**

```bash
NAPCAT_UID=$(id -u) NAPCAT_GID=$(id -g) docker-compose up -d
```

### 4. 登录QQ

通过napcat log返回的二维码，扫码登录QQ即可

```bash
docker logs napcat
```

### 5. 🆗开始和tanpopo对话吧