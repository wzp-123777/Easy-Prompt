import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from conversation_handler import ConversationHandler
from profile_manager import ProfileManager
from evaluator_service import EvaluatorService
from language_manager import lang_manager
import llm_helper
import os
from contextlib import asynccontextmanager
from threading import Lock

# 导入新的session管理模块
from schemas import (
    WebSocketMessage, UserResponse, UserConfirmation, ApiConfig, 
    ApiConfigResult, EvaluationUpdate, ChatMessage, MessageType
)
from session_manager import SessionManager, get_session_manager
from session_routes import router as session_router
from typing import Optional

# 移除所有认证功能，直接使用API配置

# 添加API配置锁，确保多用户API配置不冲突
api_config_lock = Lock()

# --- Application Setup ---
# 使用 lifespan 替代已弃用的 on_event 钩子
@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown lifecycle."""
    env_dir = os.path.join(os.path.dirname(__file__), 'env')
    if os.path.exists(env_dir):
        for f in os.listdir(env_dir):
            with open(os.path.join(env_dir, f), 'r', encoding='utf-8') as file:
                os.environ[f] = file.read().strip()
    
    evaluator_service.start()
    try:
        # If server already has a configured global LLM (from REST /api/config), allow the socket to proceed
        try:
            from openai_helper import is_openai_configured as _is_openai_configured
            from gemini_helper import is_gemini_configured as _is_gemini_configured
        except Exception:
            _is_openai_configured = lambda: False
            _is_gemini_configured = lambda: False
        yield
    finally:
        evaluator_service.stop()

app = FastAPI(
    title="Easy-Prompt API",
    description="Interactive prompt generation via WebSocket and REST API.",
    version="1.0.0",
    lifespan=lifespan,
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，解决开发环境跨域问题
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(session_router)


@app.post("/api/config")
async def set_api_config(api_config: ApiConfig, session_id: Optional[str] = None):
    """Allow frontend to POST ApiConfig (so users can enter API key/model in the UI)

    Optional query param `session_id` will persist the config to that session's metadata.
    The route attempts to initialize the configured LLM and returns success/failure.
    """
    # sanitize string fields
    config = {}
    for k, v in api_config.dict().items():
        if isinstance(v, str):
            config[k] = v.strip()
        else:
            config[k] = v

    # If the caller did not include an api_key, try to reuse existing server-side key
    try:
        from openai_helper import openai_config as _openai_config
    except Exception:
        _openai_config = None

    try:
        from gemini_helper import gemini_config as _gemini_config
    except Exception:
        _gemini_config = None

    if not config.get('api_key'):
        if config.get('api_type') == 'openai' and _openai_config and _openai_config.get('api_key'):
            config['api_key'] = _openai_config.get('api_key')
        elif config.get('api_type') == 'gemini' and _gemini_config and _gemini_config.get('api_key'):
            config['api_key'] = _gemini_config.get('api_key')

    # Try to initialize API (reuse existing initialize_api path)
    ok = initialize_api(config)
    if ok:
        # Persist to session metadata if provided
        if session_id:
            try:
                from profile_manager import ProfileManager
                pm = ProfileManager(session_id=session_id)
                pm.update_session_metadata({"api_config": config, "api_type": config.get("api_type", "unknown")})
            except Exception as e:
                print(f"Warning: unable to persist api_config to session {session_id}: {e}")

        return {"success": True, "message": "API配置已初始化"}
    else:
        return {"success": False, "message": "API初始化失败，请检查配置参数"}

evaluator_service = EvaluatorService()

async def send_json(websocket: WebSocket, message_type: str, payload: dict):
    """Utility to send a structured JSON message."""
    # 使用ensure_ascii=False确保中文字符被正确编码为UTF-8，而不是转义序列
    await websocket.send_text(json.dumps({"type": message_type, "payload": payload}, ensure_ascii=False))


# 环境驱动的默认 API 配置探测
def _str2bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def get_empty_api_config() -> dict:
    """返回空的API配置，要求用户必须手动配置"""
    return {
        "api_type": "openai",
        "api_key": "",
        "base_url": "",
        "model": "",
        "evaluator_model": "",
        "temperature": 0.7,
        "max_tokens": 4000,
        "nsfw_mode": False
    }


def initialize_api(api_config: dict) -> bool:
    """Initialize API based on configuration with thread safety"""
    with api_config_lock:  # 确保API配置的线程安全
        try:
            nsfw_mode = api_config.get("nsfw_mode", False)
            if api_config.get("api_type") == "openai":
                api_key = api_config.get("api_key", "")
                base_url = api_config.get("base_url", "")
                model = api_config.get("model", "")
                temperature = api_config.get("temperature", 0.7)
                max_tokens = api_config.get("max_tokens", 4000)

                if not api_key or not base_url or not model:
                    print("错误: OpenAI API配置不完整，缺少必要参数")
                    return False

                return llm_helper.init_llm(
                    nsfw_mode=nsfw_mode,
                    api_type="openai",
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            elif api_config.get("api_type") == "gemini":
                api_key = api_config.get("api_key", "")
                model = api_config.get("model", "")
                evaluator_model = api_config.get("evaluator_model", "")
                temperature = api_config.get("temperature", 0.7)

                if not api_key or not model:
                    print("错误: Gemini API配置不完整，缺少必要参数")
                    return False

                return llm_helper.init_llm(
                    nsfw_mode=nsfw_mode,
                    api_type="gemini",
                    api_key=api_key,
                    model=model,
                    evaluator_model=evaluator_model if evaluator_model else None,
                    temperature=temperature,
                )
            else:
                print(f"不支持的API类型: {api_config.get('api_type')}")
                return False
        except Exception as e:
            print(f"API初始化失败: {e}")
            return False


@app.websocket("/ws/prompt")
async def websocket_endpoint(
    websocket: WebSocket,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Handles WebSocket connections for interactive prompt generation."""
    await websocket.accept()

    handler = None
    session_id = None
    api_initialized = False
    # 将 API 配置限定为当前连接会话的本地变量，避免跨连接污染
    current_api_config = get_empty_api_config()

    try:
        # 1. 等待API配置 — 如果服务器已在全局配置 LLM（例如通过 /api/config 初始化），直接跳过要求
        try:
            from openai_helper import is_openai_configured as _is_openai_configured
            from gemini_helper import is_gemini_configured as _is_gemini_configured
        except Exception:
            _is_openai_configured = lambda: False
            _is_gemini_configured = lambda: False

        if _is_openai_configured() or _is_gemini_configured():
            await send_json(websocket, "api_config_result", {
                "success": True,
                "message": "API（服务器端）已配置 — 直接接受连接"
            })
            api_initialized = True

        # 继续等待API配置（如果当前连接尚未配置）
        while not api_initialized:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)

            message_type = data.get("type")
            payload = data.get("payload", {})

            if message_type == "api_config":
                # 客户端配置API — sanitize string fields to remove accidental whitespace/control chars
                for k, v in payload.items():
                    if isinstance(v, str):
                        current_api_config[k] = v.strip()
                    else:
                        current_api_config[k] = v

                # Initialize API with new configuration
                if initialize_api(current_api_config):
                    await send_json(websocket, "api_config_result", {
                        "success": True,
                        "message": f"API已配置: {current_api_config['api_type']}"
                    })
                    api_initialized = True
                else:
                    await send_json(websocket, "api_config_result", {
                        "success": False,
                        "message": "API配置失败，请检查配置参数"
                    })

            elif message_type == "start_session":
                # 要求用户必须先配置API
                await send_json(websocket, "error", {
                    "message": "请先配置API，点击设置按钮进行配置"
                })
                # 继续等待客户端发送配置

        # 2. 不在这里创建session，等待用户第一条真实消息后再创建
        # 这样避免只发送问候语就创建空session
        print("API已配置，等待用户输入...")
        
        # 3. Main interaction loop
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)

            message_type = data.get("type")
            payload = data.get("payload", {})

            if message_type == "api_config":
                # Allow runtime API reconfiguration for THIS websocket only — sanitize incoming strings
                for k, v in payload.items():
                    if isinstance(v, str):
                        current_api_config[k] = v.strip()
                    else:
                        current_api_config[k] = v
                if initialize_api(current_api_config):
                    await send_json(websocket, "api_config_result", {
                        "success": True,
                        "message": f"API已重新配置: {current_api_config['api_type']}"
                    })
                    # Reset handler with new API
                    handler = session_manager.create_handler(session_id)
                else:
                    await send_json(websocket, "api_config_result", {
                        "success": False,
                        "message": "API重新配置失败"
                    })

            elif message_type == "user_response":
                # 如果还没有创建session，现在创建（用户第一条真实消息）
                if not session_id:
                    try:
                        session = await session_manager.create_session()
                        handler = session_manager.get_handler(session.id)
                        session_id = session.id
                        print(f"收到用户第一条消息，创建session: {session_id}")
                    except Exception as e:
                        print(f"创建session失败: {e}")
                        await send_json(websocket, "error", {
                            "message": f"创建会话失败: {str(e)}"
                        })
                        continue
                
                # 添加用户消息到session
                user_message = ChatMessage(
                    id=f"msg_{int(asyncio.get_event_loop().time() * 1000)}",
                    type=MessageType.USER,
                    content=payload.get("answer", ""),
                    is_complete=True
                )
                await session_manager.add_message_to_session(session_id, user_message)
                
                response_generator = handler.handle_message(payload.get("answer", ""))

                for chunk in response_generator:
                    if chunk.startswith("CONFIRM_GENERATION::"):
                        reason = chunk.split("::", 1)[1]
                        await send_json(websocket, "confirmation_request", {"reason": reason})
                    elif chunk.startswith("EVALUATION_TRIGGER::"):
                        evaluation_message = chunk.split("::", 1)[1]
                        await send_json(websocket, "evaluation_update", {"message": evaluation_message})

                        # 执行实际的评估逻辑
                        try:
                            full_profile = handler.profile_manager.get_full_profile()
                            if full_profile:
                                from llm_helper import evaluate_profile
                                evaluation_result = evaluate_profile(full_profile)
                                if evaluation_result:
                                    critique = evaluation_result.get("critique", "")
                                    extracted_traits = evaluation_result.get("extracted_traits", [])
                                    extracted_keywords = evaluation_result.get("extracted_keywords", [])
                                    evaluation_score = evaluation_result.get("evaluation_score")
                                    completeness_breakdown = evaluation_result.get("completeness_breakdown", {})
                                    suggestions = evaluation_result.get("suggestions", [])
                                    is_ready = evaluation_result.get("is_ready_for_writing", False)

                                    # 发送完整的评估结果
                                    await send_json(websocket, "evaluation_update", {
                                        "message": f"[评估完成] {critique}",
                                        "extracted_traits": extracted_traits,
                                        "extracted_keywords": extracted_keywords,
                                        "evaluation_score": evaluation_score,
                                        "completeness_breakdown": completeness_breakdown,
                                        "suggestions": suggestions,
                                        "is_ready": is_ready
                                    })
                                else:
                                    await send_json(websocket, "evaluation_update", {"message": "[评估服务] 评估失败"})
                            else:
                                await send_json(websocket, "evaluation_update", {"message": "[评估服务] 档案为空"})
                        except Exception as e:
                            print(f"评估过程出错: {e}")
                            await send_json(websocket, "evaluation_update", {"message": f"[评估服务] 评估出错: {str(e)}"})

                    else:
                        await send_json(websocket, "ai_response_chunk", {"chunk": chunk})

            elif message_type == "user_confirmation":
                if not session_id or not handler:
                    await send_json(websocket, "error", {"message": "会话未初始化，请先发送消息"})
                    continue
                    
                if payload.get("confirm", False):
                    await send_json(websocket, "system_message", {"message": lang_manager.t("AI_PROMPT")})
                    final_prompt_stream = handler.finalize_prompt()
                    for chunk in final_prompt_stream:
                        if chunk == "::FINAL_PROMPT_END::":
                            break
                        await send_json(websocket, "final_prompt_chunk", {"chunk": chunk})
                    
                    # 更新session状态为已生成提示词，但不结束会话
                    from schemas import SessionStatus
                    await session_manager.update_session(session_id, status=SessionStatus.PROMPT_GENERATED)
                    
                    # 发送提示词生成完成事件，但不结束会话
                    await send_json(websocket, "prompt_generated", {
                        "message": "提示词已生成，您可以继续补充细节或开始新对话"
                    })
                    # 不再break，继续等待用户输入
                else:
                    await send_json(websocket, "system_message", {"message": lang_manager.t("YOU_PROMPT")})
                    await send_json(websocket, "ai_response_chunk", {"chunk": lang_manager.t('CONTINUE_PROMPT')})
            
            elif message_type == "generate_prompt":
                if not session_id or not handler:
                    await send_json(websocket, "error", {"message": "会话未初始化，请先发送消息"})
                    continue
                    
                # 新增：用户随时请求生成提示词
                await send_json(websocket, "system_message", {"message": "正在生成最终提示词..."})
                final_prompt_stream = handler.finalize_prompt()
                for chunk in final_prompt_stream:
                    if chunk == "::FINAL_PROMPT_END::":
                        break
                    await send_json(websocket, "final_prompt_chunk", {"chunk": chunk})
                
                # 更新session状态
                from schemas import SessionStatus
                await session_manager.update_session(session_id, status=SessionStatus.PROMPT_GENERATED)
                
                # 发送提示词生成完成事件
                await send_json(websocket, "prompt_generated", {
                    "message": "提示词已生成，您可以继续补充细节"
                })
            
            elif message_type == "continue_conversation":
                # 新增：用户选择继续补充细节
                await send_json(websocket, "system_message", {"message": "继续补充角色细节..."})
                await send_json(websocket, "conversation_continued", {
                    "message": "请继续描述您想要补充的角色特征"
                })
            
            elif message_type == "end_session":
                # 新增：用户主动结束会话
                await send_json(websocket, "session_end", {"message": "会话已结束"})
                break

    except WebSocketDisconnect:
        print(f"Client disconnected: {session_id}")
    except Exception as e:
        print(f"An error occurred in session {session_id}: {e}")
        try:
            await send_json(websocket, "error", {"message": str(e)})
        except:
            pass  # Ignore errors if the socket is already closed
    finally:
        if session_id:
            session_manager.remove_handler(session_id)
            print(f"Cleaned up session: {session_id}")


