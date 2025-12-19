from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.api.message_components import Plain, Image
from openai import AsyncOpenAI
import aiohttp
import json
import time
import uuid
import asyncio
from pathlib import Path
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import re
import threading
import subprocess


@register("astrbot_plugin_yoimg", "梦千秋", "基于Gitee提供全模型文生图，图生图。", "1.0")
class YoYoPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        
        # ✅ 修正：正确使用StarTools.get_data_dir()
        self.data_dir = Path(StarTools.get_data_dir("astrbot_plugin_yoimg"))
        
        # 所有持久化数据应存储在data_dir下
        self.log_dir = self.data_dir / "logs"
        self.img_dir = self.data_dir / "img"
        self.gitee_img_dir = self.img_dir / "giteeimg"
        
        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        self.img_dir.mkdir(exist_ok=True)
        self.gitee_img_dir.mkdir(exist_ok=True)
        
        # 配置文件路径
        self.personas_file = self.data_dir / "personas.json"
        
        # ✅ 从配置schema读取所有配置
        self.base_url = config.get("base_url", "https://ai.gitee.com/v1")
        self.api_keys = config.get("api_key", [])
        
        # 文生图配置
        self.txt2img_endpoint = config.get("txt2img_endpoint", "https://ai.gitee.com/v1/images/generations")
        self.txt2img_model = config.get("txt2img_model", "z-image-turbo")
        self.txt2img_trigger_words = config.get("txt2img_trigger_words", ["文生图", "生图", "txt2img", "文字生成图片"])
        
        # 图生图配置
        self.img2img_endpoint = config.get("img2img_endpoint", "https://ai.gitee.com/v1/images/edits")
        self.img2img_model = config.get("img2img_model", "Qwen-Image-Edit")
        self.num_inference_steps = config.get("num_inference_steps", 25)
        self.cfg_scale = config.get("cfg_scale", 1)
        
        # 通用图片配置
        self.size = config.get("size", "1024x1024")
        self.llm_default_mode = config.get("llm_default_mode", "img2img")
        
        # 润色配置
        self.sf_url = config.get("sf_base_url", "https://api.siliconflow.cn/v1")
        self.sf_key = config.get("sf_api_key", "")
        self.sf_model = config.get("sf_model", "deepseek-ai/DeepSeek-V3.2")
        self.use_polish = config.get("use_polish", True)
        self.llm_input_prompt = config.get("llm_input_prompt", "")
        self.persona_extract_prompt = config.get("persona_extract_prompt", "请从以下人设描述中提取关键特征（外貌、性格、背景等），生成一个简洁完整的人格描述，适合用于AI图像生成参考。")
        self.chat_history_count = config.get("chat_history_count", 15)
        
        # 共享流量池
        self.debug = config.get("debug_mode", False)
        self.use_shared_pool = config.get("use_shared_pool", False)
        self.shared_pool_url = config.get("shared_pool_url", "http://www.内卷.xyz/v1/")
        
        # 加载人格数据
        self.personas = self._load_personas()
        
        # 处理状态跟踪
        self.processing = set()
        
        # 初始化OpenAI客户端
        self._init_openai_client()
        
        logger.info("✅ YOIMG插件初始化完成，数据目录: %s", self.data_dir)
              
    def _start_flask(self):
        threading.Thread(target=lambda: subprocess.run(
            ['python', 'flask_server.py']
        ), daemon=True).start()
    
    def _init_openai_client(self):
        """初始化OpenAI客户端"""
        if self.api_keys:
            api_key = self.api_keys[0] if isinstance(self.api_keys, list) else str(self.api_keys)
            self.openai_client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=api_key,
                timeout=180
            )
        else:
            self.openai_client = None
    
    def _load_personas(self) -> List[Dict]:
        """加载人格数据"""
        try:
            if self.personas_file.exists():
                with open(self.personas_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data
        except Exception as e:
            logger.error("加载人格数据失败: %s", str(e))
        return []
    
    def _save_personas(self):
        """保存人格数据"""
        try:
            with open(self.personas_file, 'w', encoding='utf-8') as f:
                json.dump(self.personas, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("保存人格数据失败: %s", str(e))
    
    def _find_persona(self, persona_id: str) -> Optional[Dict]:
        """查找指定人格"""
        self.personas = self._load_personas()
        for persona in self.personas:
            if persona.get("persona_id") == persona_id:
                return persona
        return None
    
    @filter.command("yoimg")
    async def init_persona(self, event: AstrMessageEvent):
        """初始化人格"""
        user_id = event.get_sender_id()
        if user_id in self.processing:
            yield event.plain_result("🔄 进行中，请稍候...")
            return
        
        self.processing.add(user_id)
        try:
            persona_data = await self._get_current_persona_data(event)
            if not persona_data:
                yield event.plain_result("❌ 无法获取当前人格信息")
                return
            
            persona_id = persona_data["id"]
            raw_persona = persona_data["raw_persona"]
            
            existing = self._find_persona(persona_id)
            if existing:
                yield event.plain_result(f"⚠️ 人格 '{persona_id}' 已存在，将更新")
            
            polished_prompt = await self._call_polish_api(
                system_prompt=self.persona_extract_prompt,
                user_content=f"人设描述：\n{raw_persona}",
                api_type="init_extract"
            )
            
            if not polished_prompt:
                yield event.plain_result("❌ 润色失败，无法生成人格描述")
                return
            
            persona_entry = {
                "persona_id": persona_id,
                "png_path": "",
                "local_path": "",
                "polish_time": time.strftime("%Y/%m/%d %H:%M:%S"),
                "polished_prompt": polished_prompt
            }
            
            if existing:
                existing.update(persona_entry)
            else:
                self.personas.append(persona_entry)
            
            self._save_personas()
            
            result_msg = f"✅ 人格初始化完成！\n人格ID: {persona_id}"
            yield event.plain_result(result_msg)
            
        except Exception as e:
            logger.error("人格初始化失败: %s", str(e))
            yield event.plain_result(f"❌ 初始化失败: {str(e)}")
        finally:
            self.processing.discard(user_id)
    
    @filter.command("yo")
    async def txt2img_command(self, event: AstrMessageEvent):
        """文生图命令"""
        message_str = event.message_str.strip()
        if message_str.startswith("/yo "):
            keyword = message_str[4:].strip()
        else:
            keyword = message_str.replace("/yo", "").strip()
        
        if not keyword:
            yield event.plain_result("请提供关键词，例如：/yo 樱花树下")
            return
        
        async for result in self._generate_image(event, keyword, is_txt2img=True):
            yield result
    
    @filter.command("yoyo")
    async def img2img_command(self, event: AstrMessageEvent):
        """图生图命令"""
        message_str = event.message_str.strip()
        if message_str.startswith("/yoyo "):
            keyword = message_str[6:].strip()
        else:
            keyword = message_str.replace("/yoyo", "").strip()
        
        if not keyword:
            yield event.plain_result("请提供关键词，例如：/yoyo 在公园")
            return
        
        async for result in self._generate_image(event, keyword, is_txt2img=False):
            yield result
    
    @filter.command("yozero")
    async def txt2img_direct_command(self, event: AstrMessageEvent):
        """直接文生图命令"""
        message_str = event.message_str.strip()
        if message_str.startswith("/yozero "):
            keyword = message_str[8:].strip()
        else:
            keyword = message_str.replace("/yozero", "").strip()
        
        if not keyword:
            yield event.plain_result("请提供关键词，例如：/yozero 樱花树下")
            return
        
        user_id = event.get_sender_id()
        if user_id in self.processing:
            yield event.plain_result("🔄 进行中，请稍候...")
            return
        
        self.processing.add(user_id)
        req_id = f"req_{uuid.uuid4().hex[:13]}"
        
        try:
            result = await self._call_txt2img_api(req_id, keyword)
            
            if result["success"]:
                if self.debug:
                    yield event.chain_result([Image.fromFileSystem(result["path"]), Plain("✅ 图片生成成功！")])
                else:
                    yield event.chain_result([Image.fromFileSystem(result["path"])])
            else:
                yield event.plain_result(f"❌ 生成失败: {result['error']}")
                
        except Exception as e:
            logger.error("直接文生图失败: %s", str(e))
            yield event.plain_result(f"❌ 生成过程异常: {str(e)}")
        finally:
            self.processing.discard(user_id)
    
    async def _generate_image(self, event: AstrMessageEvent, keyword: str, is_txt2img: bool):
        """生成图像核心逻辑"""
        user_id = event.get_sender_id()
        if user_id in self.processing:
            yield event.plain_result("🔄 进行中，请稍候...")
            return
        
        self.processing.add(user_id)
        req_id = f"req_{uuid.uuid4().hex[:13]}"
        
        try:
            persona_data = await self._get_current_persona_data(event)
            if not persona_data:
                yield event.plain_result("❌ 未找到当前人格信息")
                return
            
            persona_id = persona_data["id"]
            persona_entry = self._find_persona(persona_id)
            if not persona_entry:
                yield event.plain_result(f"❌ 人格 '{persona_id}' 未初始化，请先使用 /yoimg 初始化")
                return
            
            polished_prompt = persona_entry.get("polished_prompt", "")
            if not polished_prompt:
                yield event.plain_result(f"❌ 人格 '{persona_id}' 没有润色描述")
                return
            
            _, chat_history = await self._get_conversation_data(event)
            
            if self.use_polish and self.sf_key:
                final_prompt = await self._call_polish_api(
                    system_prompt=self.llm_input_prompt,
                    user_content=f"人格描述：{polished_prompt}\n聊天记录：{chat_history}\n关键词：{keyword}",
                    api_type=f"{'txt2img' if is_txt2img else 'img2img'}_polish"
                )
                
                if not final_prompt:
                    yield event.plain_result("❌ 润色失败")
                    return
            else:
                final_prompt = f"{polished_prompt}，{keyword}"
            
            # 校验final_prompt不为空
            if not final_prompt.strip():
                yield event.plain_result("❌ 生成提示词为空，无法调用API")
                return

            if is_txt2img:
                result = await self._call_txt2img_api(req_id, final_prompt)
            else:
                png_path = persona_entry.get("png_path", "").strip()
                if not png_path:
                    yield event.plain_result("❌ 人格未上传形象图，请通过管理面板上传")
                    return
                
                image_path = Path(png_path)
                if not image_path.is_absolute():
                    image_path = self.data_dir / png_path
                
                if not image_path.exists():
                    error_msg = f"❌ 文件不存在！\n路径: {image_path}"
                    self._log_error_only(error_msg)
                    yield event.plain_result(error_msg)
                    return
                
                result = await self._call_img2img_api(req_id, final_prompt, image_path)
            
            if result["success"]:
                if self.debug:
                    yield event.chain_result([Image.fromFileSystem(result["path"]), Plain("✅ 图片生成成功！")])
                else:
                    yield event.chain_result([Image.fromFileSystem(result["path"])])
            else:
                yield event.plain_result(f"❌ 生成失败: {result['error']}")
                
        except Exception as e:
            logger.error("图像生成失败: %s", str(e))
            yield event.plain_result(f"❌ 生成过程异常: {str(e)}")
        finally:
            self.processing.discard(user_id)
    
    async def _call_txt2img_api(self, req_id: str, prompt: str) -> Dict[str, Any]:
        """调用文生图API"""
        if self.use_shared_pool and self.shared_pool_url:
            return await self._call_shared_pool_txt2img(req_id, prompt)
        
        if not self.openai_client:
            return self._error_result("未配置API密钥")
        
        try:
            self._log_to_gitee(req_id, "txt2img", "request", {
                "method": "openai_sdk",
                "model": self.txt2img_model,
                "prompt": prompt,
                "size": self.size
            })
            
            response = await self.openai_client.images.generate(
                prompt=prompt,
                model=self.txt2img_model,
                size=self.size,
                n=1,
                response_format="url"
            )
            
            if not response.data:
                return self._error_result("未返回图片数据")
            
            image_data = response.data[0]
            if image_data.url:
                save_path = await self._download_image(image_data.url)
            elif hasattr(image_data, 'b64_json') and image_data.b64_json:
                image_bytes = base64.b64decode(image_data.b64_json)
                filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
                save_path = self.gitee_img_dir / filename
                with open(save_path, 'wb') as f:
                    f.write(image_bytes)
            else:
                return self._error_result("未返回有效的图片数据")
            
            self._log_to_gitee(req_id, "txt2img", "response", {
                "status": "success",
                "save_path": str(save_path)
            })
            
            return {
                "success": True,
                "path": str(save_path)
            }
            
        except Exception as e:
            error_info = str(e)
            self._log_to_gitee(req_id, "txt2img", "response", {
                "status": "error",
                "error": error_info
            })
            
            return await self._call_txt2img_native(req_id, prompt)
    
    async def _call_txt2img_native(self, req_id: str, prompt: str) -> Dict[str, Any]:
        """原生文生图API调用"""
        if self.use_shared_pool and self.shared_pool_url:
            return await self._call_shared_pool_txt2img(req_id, prompt)
        
        if not self.api_keys:
            return self._error_result("未配置API密钥")
        
        api_key = self.api_keys[0] if isinstance(self.api_keys, list) else str(self.api_keys)
        
        try:
            request_body = {
                "prompt": prompt,
                "model": self.txt2img_model,
                "size": self.size,
                "n": 1,
                "response_format": "url",
                "num_inference_steps": self.num_inference_steps
            }
            
            self._log_to_gitee(req_id, "txt2img_native", "request", {
                "endpoint": self.txt2img_endpoint,
                "body": request_body
            })
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.txt2img_endpoint,
                    json=request_body,
                    headers=headers,
                    timeout=180
                ) as resp:
                    resp_text = await resp.text()
                    
                    self._log_to_gitee(req_id, "txt2img_native", "response", {
                        "status_code": resp.status,
                        "response": resp_text
                    })
                    
                    if resp.status != 200:
                        return self._error_result(f"HTTP {resp.status}: {resp_text[:200]}")
                    
                    result = json.loads(resp_text)
                    
                    if "data" not in result or not result["data"]:
                        return self._error_result("返回数据格式错误")
                    
                    image_info = result["data"][0]
                    if "url" not in image_info:
                        return self._error_result("未返回图片URL")
                    
                    img_url = image_info["url"]
                    save_path = await self._download_image(img_url)
                    
                    return {
                        "success": True,
                        "path": str(save_path)
                    }
                    
        except Exception as e:
            error_info = str(e)
            self._log_to_gitee(req_id, "txt2img_native", "response", {
                "status": "error",
                "error": error_info
            })
            return self._error_result(f"原生文生图失败: {error_info}")
    
    async def _call_shared_pool_txt2img(self, req_id: str, prompt: str) -> Dict[str, Any]:
        """调用共享流量池文生图API"""
        if not self.shared_pool_url:
            return self._error_result("共享流量池URL未配置")
        if not prompt.strip():
            return self._error_result("文生图提示词为空，无法发送请求")
        
        try:
            request_body = {
                "prompt": prompt.strip(),
                "model": self.txt2img_model or "z-image-turbo",
                "size": self.size or "1024x1024",
                "n": 1,
                "response_format": "url",
                "num_inference_steps": self.num_inference_steps
            }

            request_body = {k: v for k, v in request_body.items() if v}
            
            self._log_to_gitee(req_id, "shared_pool_txt2img", "request", {
                "endpoint": self.shared_pool_url,
                "body": request_body
            })
            
            headers = {
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.shared_pool_url,
                    json=request_body,
                    headers=headers,
                    timeout=180
                ) as resp:
                    
                    resp_text = await resp.text()
                    
                    self._log_to_gitee(req_id, "shared_pool_txt2img", "response", {
                        "status_code": resp.status,
                        "response": resp_text
                    })
                    
                    if resp.status != 200:
                        return self._error_result(f"共享流量池HTTP {resp.status}: {resp_text[:200]}")
                    
                    try:
                        result = json.loads(resp_text)
                    except json.JSONDecodeError:
                        return self._error_result(f"共享流量池返回非JSON数据: {resp_text[:200]}")
                    
                    if "data" not in result or not result["data"]:
                        return self._error_result("共享流量池返回数据格式错误，缺少data字段")
                    
                    image_info = result["data"][0]
                    if "url" not in image_info:
                        return self._error_result("共享流量池未返回图片URL")
                    
                    img_url = image_info["url"]
                    save_path = await self._download_image(img_url)
                    
                    return {
                        "success": True,
                        "path": str(save_path)
                    }
                    
        except Exception as e:
            error_info = str(e)
            self._log_to_gitee(req_id, "shared_pool_txt2img", "response", {
                "status": "error",
                "error": error_info
            })
            return self._error_result(f"共享流量池文生图失败: {error_info}")
    
    async def _call_img2img_api(self, req_id: str, prompt: str, image_path: Path) -> Dict[str, Any]:
        """调用图生图API"""
        if self.use_shared_pool and self.shared_pool_url:
            return await self._call_shared_pool_img2img(req_id, prompt, image_path)
        
        if not self.api_keys:
            return self._error_result("未配置API密钥")
        
        api_key = self.api_keys[0] if isinstance(self.api_keys, list) else str(self.api_keys)
        
        try:
            data = aiohttp.FormData()
            data.add_field('model', self.img2img_model)
            data.add_field('prompt', prompt)
            data.add_field('n', '1')
            data.add_field('size', self.size)
            data.add_field('response_format', 'url')
            data.add_field('num_inference_steps', str(self.num_inference_steps))
            data.add_field('cfg_scale', str(self.cfg_scale))
            
            ext = image_path.suffix.lower()
            content_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            content_type = content_type_map.get(ext, 'application/octet-stream')
            
            headers = {"Authorization": f"Bearer {api_key}"}
            
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            self._log_to_gitee(req_id, "img2img", "request", {
                "endpoint": self.img2img_endpoint,
                "body": {
                    "model": self.img2img_model,
                    "prompt": prompt[:100],
                    "size": self.size,
                    "num_inference_steps": self.num_inference_steps,
                    "cfg_scale": self.cfg_scale,
                    "image_name": image_path.name,
                    "image_size": len(image_data)
                }
            })
            
            async with aiohttp.ClientSession() as session:
                with open(image_path, 'rb') as f:
                    data.add_field(
                        'image',
                        f,
                        filename=image_path.name,
                        content_type=content_type
                    )
                    
                    async with session.post(
                        self.img2img_endpoint, 
                        data=data,
                        headers=headers, 
                        timeout=180
                    ) as resp:
                        
                        resp_text = await resp.text()
                        
                        self._log_to_gitee(req_id, "img2img", "response", {
                            "status_code": resp.status,
                            "response": resp_text
                        })
                        
                        if resp.status != 200:
                            return self._error_result(f"HTTP {resp.status}: {resp_text[:200]}")
                        
                        result = json.loads(resp_text)
                        
                        if "data" not in result or not result["data"]:
                            return self._error_result("返回数据格式错误")
                        
                        image_info = result["data"][0]
                        if "url" not in image_info:
                            return self._error_result("未返回图片URL")
                        
                        img_url = image_info["url"]
                        save_path = await self._download_image(img_url)
                        
                        return {
                            "success": True,
                            "path": str(save_path)
                        }
                        
        except Exception as e:
            error_info = str(e)
            self._log_to_gitee(req_id, "img2img", "response", {
                "status": "error",
                "error": error_info
            })
            return self._error_result(f"图生图失败: {error_info}")
    
    async def _call_shared_pool_img2img(self, req_id: str, prompt: str, image_path: Path) -> Dict[str, Any]:
        """调用共享流量池图生图API"""
        if not self.shared_pool_url:
            return self._error_result("共享流量池URL未配置")
        if not prompt.strip():
            return self._error_result("图生图提示词为空")
        if not image_path.exists():
            return self._error_result(f"原图不存在: {str(image_path)}")
        
        try:
            data = aiohttp.FormData()
            data.add_field('model', self.img2img_model or "z-image-turbo")
            data.add_field('prompt', prompt.strip())
            data.add_field('n', '1')
            data.add_field('size', self.size or "1024x1024")
            data.add_field('response_format', 'url')
            data.add_field('num_inference_steps', str(self.num_inference_steps))
            data.add_field('cfg_scale', str(self.cfg_scale))
            
            ext = image_path.suffix.lower()
            content_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            content_type = content_type_map.get(ext, 'application/octet-stream')
            
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            self._log_to_gitee(req_id, "shared_pool_img2img", "request", {
                "endpoint": self.shared_pool_url,
                "body": {
                    "model": self.img2img_model,
                    "prompt": prompt[:100],
                    "size": self.size,
                    "num_inference_steps": self.num_inference_steps,
                    "cfg_scale": self.cfg_scale,
                    "image_name": image_path.name,
                    "image_size": len(image_data)
                }
            })
            
            async with aiohttp.ClientSession() as session:
                with open(image_path, 'rb') as f:
                    data.add_field(
                        'image',
                        f,
                        filename=image_path.name,
                        content_type=content_type
                    )
                    
                    async with session.post(
                        self.shared_pool_url, 
                        data=data,
                        timeout=180
                    ) as resp:
                        
                        resp_text = await resp.text()
                        
                        self._log_to_gitee(req_id, "shared_pool_img2img", "response", {
                            "status_code": resp.status,
                            "response": resp_text
                        })
                        
                        if resp.status != 200:
                            return self._error_result(f"共享流量池HTTP {resp.status}: {resp_text[:200]}")
                        
                        try:
                            result = json.loads(resp_text)
                        except json.JSONDecodeError:
                            return self._error_result(f"共享流量池返回非JSON数据: {resp_text[:200]}")
                        
                        if "data" not in result or not result["data"]:
                            return self._error_result("共享流量池返回数据格式错误，缺少data字段")
                        
                        image_info = result["data"][0]
                        if "url" not in image_info:
                            return self._error_result("共享流量池未返回图片URL")
                        
                        img_url = image_info["url"]
                        save_path = await self._download_image(img_url)
                        
                        return {
                            "success": True,
                            "path": str(save_path)
                        }
                        
        except Exception as e:
            error_info = str(e)
            self._log_to_gitee(req_id, "shared_pool_img2img", "response", {
                "status": "error",
                "error": error_info
            })
            return self._error_result(f"共享流量池图生图失败: {error_info}")
    
    async def _call_polish_api(self, system_prompt: str, user_content: str, api_type: str) -> Optional[str]:
        """调用润色API"""
        if not self.sf_key:
            return None
        
        req_id = uuid.uuid4().hex[:8]
        
        try:
            request_body = {
                "model": self.sf_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            self._log_to_gitee(req_id, api_type, "request", {
                "endpoint": f"{self.sf_url}/chat/completions",
                "body": request_body
            })
            
            headers = {
                "Authorization": f"Bearer {self.sf_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.sf_url}/chat/completions",
                    json=request_body,
                    headers=headers,
                    timeout=30
                ) as resp:
                    
                    resp_text = await resp.text()
                    
                    self._log_to_gitee(req_id, api_type, "response", {
                        "status_code": resp.status,
                        "response": resp_text
                    })
                    
                    if resp.status != 200:
                        return None
                    
                    result = json.loads(resp_text)
                    if "choices" not in result or len(result["choices"]) == 0:
                        return None
                    return result["choices"][0]["message"]["content"].strip()
            
            return None
        except Exception as e:
            logger.error("润色API调用失败: %s", str(e))
            return None
    
    def _log_to_gitee(self, req_id: str, api_type: str, call_type: str, data: Dict):
        """记录Gitee日志"""
        try:
            log_file = self.log_dir / "gitee.log"
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "req_id": req_id,
                "api_type": api_type,
                "call_type": call_type,
                "data": data
            }
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error("记录Gitee日志失败: %s", str(e))
    
    def _log_error_only(self, error_msg: str):
        """记录错误日志"""
        try:
            log_file = self.log_dir / "error.log"
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "error": error_msg
            }
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error("记录错误日志失败: %s", str(e))
    
    async def _get_current_persona_data(self, event: AstrMessageEvent) -> Optional[Dict]:
        """获取当前人格数据"""
        try:
            umo = event.unified_msg_origin
            conv_mgr = self.context.conversation_manager
            curr_cid = await conv_mgr.get_curr_conversation_id(umo)
            
            if not curr_cid:
                return None
            
            conversation = await conv_mgr.get_conversation(umo, curr_cid)
            if not conversation:
                return None
            
            persona_id = conversation.persona_id
            if not persona_id or persona_id == "[%None]":
                persona_id = "default"
            
            raw_persona = "默认人设"
            if persona_id != "default":
                persona_mgr = self.context.persona_manager
                persona = await persona_mgr.get_persona(persona_id)
                if persona and hasattr(persona, 'system_prompt'):
                    raw_persona = persona.system_prompt
            
            return {
                "id": persona_id,
                "raw_persona": raw_persona
            }
            
        except Exception as e:
            logger.error("获取当前人格数据失败: %s", str(e))
            return None
    
    async def _get_conversation_data(self, event: AstrMessageEvent):
        """获取对话数据"""
        try:
            umo = event.unified_msg_origin
            conv_mgr = self.context.conversation_manager
            curr_cid = await conv_mgr.get_curr_conversation_id(umo)
            
            if not curr_cid:
                return "默认人设", ""
            
            conversation = await conv_mgr.get_conversation(umo, curr_cid)
            if not conversation:
                return "默认人设", ""
            
            persona_text = "默认人设"
            persona_id = conversation.persona_id
            if persona_id and persona_id != "[%None]":
                persona_mgr = self.context.persona_manager
                persona = await persona_mgr.get_persona(persona_id)
                if persona and hasattr(persona, 'system_prompt'):
                    persona_text = persona.system_prompt
            
            chat_text = ""
            history_json = conversation.history
            if history_json:
                try:
                    history_data = json.loads(history_json)
                    if isinstance(history_data, list):
                        recent_messages = history_data[-self.chat_history_count:]
                        messages = []
                        for msg in recent_messages:
                            role = msg.get("role", "")
                            content = msg.get("content", "")
                            if role and content:
                                if role == "user":
                                    messages.append(f"A{content}")
                                elif role == "assistant":
                                    messages.append(f"B{content}")
                        chat_text = "".join(messages)
                except Exception:
                    chat_text = ""
            
            return persona_text, chat_text
            
        except Exception as e:
            logger.error("获取对话数据失败: %s", str(e))
            return "默认人设", ""
    
    async def _download_image(self, url: str) -> Path:
        """下载图片到本地"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
                    save_path = self.gitee_img_dir / filename
                    with open(save_path, 'wb') as f:
                        f.write(data)
                    return save_path
                else:
                    raise Exception(f"下载失败: HTTP {resp.status}")
    
    def _error_result(self, error: str) -> Dict[str, Any]:
        """返回错误结果"""
        return {
            "success": False,
            "error": error
        }
    
    @filter.llm_tool(name="yoyo_draw")
    async def yoyo_llm_tool(self, event: AstrMessageEvent, prompt: str):
        """
        根据描述生成图像，结合当前人格和聊天记录。
        
        Args:
            prompt(string): 图像描述，可包含触发词如"文生图"
        """
        user_id = event.get_sender_id()
        
        if user_id in self.processing:
            return "正在处理中，请稍候..."
        
        self.processing.add(user_id)
        
        try:
            # 确定生成模式
            is_txt2img = self.llm_default_mode == "txt2img" or any(
                word in prompt for word in self.txt2img_trigger_words
            )
            
            keyword = prompt
            for trigger in self.txt2img_trigger_words:
                keyword = keyword.replace(trigger, "").strip()
            
            if not keyword:
                return "请提供图片描述"
            
            # 获取人格数据
            persona_data = await self._get_current_persona_data(event)
            if not persona_data:
                return "未找到当前人格信息"
            
            persona_id = persona_data["id"]
            persona_entry = self._find_persona(persona_id)
            
            if not persona_entry:
                return f"人格 '{persona_id}' 未初始化"
            
            polished_prompt = persona_entry.get("polished_prompt", "")
            if not polished_prompt:
                return f"人格 '{persona_id}' 没有润色描述"
            
            # 获取聊天记录
            _, chat_history = await self._get_conversation_data(event)
            
            # 润色处理
            if self.use_polish and self.sf_key:
                final_prompt = await self._call_polish_api(
                    system_prompt=self.llm_input_prompt,
                    user_content=f"人格描述：{polished_prompt}\n聊天记录：{chat_history}\n关键词：{keyword}",
                    api_type=f"{'txt2img' if is_txt2img else 'img2img'}_polish_llm"
                )
                
                if not final_prompt:
                    return "润色失败"
            else:
                final_prompt = f"{polished_prompt}，{keyword}"
            
            if not final_prompt.strip():
                return "生成提示词为空，无法调用API"

            # 调用图像生成API
            req_id = f"req_{uuid.uuid4().hex[:13]}"
            
            if is_txt2img:
                result = await self._call_txt2img_api(req_id, final_prompt)
            else:
                # 图生图需要检查形象图
                png_path = persona_entry.get("png_path", "").strip()
                if not png_path:
                    return "人格未上传形象图"
                
                image_path = Path(png_path)
                if not image_path.is_absolute():
                    image_path = self.data_dir / png_path
                
                if not image_path.exists():
                    return "形象图文件不存在"
                
                result = await self._call_img2img_api(req_id, final_prompt, image_path)
            
            if result["success"]:
                # 手动发送图片
                await event.send(event.chain_result([Image.fromFileSystem(result["path"])]))
                # 返回描述性字符串
                return f"已为 {persona_id} 人格生成图片。Prompt: {keyword}"
            else:
                return f"生成失败: {result.get('error', '未知错误')}"
                
        except Exception as e:
            error_msg = str(e)
            logger.error("LLM工具生成图像失败: %s", error_msg)
            return f"生成过程异常: {error_msg}"
        finally:
            self.processing.discard(user_id)
    
    async def terminate(self):
        """插件终止时清理资源"""
        self.processing.clear()
        logger.info("YOIMG插件已停止")