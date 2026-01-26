"""AAS keyword handling functionality."""

from typing import List
from autogen import register_function
from autogen.agentchat.group import ContextVariables, AgentTarget, ReplyResult
from ..utils import AAS_keywords_dict


def record_aas_keywords(aas_keywords: List[str], context_variables: ContextVariables, cmbagent_instance) -> ReplyResult:
    """
    Extracts the relevant AAS keywords from the list, given the text input.
    
    Args:
        aas_keywords (list[str]): The list of AAS keywords to be recorded
        context_variables (dict): A dictionary maintaining execution context, including previous plans, 
            feedback tracking, and finalized plans.
    """
    aas_keyword_finder = cmbagent_instance.get_agent_from_name('aas_keyword_finder')
    control = cmbagent_instance.get_agent_from_name('control')
    
    for keyword in aas_keywords:
        if keyword not in AAS_keywords_dict:
            return ReplyResult(
                target=AgentTarget(aas_keyword_finder),  ## loop-back 
                message=f"Proposed keyword {keyword} not found in the list of AAS keywords. Extract keywords from provided AAS list!",
                context_variables=context_variables
            )
            
    context_variables["aas_keywords"] = {
        f'{aas_keyword}': AAS_keywords_dict[aas_keyword] for aas_keyword in aas_keywords
    }
        
    AAS_keyword_list = "\n".join(
        [f"- [{keyword}]({AAS_keywords_dict[keyword]})" for keyword in aas_keywords]
    )

    return ReplyResult(
        target=AgentTarget(control),  ## print and finish
        message=f"""
**AAS keywords**:\n
{AAS_keyword_list}
""",
        context_variables=context_variables
    )


def setup_keyword_functions(cmbagent_instance):
    """Register keyword-related functions with the appropriate agents."""
    aas_keyword_finder = cmbagent_instance.get_agent_from_name('aas_keyword_finder')
    
    # Create closure to bind cmbagent_instance
    def record_aas_keywords_closure(aas_keywords: List[str], context_variables: ContextVariables) -> ReplyResult:
        return record_aas_keywords(aas_keywords, context_variables, cmbagent_instance)
    
    register_function(
        record_aas_keywords_closure,
        caller=aas_keyword_finder,
        executor=aas_keyword_finder,
        description=r"""
        Extracts the relevant AAS keywords from the list, given the text input.
        Args:
            aas_keywords (list[str]): The list of AAS keywords to be recorded
            context_variables (dict): A dictionary maintaining execution context, including previous plans, 
                feedback tracking, and finalized plans.
        """,
    )
