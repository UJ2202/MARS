import os
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

def run_streamlit_gui(deploy: bool):
    """Run the Streamlit GUI"""
    # Get the installed file path to cmbagent.cli
    gui_spec = find_spec("cmbagent.cli")
    if gui_spec is None or gui_spec.origin is None:
        print("❌ Could not locate cmbagent.cli")
        sys.exit(1)

    gui_path = gui_spec.origin.replace("cli.py", "gui/")

    # Ensure ~/.streamlit/config.toml exists and set theme to dark
    config_dir = os.path.expanduser("~/.streamlit")
    config_path = os.path.join(config_dir, "config.toml")
    os.makedirs(config_dir, exist_ok=True)

    theme_config = '[theme]\nbase = "dark"\n'

    # Write or update config.toml
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            lines = f.readlines()

        # Update existing theme section or append it
        with open(config_path, "w") as f:
            in_theme_block = False
            theme_written = False
            for line in lines:
                if line.strip().startswith("[theme]"):
                    in_theme_block = True
                    f.write(line)
                    f.write('base = "dark"\n')
                    theme_written = True
                    continue
                if in_theme_block and line.strip().startswith("["):
                    in_theme_block = False  # end of theme block
                if not in_theme_block:
                    f.write(line)

            if not theme_written:
                f.write("\n" + theme_config)
    else:
        with open(config_path, "w") as f:
            f.write(theme_config)

    # Run the Streamlit GUI
    print("🚀 Starting CMBAgent Streamlit GUI...")
    print("📡 Interface will be available at: http://localhost:8501")
    command = ["streamlit", "run", gui_path + "gui.py"]
    if deploy:
        command.extend(["--","--deploy"])
    sys.exit(subprocess.call(command))

