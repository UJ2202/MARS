"""
AG2 Integration Hooks for Event Capture

Monkey-patches AG2 classes to automatically capture events without
requiring code changes in CMBAgent.
"""

import logging
from typing import Optional, Any, Dict
import functools
import time

logger = logging.getLogger(__name__)

from cmbagent.execution.event_capture import get_event_captor

# Track if hooks are already installed (idempotency)
_hooks_installed = False


def patch_conversable_agent():
    """
    Patch ConversableAgent to capture message events.
    """
    try:
        from autogen import ConversableAgent
        
        # Store original methods
        original_generate_reply = ConversableAgent.generate_reply
        original_send = ConversableAgent.send
        
        @functools.wraps(original_generate_reply)
        def enhanced_generate_reply(self, messages=None, sender=None, **kwargs):
            """Enhanced generate_reply with event capture."""
            captor = get_event_captor()
            event_id = None
            
            if captor and captor.enabled:
                # Capture agent call start
                message_content = messages[-1].get("content", "") if messages else ""
                event_id = captor.capture_agent_call(
                    agent_name=self.name,
                    message=message_content,
                    metadata={
                        "sender": sender.name if sender else None,
                        "llm_config": getattr(self, "llm_config", {})
                    }
                )
            
            # Call original method
            start_time = time.time()
            result = original_generate_reply(self, messages, sender, **kwargs)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if captor and captor.enabled and event_id:
                # Capture agent response
                response_content = result if isinstance(result, str) else str(result)
                captor.capture_agent_response(
                    agent_name=self.name,
                    response=response_content,
                    event_id=event_id,
                    metadata={"duration_ms": duration_ms}
                )
            
            return result
        
        @functools.wraps(original_send)
        def enhanced_send(self, message, recipient, request_reply=None, silent=False):
            """Enhanced send with event capture."""
            captor = get_event_captor()
            
            if captor and captor.enabled:
                # Capture message
                content = message if isinstance(message, str) else message.get("content", "")
                captor.capture_message(
                    sender=self.name,
                    recipient=recipient.name,
                    content=content
                )
            
            # Call original method
            return original_send(self, message, recipient, request_reply, silent)
        
        # Apply patches
        ConversableAgent.generate_reply = enhanced_generate_reply
        ConversableAgent.send = enhanced_send
        
        logger.info("ConversableAgent patched successfully")
        return True

    except Exception as e:
        logger.error("Failed to patch ConversableAgent: %s", e)
        return False


def patch_group_chat():
    """
    Patch GroupChat to capture speaker selection (handoffs).
    """
    try:
        from autogen import GroupChat
        
        # Store original method
        original_select_speaker = GroupChat.select_speaker
        
        @functools.wraps(original_select_speaker)
        def enhanced_select_speaker(self, last_speaker, selector):
            """Enhanced select_speaker with handoff capture."""
            # Call original method
            next_speaker = original_select_speaker(self, last_speaker, selector)
            
            captor = get_event_captor()
            if captor and captor.enabled and last_speaker and next_speaker:
                # Capture handoff
                captor.capture_handoff(
                    from_agent=last_speaker.name,
                    to_agent=next_speaker.name,
                    reason="group_chat_selection"
                )
            
            return next_speaker
        
        # Apply patch
        GroupChat.select_speaker = enhanced_select_speaker
        
        logger.info("GroupChat patched successfully")
        return True

    except Exception as e:
        logger.error("Failed to patch GroupChat: %s", e)
        return False


def patch_code_executor():
    """
    Patch LocalCommandLineCodeExecutor to capture code_exec events.
    """
    try:
        from autogen.coding import LocalCommandLineCodeExecutor

        original_execute = LocalCommandLineCodeExecutor.execute_code_blocks

        @functools.wraps(original_execute)
        def enhanced_execute_code_blocks(self, code_blocks, *args, **kwargs):
            """Enhanced execute_code_blocks with event capture."""
            captor = get_event_captor()

            if captor and captor.enabled:
                for block in code_blocks:
                    captor.capture_code_execution(
                        agent_name=getattr(self, '_agent_name', 'code_executor'),
                        code=block.code,
                        language=block.language,
                    )

            start_time = time.time()
            result = original_execute(self, code_blocks, *args, **kwargs)
            duration_ms = int((time.time() - start_time) * 1000)

            if captor and captor.enabled:
                captor.capture_code_execution(
                    agent_name=getattr(self, '_agent_name', 'code_executor'),
                    code='\n'.join(b.code for b in code_blocks),
                    language=code_blocks[0].language if code_blocks else 'python',
                    result=result.output[:2000] if result.output else None,
                    exit_code=result.exit_code,
                    duration_ms=duration_ms,
                )

            return result

        LocalCommandLineCodeExecutor.execute_code_blocks = enhanced_execute_code_blocks

        logger.info("LocalCommandLineCodeExecutor patched successfully")
        return True

    except Exception as e:
        logger.error("Failed to patch code executor: %s", e)
        return False


def install_ag2_hooks() -> bool:
    """
    Install all AG2 hooks for event capture.
    Idempotent - safe to call multiple times.

    Returns:
        True if hooks installed successfully (or already installed)
    """
    global _hooks_installed

    # Check if already installed
    if _hooks_installed:
        logger.debug("Already installed, skipping")
        return True

    results = [
        patch_conversable_agent(),
        patch_group_chat(),
        patch_code_executor()
    ]

    success = all(results)
    if success:
        _hooks_installed = True
        logger.info("All hooks installed successfully")
    else:
        logger.warning("Some hooks failed to install")

    return success


def uninstall_ag2_hooks():
    """
    Uninstall AG2 hooks (restore original behavior).
    Note: This is currently not implemented as it requires storing
    original methods. Add if needed for testing.
    """
    logger.warning("Uninstall not implemented - restart process to remove hooks")
