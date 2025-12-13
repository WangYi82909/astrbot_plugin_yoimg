![本地图片描述](logo.png)
<!-- 居中显示名称 -->
<p align="center">**YOIMG文档**</p>
AstrBot 图像生成插件帮助文档

📌 插件概述

这是一个基于AstrBot框架的图像生成插件，支持人格初始化与智能图像生成功能
如果您的服务器可以访问gitee生图接口，那么请在代理页填写当前网站的域名
如果您的服务器无法访问gitee，请将本网站目录的hk.php，上传到香港虚拟主机上，并在配置页代理处填写绑定香港虚拟主机的域名，不用添加末尾/
你可以在配置页最下方填写润词模型
我计划在下个版本中添加共享流量池，您可以上传自己的免费key，和使用其他人的共享接口。
🔧 配置说明

配置文件 (_conf_schema.json)

```json
{
  "server_url": "服务器地址（如：http://154.40.35.203:520）",
  "enable_debug_log": "是否启用调试日志"
}
```

📋 命令列表

1. /yo 初始化

功能：上传当前对话的人格到服务器进行关键词提取

流程：

1. 获取当前对话的人格ID和内容
2. 生成随机令牌
3. 上传到服务器 /up.php 接口
4. 缓存服务器返回的关键词

使用示例：

```
/yo 初始化
```

2. /yoimg <关键词> - 生成图像

功能：基于当前人格和聊天记录生成图像

参数：

· <关键词>：图像描述关键词（必需）

流程：

1. 检查人格是否已初始化
2. 获取最近聊天记录
3. 发送到服务器 /us.php 接口
4. 返回生成的图片

使用示例：

```
/yoimg 一个可爱的小女孩在公园玩耍
```

3. /hq - 查询历史记录

功能：查看当前对话的人格和最近聊天记录

使用示例：

```
/hq
```

🔄 工作流程

人格初始化流程

```
用户输入 /yo
    ↓
获取当前人格ID和内容
    ↓
生成随机令牌 (6位数字)
    ↓
POST 请求 → server_url/up.php
    ↓
服务器返回关键词
    ↓
本地缓存关键词
```

图像生成流程

```
用户输入 /yoimg <关键词>
    ↓
检查人格是否已初始化
    ↓
获取最近10条聊天记录
    ↓
格式化聊天记录为 "A内容B内容" 格式
    ↓
POST 请求 → server_url/us.php
    ↓
服务器返回图片URL
    ↓
发送图片给用户
```

📡 接口规范

人设上传接口

URL: {server_url}/up.php
方法: POST
Content-Type: application/json

请求参数：

```json
{
  "name": "人格ID名称",
  "token": "随机6位数字令牌",
  "original_content": "人格的完整system_prompt内容",
  "timestamp": "YYYY-MM-DDTHH:MM:SS格式的时间戳"
}
```

响应格式：

```json
{
  "code": 200,
  "data": {
    "人设名称": "处理后的人格名称",
    "提取关键词": "逗号分隔的关键词"
  }
}
```

图像生成接口

URL: {server_url}/us.php
方法: POST
Content-Type: application/json

请求参数：

```json
{
  "personality": "人格ID名称",
  "chat_record": "格式化的聊天记录（A用户消息B助手消息...）",
  "prompt": "用户输入的关键词"
}
```

响应格式：

```json
{
  "code": 200,
  "data": {
    "local_url": "本地图片URL",
    "gitee_url": "Gitee图片URL",
    "original_prompt": "原始关键词",
    "refined_prompt": "优化后的提示词",
    "personality": "使用的人格ID",
    "chat_record": "使用的聊天记录"
  }
}
```

🗂️ 数据格式

聊天记录格式

· 用户消息：前缀 A + 内容
· 助手消息：前缀 B + 内容
· 示例："A你好B你好啊A今天天气怎么样B天气很好"

时间戳格式

· 格式：YYYY-MM-DDTHH:MM:SS
· 示例：2025-01-15T14:30:25

⚠️ 注意事项

1. 必须先初始化：使用 /yoimg 前必须先执行 /yo 初始化人格
2. 人格设置：确保AstrBot中已设置人格
3. 网络要求：需要能访问配置的服务器地址
4. 调试模式：开启 enable_debug_log 可查看详细请求/响应信息
5. 超时设置：所有请求默认超时时间为300秒

🔍 调试信息

开启调试日志后，会显示：

· 请求的完整URL
· 发送的JSON数据
· 服务器响应的原始数据
· 错误详细信息

📁 文件结构

```
插件目录/
├── main.py              # 主程序
├── _conf_schema.json    # 配置文件
└── data/img_gen_test_cache/
    └── persona_cache.json  # 人格缓存
```

---

网页版
#📁 文件夹
- `api/`api请求信息
- `astrbot_plugin_yoimg/`插件
- `img/`照片缓存目录
- `logs/`日志文件

## 📄 文件列表

- `astrbot_debug.log`人设日志
- `config.json`配置文件
- `config.php`配置文件
- `hk.php`生图接口
- `index.php`配置页
- `personality.json`人格存储文件
- `request.json`响应文件
- `script.js`无
- `style.css`无
- `up.php`人设文件
- `us.php`发送post到hk.php
