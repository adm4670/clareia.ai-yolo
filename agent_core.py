import os
import json
import asyncio
import logging
import base64
from pathlib import Path
from typing import Any, Optional, List, Dict, Callable

from openai import OpenAI

ToolSchema = Dict[str, Any]
ToolHandler = Callable[..., Any]

logger = logging.getLogger(__name__)


class Agent:
    def __init__(
        self,
        name: str,
        role: str,
        goal: str,
        backstory: str,
        model: Optional[str] = None,
        general_instructions: Optional[str] = None,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ):
        self.name = name
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.history: List[Dict[str, Any]] = []

        self.general_instructions = general_instructions or (
            "- Responda em português do Brasil.\n"
            "- Seja objetivo e claro.\n"
        )

        self.tool_schemas: List[ToolSchema] = []
        self.tool_handlers: Dict[str, ToolHandler] = {}
        self._register_tools(tools or [])

        self._log(f"Iniciado | model={self.model} | tools={list(self.tool_handlers)}")

    # ------------------------------------------------------------------ #
    # Utils
    # ------------------------------------------------------------------ #

    def _log(self, msg: str) -> None:
        logger.info(f"[Agent:{self.name}] {msg}")

    def _system_prompt(self) -> str:
        return (
            f"Você é o agente '{self.name}'.\n\n"
            f"Papel: {self.role}\n"
            f"Objetivo: {self.goal}\n"
            f"Contexto: {self.backstory}\n\n"
            f"Instruções:\n{self.general_instructions}"
        )

    # ------------------------------------------------------------------ #
    # Image utils (multimodal)
    # ------------------------------------------------------------------ #

    def _image_to_input(self, image: str) -> Dict[str, Any]:
        """
        Aceita caminho local ou URL.
        """
        if image.startswith("http://") or image.startswith("https://"):
            return {
                "type": "input_image",
                "image_url": image
            }

        path = Path(image)
        if not path.exists():
            raise FileNotFoundError(f"Imagem não encontrada: {image}")

        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        return {
            "type": "input_image",
            "image_base64": encoded
        }

    # ------------------------------------------------------------------ #
    # Tools
    # ------------------------------------------------------------------ #

    def _register_tools(self, tools: List[Dict[str, Any]]) -> None:
        for raw in tools:
            if not isinstance(raw, dict):
                continue

            schema = raw.get("schema", raw)
            handler = raw.get("handler")

            schema = {k: v for k, v in schema.items() if k != "handler"}

            name = (
                schema.get("name")
                if schema.get("type") == "function"
                else schema.get("function", {}).get("name")
            )

            if name and handler:
                self.tool_handlers[name] = handler
                self._log(f"Tool registrada: {name}")

            if schema:
                self.tool_schemas.append(schema)

    # ------------------------------------------------------------------ #
    # Conversation builder (multimodal)
    # ------------------------------------------------------------------ #

    def _build_conversation(
        self,
        user_message: str,
        *,
        images: Optional[List[str]] = None,
        context: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:

        conversation = [
            {
                "role": "system",
                "content": [
                    {"type": "input_text", "text": self._system_prompt()}
                ],
            }
        ]

        for msg in context or []:
            content = msg["content"]
            if isinstance(content, str):
                content = [{
                    "type": "output_text" if msg["role"] == "assistant" else "input_text",
                    "text": content
                }]
            conversation.append({"role": msg["role"], "content": content})

        user_content = [{"type": "input_text", "text": user_message}]

        for img in images or []:
            user_content.append(self._image_to_input(img))

        conversation.append({
            "role": "user",
            "content": user_content
        })

        return conversation

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #

    async def run(
        self,
        user_message: str,
        *,
        images: Optional[List[str]] = None,
        context: Optional[List[Dict[str, Any]]] = None,
    ) -> str:

        conversation = self._build_conversation(
            user_message=user_message,
            images=images,
            context=context
        )

        response_text = await self._run_with_tools(conversation)

        if response_text:
            self.history.append(
                {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": response_text}],
                }
            )

        return response_text

    async def _run_with_tools(self, conversation: List[Dict[str, Any]]) -> str:
        while True:
            response = self.client.responses.create(
                model=self.model,
                input=conversation,
                tools=self.tool_schemas or None,
            )

            text = getattr(response, "output_text", "") or ""

            calls = [
                item for item in getattr(response, "output", [])
                if item.type == "function_call"
            ]

            if not calls:
                return text

            for call in calls:
                output = await self._execute_tool(call)
                conversation.extend([
                    {
                        "type": "function_call",
                        "name": call.name,
                        "arguments": call.arguments,
                        "call_id": call.call_id,
                    },
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": output,
                    }
                ])

    async def _execute_tool(self, call) -> str:
        handler = self.tool_handlers.get(call.name)
        if not handler:
            return f"Erro: tool '{call.name}' não registrada."

        try:
            args = json.loads(call.arguments) if call.arguments else {}
        except Exception:
            args = {}

        try:
            result = (
                await handler(**args)
                if asyncio.iscoroutinefunction(handler)
                else handler(**args)
            )
        except Exception as e:
            return f"Erro ao executar '{call.name}': {e}"

        if isinstance(result, str):
            return result

        return json.dumps(result, ensure_ascii=False, default=str)

    # ------------------------------------------------------------------ #

    def reset_history(self) -> None:
        self.history.clear()
        self._log("Histórico resetado")