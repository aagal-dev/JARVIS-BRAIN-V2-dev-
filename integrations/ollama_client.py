import ollama

from typing import Generic, Optional, TypeVar, Type
from pydantic import BaseModel, ValidationError

import json

T = TypeVar("T", bound=BaseModel)


class LLMResponse(BaseModel, Generic[T]):
    success: bool
    output: Optional[str] = None
    data: Optional[T] = None
    error: Optional[str] = None


class OllamaClient:
    def __init__(
        self,
        model: str = "gpt-oss:120b-cloud",
        max_token_output: int = 4096,
        temperature: float = 0.2,
    ):
        self.model = model
        self.max_token_output = max_token_output
        self.temperature = temperature

    def generate(
        self,
        state,
        response_model: Optional[Type[T]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse[T]:

        try:
            # Structured output schema
            output_format = None

            if response_model is not None:
                output_format = response_model.model_json_schema()
          
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt or "",
                    },
                    {
                        "role": "user",
                        "content": str(state),
                    },
                ],
                format=output_format,
                options={
                    "temperature": self.temperature,
                    "num_predict": self.max_token_output,
                },
            )

            #print("\nFrom ollama_client:")
            #print(response.model_dump_json(indent=2))

            content = response["message"]["content"]

            #print("\nFrom ollama_client (LLM response):")
            #print(content)
          
            # Structured response
            if response_model is not None:
                data = response_model.model_validate_json(content)
              
                return LLMResponse[T](
                    success=True,
                    output=content,
                    data=data,
                )

            # Normal text response
            return LLMResponse[T](
                success=True,
                output=content,
            )

        except ValidationError as e:
            return LLMResponse[T](
                success=False,
                error=f"Output validation failed: {e}",
            )

        except Exception as e:
            return LLMResponse[T](
                success=False,
                error=str(e),
            )