def run_next_gui():
    """Run the Next.js GUI with FastAPI backend"""
    import signal
    import time
    
    # Get the installed file path to cmbagent package
    cmbagent_spec = find_spec("cmbagent")
    if cmbagent_spec is None or cmbagent_spec.origin is None:
        print("❌ Could not locate cmbagent package")
        sys.exit(1)
    
    # Get the package root directory
    package_root = Path(cmbagent_spec.origin).parent.parent
    backend_path = package_root / "backend"
    frontend_path = package_root / "cmbagent-ui"
    
    # Check if this is a development installation or pip installation
    is_editable_install = (package_root / ".git").exists() or "site-packages" not in str(package_root)
    
    # Check if directories exist
    if not backend_path.exists() or not frontend_path.exists():
        print("❌ Next.js UI components not found!")
        print("")
        if is_editable_install:
            print("It looks like you're using a development installation, but the Next.js")
            print("components are missing. Please make sure you have:")
            print("• Built the frontend: cd cmbagent-ui && npm install && npm run build")
            print("• All required files in the backend/ and cmbagent-ui/ directories")
        else:
            print("The Next.js interface is not available in the pip-installed version.")
            print("This is because pip packages only include Python files, not the full Next.js frontend.")
        print("")
        print("📋 To use the Next.js interface, you have these options:")
        print("")
        print("1. 🔧 Install from source (recommended):")
        print("   git clone https://github.com/CMBAgents/cmbagent.git")
        print("   cd cmbagent")
        print("   pip install -e .")
        print("   cd cmbagent-ui && npm install && npm run build")
        print("   cd .. && cmbagent run --next")
        print("")
        print("2. 🐳 Use Docker (easiest):")
        print("   docker pull docker.io/borisbolliet/cmbagent-ui:latest")
        print("   docker run -p 3000:3000 -p 8000:8000 \\")
        print("     -e OPENAI_API_KEY=\"your-key-here\" \\")
        print("     docker.io/borisbolliet/cmbagent-ui:latest")
        print("")
        print("3. 🌐 Use Streamlit interface instead:")
        print("   cmbagent run --streamlit")
        print("")
        print("4. 💻 Try HuggingFace Spaces (online):")
        print("   https://huggingface.co/spaces/astropilot-ai/cmbagent")
        print("")
        sys.exit(1)
    
    # Check if run.py exists
    run_script = backend_path / "run.py"
    if not run_script.exists():
        print("❌ Could not locate backend/run.py")
        print(f"Expected path: {run_script}")
        sys.exit(1)
    
    # Check if package.json exists
    package_json = frontend_path / "package.json"
    if not package_json.exists():
        print("❌ Could not locate frontend/package.json")
        print(f"Expected path: {package_json}")
        print("💡 Make sure Node.js dependencies are installed")
        sys.exit(1)
    
    print("🚀 Starting CMBAgent Full Stack...")
    print("📡 Backend will be available at: http://localhost:8000")
    print("🌐 Frontend will be available at: http://localhost:3000")
    print("📖 API docs: http://localhost:8000/docs")
    print("\n" + "="*50)
    
    backend_process = None
    frontend_process = None
    
    def cleanup(signum=None, frame=None):
        """Cleanup function to stop both processes"""
        print("\n🛑 Stopping servers...")
        if backend_process:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
                print("   Backend server stopped")
            except subprocess.TimeoutExpired:
                backend_process.kill()
                print("   Backend server force killed")
        
        if frontend_process:
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
                print("   Frontend server stopped")
            except subprocess.TimeoutExpired:
                frontend_process.kill()
                print("   Frontend server force killed")
        
        sys.exit(0)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    try:
        # Start backend server
        print("🔧 Starting backend server...")
        backend_process = subprocess.Popen(
            [sys.executable, "run.py"],
            cwd=backend_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("✅ Backend server started")
        
        # Give backend time to start
        time.sleep(3)
        
        # Check if backend is still running
        if backend_process.poll() is not None:
            print("❌ Backend server failed to start")
            stdout, stderr = backend_process.communicate()
            if stderr:
                print(f"Error: {stderr.decode()}")
            sys.exit(1)
        
        # Start frontend server
        print("🔧 Starting frontend server...")
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("✅ Frontend server started")
        
        print("\n🎉 CMBAgent Full Stack is running!")
        print("📡 Backend API: http://localhost:8000")
        print("🌐 Frontend UI: http://localhost:3000 (or next available port)")
        print("📖 API Documentation: http://localhost:8000/docs")
        print("\n💡 Press Ctrl+C to stop both servers")
        
        # Wait for both processes
        while True:
            # Check if processes are still running
            backend_running = backend_process.poll() is None
            frontend_running = frontend_process.poll() is None
            
            if not backend_running:
                print("❌ Backend server stopped unexpectedly")
                break
            
            if not frontend_running:
                print("❌ Frontend server stopped unexpectedly")
                break
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        print(f"❌ Error starting servers: {e}")
        cleanup()
        sys.exit(1)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        prog="cmbagent",
        description="CMBAgent - Multi-Agent System for Scientific Discovery"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Run command with interface options
    run_parser = subparsers.add_parser(
        "run", 
        help="Launch the CMBAgent user interface"
    )
    interface_group = run_parser.add_mutually_exclusive_group()
    interface_group.add_argument(
        "--streamlit",
        action="store_true",
        help="Launch the Streamlit interface (default)"
    )
    interface_group.add_argument(
        "--next",
        action="store_true", 
        help="Launch the Next.js interface with FastAPI backend"
    )
    
    # Deploy command (for Streamlit only - HuggingFace Spaces)
    subparsers.add_parser(
        "deploy",
        help="Launch Streamlit GUI with deployment settings for Hugging Face Spaces"
    )

    # Branch command
    branch_parser = subparsers.add_parser(
        "branch",
        help="Create a branch from a specific workflow step"
    )
    branch_parser.add_argument("run_id", help="Workflow run ID to branch from")
    branch_parser.add_argument("step_id", help="Step ID to branch from")
    branch_parser.add_argument("--name", required=True, help="Branch name")
    branch_parser.add_argument("--hypothesis", help="Hypothesis being tested")

    # Play-from command
    play_parser = subparsers.add_parser(
        "play-from",
        help="Resume execution from a specific node"
    )
    play_parser.add_argument("run_id", help="Workflow run ID")
    play_parser.add_argument("node_id", help="Node ID to resume from")

    # Compare command
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two workflow branches"
    )
    compare_parser.add_argument("run_id_1", help="First run ID")
    compare_parser.add_argument("run_id_2", help="Second run ID")

    # Branch tree command
    tree_parser = subparsers.add_parser(
        "branch-tree",
        help="Visualize branch tree for a workflow"
    )
    tree_parser.add_argument("run_id", help="Root workflow run ID")

    args = parser.parse_args()

    if args.command == "run":
        if args.next:
            run_next_gui()
        else:
            # Default to Streamlit if no interface specified or --streamlit explicitly used
            run_streamlit_gui(False)
    elif args.command == "deploy":
        run_streamlit_gui(True)
    elif args.command == "branch":
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import BranchManager
        import json

        db_session = get_session()
        manager = BranchManager(db_session, args.run_id)
        new_run_id = manager.create_branch(
            step_id=args.step_id,
            branch_name=args.name,
            hypothesis=args.hypothesis
        )
        db_session.close()

        print(f"✅ Branch created successfully!")
        print(f"Branch name: {args.name}")
        print(f"New run ID: {new_run_id}")

    elif args.command == "play-from":
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import PlayFromNodeExecutor
        import json

        db_session = get_session()
        executor = PlayFromNodeExecutor(db_session, args.run_id)
        result = executor.play_from_node(args.node_id)
        db_session.close()

        print(f"✅ Workflow prepared for resumption")
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")

    elif args.command == "compare":
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import BranchComparator
        import json

        db_session = get_session()
        comparator = BranchComparator(db_session)
        comparison = comparator.compare_branches(args.run_id_1, args.run_id_2)
        db_session.close()

        print("📊 Branch Comparison")
        print("=" * 50)
        print(json.dumps(comparison, indent=2))

    elif args.command == "branch-tree":
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import BranchComparator

        db_session = get_session()
        comparator = BranchComparator(db_session)
        tree = comparator.visualize_branch_tree(args.run_id)
        db_session.close()

        print("🌳 Branch Tree")
        print("=" * 50)
        print(comparator._format_tree(tree))

    else:
        parser.print_help()