@app.get("/")
async def read_root():
    return {"message": "Welcome to the Easy-Prompt API. Connect via WebSocket at /ws/prompt"}


@app.get("/api/status")
async def get_api_status():
    """Get API configuration status - 不再支持自动配置"""
    status = {
        "supports": ["gemini", "openai"],
        "requires_manual_config": True,
        "message": "请在前端配置API密钥和模型信息"
    }
    return status



@app.get("/api/debug/config")
async def debug_config():
    """Debug endpoint (local only) — returns masked configuration state without secret values.

    NOTE: This endpoint intentionally masks API keys (first/last 4 characters) to avoid leaking secrets.
    """
    try:
        from openai_helper import openai_config, is_openai_configured
    except Exception:
        openai_config = None

    try:
        from gemini_helper import gemini_config, is_gemini_configured
    except Exception:
        gemini_config = None

    def mask_key(key: str | None) -> str | None:
        if not key:
            return None
        if len(key) <= 8:
            return f"{key[:2]}...{key[-2:]}"
        return f"{key[:4]}...{key[-4:]}"

    response = {
        "openai": None,
        "gemini": None
    }

    if openai_config is not None:
        response["openai"] = {
            "configured": is_openai_configured(),
            "base_url": openai_config.get("base_url"),
            "model": openai_config.get("model"),
            "api_key_masked": mask_key(openai_config.get("api_key"))
        }

    if gemini_config is not None:
        response["gemini"] = {
            "configured": is_gemini_configured(),
            "model": gemini_config.get("model"),
            "api_key_masked": mask_key(gemini_config.get("api_key"))
        }

    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8010,
        reload=True,
        log_level="info"
    )
