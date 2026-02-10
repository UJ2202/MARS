# import warnings
# warnings.filterwarnings("ignore", message=r'Field "model_client_cls" in LLMConfigEntry has conflict with protected namespace "model_"')

import warnings

warnings.filterwarnings(
    "ignore",                               # action
    message=r"Update function string contains no variables\.",  # regex
    category=UserWarning,                   # same category that’s raised
    module=r"autogen\.agentchat\.conversable_agent"  # where it comes from
)


from .cmbagent import CMBAgent
from .rag_utils import make_rag_agents
from .version import __version__
import os
from IPython.display import Image, display, Markdown
from .cmbagent_utils import LOGO, IMG_WIDTH, cmbagent_disable_display

# Workflow functions - import from workflows module
from .workflows import (
    planning_and_control_context_carryover,
    planning_and_control,
    deep_research,  # Alias for planning_and_control_context_carryover
    one_shot,
    human_in_the_loop,
    control,
    # Copilot workflows
    copilot,
    copilot_async,
    quick_task,
    planned_task,
    interactive_session,
)

# Keyword functions
from .keywords import get_keywords

# Processing functions
from .processing import summarize_document, summarize_documents, preprocess_task

# Utilities
from .utils import work_dir_default

# Workflow callbacks for event tracking
from .callbacks import (
    WorkflowCallbacks, 
    PlanInfo, 
    StepInfo, 
    StepStatus,
    create_null_callbacks,
    create_print_callbacks,
    create_websocket_callbacks,
    create_database_callbacks,
    merge_callbacks
)

# OCR functionality
from .ocr import process_single_pdf, process_folder

# arXiv downloader functionality
from .arxiv_downloader import arxiv_filter 


def print_cmbagent_logo():
    base_dir = os.path.dirname(__file__)
    png_path = os.path.join(base_dir, "logo.png")
    if not cmbagent_disable_display:
        display(Image(filename=png_path, width=IMG_WIDTH))
        display(Markdown(LOGO))

print_cmbagent_logo()