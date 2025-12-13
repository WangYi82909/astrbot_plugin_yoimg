from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path

import aiohttp
import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.star.star_tools import StarTools


@register("img_gen_test", "作者", "生图测试插件", "1.0.0")
class ImgGenTest(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.persona_keywords = {}
        self._load_cache()
    
    def _load_cache(self):
        try:
            cache_dir = Path("data/img_gen_test_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            cache_file = cache_dir / "persona_cache.json"
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    self.persona_keywords = json.load(f)
                logger.info(f"已加载 {len(self.persona_keywords)} 个人格缓存")
        except Exception as e:
            logger.error(f"加载缓存失败: {e}")
    
    def _save_cache(self):
        try:
            cache_dir = Path("data/img_gen_test_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            cache_file = cache_dir / "persona_cache.json"
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self.persona_keywords, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
    
    def _generate_random_token(self):
        return str(random.randint(100000, 999999))
    
    @filter.command("hq")
    async def query_history(self, event: AstrMessageEvent):
        try:
            umo = event.unified_msg_origin
            conv_mgr = self.context.conversation_manager
            curr_cid = await conv_mgr.get_curr_conversation_id(umo)
            
            if not curr_cid:
                yield event.plain_result("当前没有对话记录")
                return
            
            conversation = await conv_mgr.get_conversation(umo, curr_cid)
            if not conversation:
                yield event.plain_result("无法获取对话信息")
                return
            
            persona_text = await self._get_personality(conversation)
            history_text = self._get_chat_record_ab(conversation)
            
            yield event.plain_result(f"🧠 当前人设:\n{persona_text[:500]}...\n\n💬 最近聊天记录:\n{history_text}")
            
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
    
    @filter.command("yo")
    async def init_persona(self, event: AstrMessageEvent):
        try:
            umo = event.unified_msg_origin
            conv_mgr = self.context.conversation_manager
            curr_cid = await conv_mgr.get_curr_conversation_id(umo)
            
            if not curr_cid:
                yield event.plain_result("当前没有对话记录")
                return
            
            conversation = await conv_mgr.get_conversation(umo, curr_cid)
            if not conversation:
                yield event.plain_result("无法获取对话信息")
                return
            
            persona_id = conversation.persona_id
            if not persona_id or persona_id == "[%None]":
                yield event.plain_result("当前未设置人格")
                return
            
            persona_content = await self._get_personality(conversation)
            
            server_url = self.config.get("server_url", "http://154.40.35.203:520").rstrip("/")
            upload_url = f"{server_url}/up.php"
            
            upload_data = {
                "name": persona_id,
                "token": self._generate_random_token(),
                "original_content": persona_content,
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            }
            
            yield event.plain_result("正在上传人设...")
            
            result = await self._upload_persona(upload_url, upload_data)
            if result and result.get("code") == 200:
                data = result.get("data", {})
                persona_name = data.get("人设名称", persona_id)
                keywords = data.get("提取关键词", "")
                
                if keywords:
                    self.persona_keywords[persona_id] = {
                        "name": persona_name,
                        "keywords": keywords,
                        "updated_at": datetime.now().isoformat()
                    }
                    self._save_cache()
                    
                    yield event.plain_result(f"✅ 人设上传成功\n📛 人设名称: {persona_name}\n🔑 提取关键词: {keywords[:200]}...")
                else:
                    yield event.plain_result("上传成功但未返回关键词")
            else:
                yield event.plain_result("上传失败")
                
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=self.config.get("enable_debug_log", False))
            yield event.plain_result(f"初始化失败: {str(e)}")
    
    @filter.command("yoimg")
    async def generate_image(self, event: AstrMessageEvent, prompt: str):
        try:
            umo = event.unified_msg_origin
            conv_mgr = self.context.conversation_manager
            curr_cid = await conv_mgr.get_curr_conversation_id(umo)
            
            if not curr_cid:
                yield event.plain_result("当前没有对话记录")
                return
            
            conversation = await conv_mgr.get_conversation(umo, curr_cid)
            if not conversation:
                yield event.plain_result("无法获取对话信息")
                return
            
            persona_id = conversation.persona_id
            if not persona_id or persona_id == "[%None]":
                yield event.plain_result("当前未设置人格")
                return
            
            if persona_id not in self.persona_keywords:
                yield event.plain_result(f"人格 {persona_id} 未初始化，请先使用 /yo 命令")
                return
            
            chat_record = self._get_chat_record_ab(conversation)
            
            server_url = self.config.get("server_url", "http://154.40.35.203:520").rstrip("/")
            generate_url = f"{server_url}/us.php"
            
            api_data = {
                "personality": persona_id,
                "chat_record": chat_record,
                "prompt": prompt
            }
            
            if self.config.get("enable_debug_log", False):
                debug_info = (
                    "📤 调试信息 - 发送请求:\n"
                    f"🔗 URL: {generate_url}\n"
                    f"🧠 人格ID: {persona_id}\n"
                    f"💬 聊天记录: {chat_record[:200]}...\n"
                    f"🎨 关键词: {prompt}"
                )
                yield event.plain_result(debug_info)
            
            yield event.plain_result("正在生成图片...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    generate_url,
                    json=api_data,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if self.config.get("enable_debug_log", False):
                            yield event.plain_result(f"🔍 调试信息 - 响应结果:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
                        
                        if result.get("code") == 200:
                            data = result.get("data", {})
                            
                            image_url = data.get("local_url", "") or data.get("gitee_url", "")
                            refined_prompt = data.get("refined_prompt", "")
                            
                            if image_url:
                                yield event.image_result(image_url)
                                
                                if refined_prompt:
                                    yield event.plain_result(f"✨ 优化后提示词:\n{refined_prompt}")
                            else:
                                yield event.plain_result("生成失败：未返回图片URL")
                        else:
                            msg = result.get("msg", "未知错误")
                            yield event.plain_result(f"API错误: {msg}")
                    else:
                        response_text = await response.text()
                        yield event.plain_result(f"API请求失败: {response.status}\n{response_text}")
                
        except asyncio.TimeoutError:
            yield event.plain_result("请求超时，请稍后重试")
        except aiohttp.ClientError as e:
            yield event.plain_result(f"网络错误: {str(e)}")
        except Exception as e:
            logger.error(f"生成失败: {e}", exc_info=self.config.get("enable_debug_log", False))
            yield event.plain_result(f"生成失败: {str(e)}")
    
    async def _get_personality(self, conversation):
        persona_id = conversation.persona_id
        
        if not persona_id or persona_id == "[%None]":
            return "默认人格"
        
        try:
            persona_mgr = self.context.persona_manager
            persona = await persona_mgr.get_persona(persona_id)
            
            if persona and hasattr(persona, 'system_prompt'):
                system_prompt = persona.system_prompt
                if system_prompt:
                    return system_prompt
                
        except Exception as e:
            logger.error(f"获取人格内容失败: {e}")
        
        return "无法获取详细人设"
    
    def _get_chat_record_ab(self, conversation):
        history_json = conversation.history
        
        if not history_json:
            return "无聊天记录"
        
        try:
            history_data = json.loads(history_json)
            if isinstance(history_data, list):
                recent_messages = history_data[-10:]
                messages = []
                
                for msg in recent_messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role and content:
                        if role == "user":
                            messages.append(f"A{content}")
                        elif role == "assistant":
                            messages.append(f"B{content}")
                
                return "".join(messages)
        except Exception as e:
            logger.error(f"解析聊天记录失败: {e}")
        
        return "无法解析聊天记录"
    
    async def _upload_persona(self, upload_url, upload_data):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    upload_url,
                    json=upload_data,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    response_text = await response.text()
                    
                    if self.config.get("enable_debug_log", False):
                        logger.info(f"上传人设响应: {response_text}")
                    
                    if response.status == 200:
                        return json.loads(response_text)
                        
        except Exception as e:
            logger.error(f"上传人设失败: {e}", exc_info=self.config.get("enable_debug_log", False))
        
        return None
    
    async def terminate(self):
        self._save_cache()
        logger.info("img_gen_test插件已卸载，缓存已保存")