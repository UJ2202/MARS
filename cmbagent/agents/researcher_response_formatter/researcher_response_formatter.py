import os
import base64
import logging
from cmbagent.base_agent import BaseAgent
from pydantic import BaseModel, Field
import re

_fmt_logger = logging.getLogger(__name__)


class ResearcherResponseFormatterAgent(BaseAgent):
    
    def __init__(self, llm_config=None, **kwargs):

        agent_id = os.path.splitext(os.path.abspath(__file__))[0]

        llm_config['config_list'][0]['response_format'] = self.StructuredMardown

        super().__init__(llm_config=llm_config, agent_id=agent_id, **kwargs)


    def set_agent(self,**kwargs):

        super().set_assistant_agent(**kwargs)

        # Register a high-priority reply function that programmatically
        # extracts <code> blocks from the researcher's output and converts
        # them to executable ```python blocks.  This bypasses the LLM
        # structured-output path which is lossy for long report content.
        def _extract_code_reply(agent, messages=None, sender=None, config=None):
            if not messages:
                return False, None
            last_msg = messages[-1]
            content = last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c)
                    for c in content
                )
            code_match = re.search(r'<code>\s*(.*?)\s*</code>', content, re.DOTALL)
            if not code_match:
                return False, None
            code_content = code_match.group(1).strip()
            if 'open(' in code_content and '.write(' in code_content:
                _fmt_logger.info("researcher_response_formatter: extracted <code> save script (%d chars), bypassing LLM", len(code_content))
                return True, f"```python\n{code_content}\n```"
            return False, None

        from autogen import ConversableAgent as _CA
        self.agent.register_reply(
            trigger=_CA,
            reply_func=_extract_code_reply,
            position=0,
        )


    class StructuredMardown(BaseModel):
        markdown_block: str = Field(..., description="A Markdown block containing the researcher's notes in a form ready to be saved. Should not contain ```markdown fences.")
        filename: str = Field(..., description="The name to give to this markdown notes in the format: <filename>.md.")

        def format(self) -> str:
            full_path = self.filename
            comment_line = f"<!-- filename: {full_path} -->"

            # Step 1: Remove any leading or trailing markdown code fences
            cleaned_block = re.sub(r"^\s*```(?:markdown)?\s*", "", self.markdown_block.strip(), flags=re.IGNORECASE)
            cleaned_block = re.sub(r"\s*```\s*$", "", cleaned_block, flags=re.IGNORECASE)

            lines = cleaned_block.splitlines()
            
            # Step 2: Replace or prepend the comment line
            if lines and lines[0].strip().startswith("<!-- filename:"):
                lines[0] = comment_line
            else:
                lines = [comment_line] + lines

            updated_markdown_block = "\n".join(lines)

            # Step 3: Produce a Python script the researcher_executor can run
            # to save the markdown content to disk.  We use repr() so that
            # all special characters inside the content are safely escaped.
            safe_content = repr(updated_markdown_block)
            safe_filename = repr(full_path)
            return (
    f"Save the following content to file.\n\n"
    f"```python\n"
    f"import os\n"
    f"content = {safe_content}\n"
    f"filename = {safe_filename}\n"
    f"filepath = os.path.join(os.getcwd(), filename)\n"
    f"with open(filepath, 'w', encoding='utf-8') as f:\n"
    f"    f.write(content)\n"
    f"print(f'Saved {{len(content)}} chars to {{filepath}}')\n"
    f"```"
            )

#     class StructuredMardown(BaseModel):
#         markdown_block: str = Field(..., description="The Mardown notes in a form ready to saved. Without spurious indentation at the start. It should not start with ```markdown, as it will be added automatically.")
#         filename: str = Field(..., description="The name to give to this markdown notes in the format: <filename>.md")
#         # relative_path: Optional[str] = Field(None, description="The relative path to the file (exclude <filename>.md itself)")

#         def format(self) -> str:
#             full_path = self.filename
#             comment_line = f"<!-- filename: {full_path} -->"
#             lines = self.markdown_block.splitlines()
        
#             if lines and lines[0].strip().startswith("<!-- filename:"):
#                 # Replace the existing filename comment with the new one.
#                 lines[0] = comment_line
#                 updated_markdown_block = "\n".join(lines)
#             else:
#                 # Prepend the new filename comment.
#                 updated_markdown_block = "\n".join([comment_line, self.markdown_block])
        
#             return (
# f"**Markdown:**\n\n"
# f"```markdown\n"
# f"{updated_markdown_block}\n"
# f"```"
#             )








