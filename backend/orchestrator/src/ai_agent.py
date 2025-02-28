"""
AI Agent module for the Atheon AI Orchestrator.

This module provides functions for interacting with LLM providers and
managing AI agent workflows.
"""

import asyncio
from typing import Any, Dict, List, Optional, Union

import anthropic
import openai
from loguru import logger
from pydantic import BaseModel, Field

from src.config import settings
from src.utils import select_llm_provider


class LLMResponse(BaseModel):
    """Model for structured LLM responses."""

    content: str = Field(..., description="The response content")
    model: str = Field(..., description="The model used for generation")
    provider: str = Field(..., description="The provider used (e.g., 'anthropic')")
    usage: Dict[str, int] = Field(..., description="Token usage information")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


async def llm_generate_text(
    prompt: str,
    task_type: str,
    max_tokens: int = 1000,
    temperature: float = 0.7,
    system_prompt: Optional[str] = None,
) -> LLMResponse:
    """
    Generate text using the appropriate LLM provider.

    Args:
        prompt: The prompt to send to the LLM.
        task_type: The type of task (used to select the appropriate provider).
        max_tokens: Maximum number of tokens to generate.
        temperature: Sampling temperature (0.0 to 1.0).
        system_prompt: Optional system prompt for context.

    Returns:
        LLMResponse: The structured response from the LLM.
    """
    # Select the appropriate LLM provider
    provider_config = select_llm_provider(task_type)
    provider = provider_config["provider"]
    model = provider_config["model"]

    logger.info(f"Generating text with {provider} ({model}) for task type {task_type}")

    try:
        if provider == "anthropic":
            return await llm_generate_with_anthropic(
                prompt, model, max_tokens, temperature, system_prompt
            )
        elif provider == "openai":
            return await llm_generate_with_openai(
                prompt, model, max_tokens, temperature, system_prompt
            )
        else:
            # Fallback to default provider
            logger.warning(f"Unknown provider {provider}, falling back to anthropic")
            return await llm_generate_with_anthropic(
                prompt, "claude-3-7-sonnet-20240229", max_tokens, temperature, system_prompt
            )
    except Exception as e:
        logger.error(f"Error generating text with {provider}: {str(e)}")
        # Fallback to a different provider in case of error
        fallback_provider = "openai" if provider != "openai" else "anthropic"
        fallback_model = (
            "gpt-4" if fallback_provider == "openai" else "claude-3-7-sonnet-20240229"
        )
        logger.info(f"Falling back to {fallback_provider} ({fallback_model})")

        if fallback_provider == "anthropic":
            return await llm_generate_with_anthropic(
                prompt, fallback_model, max_tokens, temperature, system_prompt
            )
        else:
            return await llm_generate_with_openai(
                prompt, fallback_model, max_tokens, temperature, system_prompt
            )


async def llm_generate_with_anthropic(
    prompt: str,
    model: str,
    max_tokens: int,
    temperature: float,
    system_prompt: Optional[str] = None,
) -> LLMResponse:
    """
    Generate text using Anthropic's Claude.

    Args:
        prompt: The prompt to send to Claude.
        model: The Claude model to use.
        max_tokens: Maximum number of tokens to generate.
        temperature: Sampling temperature (0.0 to 1.0).
        system_prompt: Optional system prompt for context.

    Returns:
        LLMResponse: The structured response from Claude.
    """
    if not settings.anthropic_api_key:
        raise ValueError("Anthropic API key not configured")

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    messages = [{"role": "user", "content": prompt}]

    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=messages,
    )

    # Extract the response content
    content = response.content[0].text

    # Create a structured response
    return LLMResponse(
        content=content,
        model=model,
        provider="anthropic",
        usage={
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
        metadata={
            "id": response.id,
            "type": response.type,
            "stop_reason": response.stop_reason,
        },
    )


async def llm_generate_with_openai(
    prompt: str,
    model: str,
    max_tokens: int,
    temperature: float,
    system_prompt: Optional[str] = None,
) -> LLMResponse:
    """
    Generate text using OpenAI's GPT models.

    Args:
        prompt: The prompt to send to GPT.
        model: The GPT model to use.
        max_tokens: Maximum number of tokens to generate.
        temperature: Sampling temperature (0.0 to 1.0).
        system_prompt: Optional system prompt for context.

    Returns:
        LLMResponse: The structured response from GPT.
    """
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured")

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    # Extract the response content
    content = response.choices[0].message.content

    # Create a structured response
    return LLMResponse(
        content=content,
        model=model,
        provider="openai",
        usage={
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
        metadata={
            "id": response.id,
            "object": response.object,
            "created": response.created,
        },
    )