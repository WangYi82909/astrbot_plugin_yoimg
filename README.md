# AstrBot Gitee Yoimg插件

本插件提供多样化图片生成Webui面板，支持自定义多种参数，支持llm自然调用，支持提取人设和聊天记录，支持使用润色模型和自定义润色词来优化你的生图命令，支持Gitee模力方舟图片全模型文生图，图生图。
##Webui支持
- 多人格多形象图（若无法部署参考下面的persona条）
- 照片管理
- 人格数据修改
- 详细日志查看
- 更多配置参数

##我无法部署Webui？
依赖flask框架，只有你安装flask依赖，跳转到本目录并python3 app.py跑起来就能使用！
如果不能使用，依然可以正常使用本插件，只是缺少互动性。

##人物形象图
- 访问ip:1200即可
- 如果你无法使用，请进入插件目录personas.json人格配置文件，上传到img目录，其中png_path修改为“img/照片.png”
否则图生图无效。

##功能特性
- llm自然调用
- 支持gitee的图片全模型，对关键词进行润色时，支持使用所有模型，需要自行填写api地址key。
- /yoimg 初始化：命令，提取当前人设精简内容，你可以自行设定提取什么，也可以在webui面板重新填写
- /yo 关键词：文生图命令，提取人设和聊天记录，通过设置的润色模型来补全
- /yoyo 关键词：图生图命令，提取人设和聊天记录通过设置的润色模型补全
- /yozero 关键词：不提取任何聊天记录和人设，从0生成，如果你开启了润色，此刻润色会介入
- 图片比例和分辨率请在插件配置/webui调整
- 支持gitee图片处理文生图，图生图全模型
- 流量池功能：当开启时，您的请求会以post形式转发给他并返回结果，注意，不会携带您的令牌，每小时不超过20张，我们遵循自助共享机制，在流量池中我们提供2000次每天免费调用余额，您在安装插件后默认关闭，若您不需要请关闭并重启astrbot。
## 安装Webui可视化面板
###宝塔部署
```
跳转目录：cd /www/dk_project/dk_app/astrbot/astrbot_WrLE/data/plugins/astrbot_plugin_yoimg //此处可能不固定
一键执行：docker run -d --name flask-aiimg -p 1200:1200 -v $(pwd)/html:/html -v $(pwd)/img:/img -v $(pwd)/logs:/logs -v $(pwd)/personas.json:/personas.json -v $(pwd)/_conf_schema.json:/_conf_schema.json -v $(pwd)/app.py:/app.py:ro -e TZ=Asia/Shanghai --restart unless-stopped --workdir / python:3.9-slim sh -c "pip install flask pymysql mysql-connector-python -q && python /app.py"
请确保1200端口开启
```
###1pan部署
```
一键执行：cd "/opt/1panel/apps/astrbot/astrbot/data/plugins/astrbot_plugin_yoimg" && docker run -d --name flask-aiimg -p 1200:1200 -v $(pwd)/html:/html -v $(pwd)/img:/img -v $(pwd)/logs:/logs -v $(pwd)/personas.json:/personas.json -v $(pwd)/_conf_schema.json:/_conf_schema.json -v $(pwd)/app.py:/app.py:ro -e TZ=Asia/Shanghai --restart unless-stopped --workdir / python:3.9-slim sh -c "pip install flask pymysql mysql-connector-python -q && python /app.py"
请确保路径是插件目录！
```
##其余部署
###win系统
```
pip install flask
cd 插件目录
python3 app.py
后台保活即可
```
## 配置

在 插件配置/Webui中中配置参数：

必要：gitee文生图，图生图端口，我已经提供不要修改！
令牌和参数，cfg不懂勿改
可选：润色模型，对你的词进行润色，支持自行修改ai的润色词说明
流量池：默认关闭，开启后你的请求被转发给流量池，不会携带您的key，可在webui面板上传或访问流量池地址（不加v1），我为共享池提供每天2000次免费调用，遵循自助共享原则。

##共享流量池
我们支持您上传自己的免费令牌。
在您使用共享流量池时，您的令牌不会被传递
###流量池暂不支持图生图

## Gitee AI API Key获取方法，偷木有知。
1.访问https://ai.gitee.com/serverless-api?model=z-image-turbo

2.<img width="2241" height="1280" alt="PixPin_2025-12-05_16-56-27" src="https://github.com/user-attachments/assets/77f9a713-e7ac-4b02-8603-4afc25991841" />

3.<img width="240" height="63" alt="PixPin_2025-12-05_16-56-49" src="https://github.com/user-attachments/assets/6efde7c4-24c6-456a-8108-e78d7613f4fb" />

##图像尺寸只支持以下
    "1:1 (256×256)": (256, 256),
    "1:1 (512×512)": (512, 512),
    "1:1 (1024×1024)": (1024, 1024),
    "1:1 (2048×2048)": (2048, 2048),
    "4:3 (1152×896)": (1152, 896),
    "4:3 (2048×1536)": (2048, 1536),
    "3:4 (768×1024)": (768, 1024),
    "3:4 (1536×2048)": (1536, 2048),
    "3:2 (2048×1360)": (2048, 1360),
    "2:3 (1360×2048)": (1360, 2048),
    "16:9 (1024×576)": (1024, 576),
    "16:9 (2048×1152)": (2048, 1152),
    "9:16 (576×1024)": (576, 1024),
    "9:16 (1152×2048)": (1152, 2048),


### 指令调用

```
/yoimg 初始化 //必须
/yo [关键词] //文生图
/yoyo [关键词] //图生图
/yozero [关键词] //从0开始文生图
LLM自然调用
```

示例：
- `/yoimg ` (使用默认比例 1:1)，可携带初始化参数
- `/yo 看看你的样子`
- `/yoyo 我想看看小猫`
- `/yozero 小猫`


### 自然语言调用

直接与 bot 对话，例如：
- "帮我画一张小猫的图片"
- "生成一个二次元风格的少女"

## 注意事项

注意，修改配置后若无效需要重启，docker容器部署如果webui进不去请重新执行命令即可

### Webui

<img width="1152" height="2048" alt="a.png" src="http://www.xn--v6q40c.xyz/img/a.jpg" />

<img width="1152" height="2048" alt="b.png" src="http://www.xn--v6q40c.xyz/img/b.jpg" />

###图生图展示图

<img width="1152" height="2048" alt="c.png" src="http://www.xn--v6q40c.xyz/img/c.png" />

<img width="1152" height="2048" alt="d.png" src="http://www.xn--v6q40c.xyz/img/d.png" />


