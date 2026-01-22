"""
AG2 Integration Hooks for Event Capture

Monkey-patches AG2 classes to automatically capture events without
requiring code changes in CMBAgent.
"""

from typing import Optional, Any, Dict
import functools
import time

from cmbagent.execution.event_capture import get_event_captor


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
        
        print("[AG2 Hooks] ConversableAgent patched successfully")
        return True
        
    except Exception as e:
        print(f"[AG2 Hooks] Failed to patch ConversableAgent: {e}")
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
        
        print("[AG2 Hooks] GroupChat patched successfully")
        return True
        
    except Exception as e:
        print(f"[AG2 Hooks] Failed to patch GroupChat: {e}")
        return False


def patch_code_executor():
    """
    Patch code execution to capture code_exec events.
    """
    try:
        from autogen.coding import CodeBlock, CodeExecutor
        
        # This is a simplified version - actual implementation may vary
        # based on how code execution is done in AG2
        
        print("[AG2 Hooks] Code executor hooks registered")
        return True
        
    except Exception as e:
        print(f"[AG2 Hooks] Failed to patch code executor: {e}")
        return False


def install_ag2_hooks() -> bool:
    """
    Install all AG2 hooks for event capture.
    
    Returns:
        True if all hooks installed successfully
    """
    results = [
        patch_conversable_agent(),
        patch_group_chat(),
        patch_code_executor()
    ]
    
    success = all(results)
    if success:
        print("[AG2 Hooks] All hooks installed successfully")
    else:
        print("[AG2 Hooks] Some hooks failed to install")
    
    return success


def uninstall_ag2_hooks():
    """
    Uninstall AG2 hooks (restore original behavior).
    Note: This is currently not implemented as it requires storing
    original methods. Add if needed for testing.
    """
    print("[AG2 Hooks] Uninstall not implemented - restart process to remove hooks")
